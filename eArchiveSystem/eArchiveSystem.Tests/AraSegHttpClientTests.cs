using System.Net;
using System.Text;
using System.Text.Json;
using eArchiveSystem.Application.Exceptions;
using eArchiveSystem.Application.Segmentation.Models;
using eArchiveSystem.Infrastructure.AI.Clients;
using eArchiveSystem.Infrastructure.Configuration;
using Microsoft.Extensions.Options;

namespace eArchiveSystem.Tests;

public sealed class AraSegHttpClientTests
{
    [Fact]
    public async Task SegmentAsync_sends_exact_request_url_and_contract_preserving_text()
    {
        HttpRequestMessage? capturedRequest = null;
        var inputText = "  مرحبا،  \tسطر أول\nسطر ثاني\\n[PAR] ؟!  ";
        var handler = new StubHandler(async request =>
        {
            capturedRequest = request;
            return Json(
                HttpStatusCode.OK,
                """
                {
                  "documentId": "doc-1",
                  "status": "completed",
                  "provider": "AraSeg",
                  "track": "PA",
                  "pipelineId": "pa-current-micro-ensemble-861752",
                  "normalizedText": "  مرحبا،  \tسطر أول\nسطر ثاني\\n[PAR] ؟!  ",
                  "segments": [
                    {
                      "index": 0,
                      "text": "  مرحبا،  \tسطر أول\nسطر ثاني\\n[PAR] ؟!  ",
                      "startToken": 0,
                      "endToken": 5
                    }
                  ]
                }
                """);
        });

        var result = await CreateClient(handler).SegmentAsync("doc-1", inputText, "PA");

        Assert.NotNull(capturedRequest);
        Assert.Equal(HttpMethod.Post, capturedRequest!.Method);
        Assert.Equal("http://127.0.0.1:8000/internal/api/v1/segment-text", capturedRequest.RequestUri!.OriginalString);

        var requestJson = await capturedRequest.Content!.ReadAsStringAsync();
        using var document = JsonDocument.Parse(requestJson);
        var root = document.RootElement;
        var propertyNames = root.EnumerateObject().Select(property => property.Name).ToArray();

        Assert.Equal(new[] { "documentId", "text", "track" }, propertyNames);
        Assert.Equal(3, propertyNames.Length);
        Assert.Equal("doc-1", root.GetProperty("documentId").GetString());
        Assert.Equal(inputText, root.GetProperty("text").GetString());
        Assert.Equal("PA", root.GetProperty("track").GetString());
        Assert.False(root.TryGetProperty("tokens", out _));
        Assert.False(root.TryGetProperty("offsets", out _));
        Assert.False(root.TryGetProperty("preserveParagraphs", out _));
        Assert.False(root.TryGetProperty("returnConfidence", out _));
        Assert.False(root.TryGetProperty("thresholds", out _));

        Assert.Equal("doc-1", result.DocumentId);
        Assert.Equal("completed", result.Status);
        Assert.Equal("AraSeg", result.Provider);
        Assert.Equal("PA", result.Track);
        Assert.Equal("pa-current-micro-ensemble-861752", result.PipelineId);
        Assert.Equal(inputText, result.NormalizedText);
        var sentence = Assert.Single(result.Sentences);
        Assert.Equal(0, sentence.Index);
        Assert.Equal(inputText, sentence.Text);
        Assert.Equal(0, sentence.StartToken);
        Assert.Equal(5, sentence.EndToken);
    }

    [Theory]
    [InlineData(HttpStatusCode.BadRequest, "INVALID_INPUT", "Input failed validation")]
    [InlineData(HttpStatusCode.UnprocessableEntity, "UNSUPPORTED_TRACK", "Only PA is supported")]
    [InlineData(HttpStatusCode.ServiceUnavailable, "MODEL_NOT_READY", "Model startup is incomplete")]
    public async Task SegmentAsync_maps_structured_upstream_errors(HttpStatusCode statusCode, string expectedErrorCode, string expectedMessage)
    {
        var exception = await Assert.ThrowsAsync<AraSegClientException>(() => CreateClient(
            new StubHandler(_ => Task.FromResult(Json(
                statusCode,
                $$"""
                {
                  "error": {
                    "code": "{{expectedErrorCode}}",
                    "message": "{{expectedMessage}}",
                    "requestId": "req-123"
                  }
                }
                """))))
            .SegmentAsync("doc-1", "النص", "PA"));

        Assert.Equal(statusCode, exception.StatusCode);
        Assert.Equal(expectedErrorCode, exception.ErrorCode);
        Assert.Equal(expectedMessage, exception.Message);
    }

