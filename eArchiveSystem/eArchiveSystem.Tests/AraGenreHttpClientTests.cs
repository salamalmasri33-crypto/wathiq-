using System.Net;
using System.Text;
using System.Text.Json;
using eArchiveSystem.Application.Exceptions;
using eArchiveSystem.Infrastructure.AI.Clients;
using eArchiveSystem.Infrastructure.Configuration;
using Microsoft.Extensions.Logging.Abstractions;
using Microsoft.Extensions.Options;

namespace eArchiveSystem.Tests;

public sealed class AraGenreHttpClientTests
{
    [Fact]
    public async Task Classify_maps_snake_case_and_sends_expected_request()
    {
        HttpRequestMessage? captured = null;
        var handler = new StubHandler(async request =>
        {
            captured = request;
            var requestJson = await request.Content!.ReadAsStringAsync();
            Assert.Contains("\"id\":\"doc-1\"", requestJson);
            Assert.Contains("\"text\":\"sensitive text\"", requestJson);
            return Json(HttpStatusCode.OK, """{"id":"doc-1","broad_genre":"Administrative","specific_genre":"Decision"}""");
        });

        var result = await Client(handler).ClassifyAsync("institution/a", "doc-1", "sensitive text");

        Assert.Equal("Administrative", result.BroadGenre);
        Assert.Equal("Decision", result.SpecificGenre);
        Assert.EndsWith("/institutions/institution%2Fa/classify", captured!.RequestUri!.OriginalString, StringComparison.OrdinalIgnoreCase);
    }

    [Theory]
    [InlineData(HttpStatusCode.NotFound, typeof(NotFoundException))]
    [InlineData(HttpStatusCode.Conflict, typeof(ConflictException))]
    [InlineData(HttpStatusCode.InternalServerError, typeof(ExternalServiceException))]
    public async Task Maps_service_failures(HttpStatusCode status, Type expected)
    {
        var exception = await Record.ExceptionAsync(() => Client(new StubHandler(_ => Task.FromResult(Json(status, "{}")))).GetStatusAsync("institution-a"));
        Assert.IsType(expected, exception);
    }

    [Fact]
    public async Task Timeout_becomes_external_service_exception()
    {
        var handler = new StubHandler(_ => throw new TaskCanceledException());
        await Assert.ThrowsAsync<ExternalServiceException>(() => Client(handler).GetStatusAsync("institution-a"));
    }

    private static AraGenreHttpClient Client(HttpMessageHandler handler) => new(
        new HttpClient(handler) { BaseAddress = new Uri("http://127.0.0.1:8001/") },
        Options.Create(new AraGenreOptions()),
        NullLogger<AraGenreHttpClient>.Instance);

    private static HttpResponseMessage Json(HttpStatusCode status, string json) => new(status) { Content = new StringContent(json, Encoding.UTF8, "application/json") };

    private sealed class StubHandler(Func<HttpRequestMessage, Task<HttpResponseMessage>> send) : HttpMessageHandler
    {
        protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken) => send(request);
    }
}