    [Fact]
    public async Task SegmentAsync_maps_timeout_to_gateway_timeout()
    {
        var exception = await Assert.ThrowsAsync<AraSegClientException>(() => CreateClient(
            new StubHandler(_ => throw new TaskCanceledException()))
            .SegmentAsync("doc-1", "النص", "PA"));

        Assert.Equal(HttpStatusCode.GatewayTimeout, exception.StatusCode);
        Assert.Equal("AraSeg request timed out", exception.Message);
    }

    [Fact]
    public async Task SegmentAsync_maps_transport_failure_to_bad_gateway()
    {
        var exception = await Assert.ThrowsAsync<AraSegClientException>(() => CreateClient(
            new StubHandler(_ => throw new HttpRequestException("connection failed")))
            .SegmentAsync("doc-1", "النص", "PA"));

        Assert.Equal(HttpStatusCode.BadGateway, exception.StatusCode);
        Assert.Equal("AraSeg service is unavailable", exception.Message);
    }

    [Fact]
    public async Task SegmentAsync_preserves_cancellation()
    {
        using var cts = new CancellationTokenSource();
        cts.Cancel();

        await Assert.ThrowsAnyAsync<OperationCanceledException>(() => CreateClient(
            new StubHandler((_, cancellationToken) => Task.FromCanceled<HttpResponseMessage>(cancellationToken)))
            .SegmentAsync("doc-1", "النص", "PA", cts.Token));
    }

    [Fact]
    public async Task SegmentAsync_rejects_malformed_success_response()
    {
        var exception = await Assert.ThrowsAsync<AraSegClientException>(() => CreateClient(
            new StubHandler(_ => Task.FromResult(Json(
                HttpStatusCode.OK,
                """
                {
                  "documentId": "doc-1",
                  "status": "completed",
                  "provider": "AraSeg",
                  "track": "PA",
                  "normalizedText": "النص",
                  "segments": []
                }
                """))))
            .SegmentAsync("doc-1", "النص", "PA"));

        Assert.Equal(HttpStatusCode.BadGateway, exception.StatusCode);
        Assert.Equal("AraSeg returned an invalid segmentation response", exception.Message);
    }

    [Fact]
    public async Task SegmentAsync_rejects_success_response_when_normalized_text_does_not_match_source()
    {
        var exception = await Assert.ThrowsAsync<AraSegClientException>(() => CreateClient(
            new StubHandler(_ => Task.FromResult(Json(
                HttpStatusCode.OK,
                """
                {
                  "documentId": "doc-1",
                  "status": "completed",
                  "provider": "AraSeg",
                  "track": "PA",
                  "pipelineId": "pa-current-micro-ensemble-861752",
                  "normalizedText": "different text",
                  "segments": [
                    {
                      "index": 0,
                      "text": "different text",
                      "startToken": 0,
                      "endToken": 0
                    }
                  ]
                }
                """))))
            .SegmentAsync("doc-1", "original text", "PA"));

        Assert.Equal(HttpStatusCode.BadGateway, exception.StatusCode);
        Assert.Equal("AraSeg returned an invalid segmentation response", exception.Message);
    }

    private static AraSegHttpClient CreateClient(HttpMessageHandler handler, AraSegOptions? options = null)
    {
        var httpClient = new HttpClient(handler)
        {
            BaseAddress = new Uri("http://127.0.0.1:8000/"),
            Timeout = TimeSpan.FromSeconds(120)
        };

        return new AraSegHttpClient(
            httpClient,
            Options.Create(options ?? new AraSegOptions()));
    }

    private static HttpResponseMessage Json(HttpStatusCode statusCode, string json) =>
        new(statusCode)
        {
            Content = new StringContent(json, Encoding.UTF8, "application/json")
        };

    private sealed class StubHandler : HttpMessageHandler
    {
        private readonly Func<HttpRequestMessage, CancellationToken, Task<HttpResponseMessage>> _send;

        public StubHandler(Func<HttpRequestMessage, Task<HttpResponseMessage>> send)
            : this((request, _) => send(request))
        {
        }

        public StubHandler(Func<HttpRequestMessage, CancellationToken, Task<HttpResponseMessage>> send)
        {
            _send = send;
        }

        protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken) =>
            _send(request, cancellationToken);
    }
}
