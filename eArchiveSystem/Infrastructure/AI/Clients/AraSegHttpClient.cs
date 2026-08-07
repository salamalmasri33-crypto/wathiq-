using System;
using System.Collections.Generic;
using System.Net.Http;
using System.Net.Http.Json;
using System.Net;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using eArchiveSystem.Application.Exceptions;
using Microsoft.Extensions.Options;
using eArchiveSystem.Application.Segmentation.Abstractions;
using eArchiveSystem.Application.Segmentation.Models;
using eArchiveSystem.Infrastructure.Configuration;

namespace eArchiveSystem.Infrastructure.AI.Clients
{
    /// <summary>
    /// Infrastructure adapter responsible for communicating with the external AraSeg service.
    ///
    /// This class belongs to the Infrastructure layer because it encapsulates details
    /// about how the application talks to an external system (transport, HTTP client,
    /// endpoint composition, etc.). It implements <see cref="IAraSegClient"/> to depend
    /// on an application-layer abstraction and to enable decoupling between application
    /// logic and infrastructure concerns (Dependency Inversion / Adapter Pattern).
    /// </summary>
    public sealed class AraSegHttpClient : IAraSegClient
    {
        private static readonly JsonSerializerOptions JsonOptions = new(JsonSerializerDefaults.Web);
        private const string InvalidResponseMessage = "AraSeg returned an invalid segmentation response";

        private readonly HttpClient _httpClient;
        private readonly AraSegOptions _options;

        /// <summary>
        /// Initializes a new instance of the <see cref="AraSegHttpClient"/> class.
        /// </summary>
        /// <param name="httpClient">The <see cref="HttpClient"/> used for transport.</param>
        /// <param name="options">The configured <see cref="AraSegOptions"/>.</param>
        /// <exception cref="ArgumentNullException">Thrown when a required argument is null.</exception>
        public AraSegHttpClient(HttpClient httpClient, IOptions<AraSegOptions> options)
        {
            _httpClient = httpClient ?? throw new ArgumentNullException(nameof(httpClient));
            _options = options?.Value ?? throw new ArgumentNullException(nameof(options));
        }

        /// <summary>
        /// Sends the specified text to the AraSeg service and returns the segmentation result.
        /// </summary>
        /// <param name="documentId">A unique identifier for the document being segmented.</param>
        /// <param name="text">The document text to send for segmentation.</param>
        /// <param name="track">The segmentation track to send to AraSeg.</param>
        /// <param name="cancellationToken">A token to cancel the operation.</param>
        /// <returns>A <see cref="SegmentationResult"/> describing the segmentation outcome.</returns>
        public async Task<SegmentationResult> SegmentAsync(
            string documentId,
            string text,
            string track,
            CancellationToken cancellationToken = default)
        {
            if (documentId is null)
            {
                throw new ArgumentNullException(nameof(documentId));
            }

            if (text is null)
            {
                throw new ArgumentNullException(nameof(text));
            }

            if (track is null)
            {
                throw new ArgumentNullException(nameof(track));
            }

            try
            {
                using var request = new HttpRequestMessage(HttpMethod.Post, BuildRequestPath())
                {
                    Content = JsonContent.Create(
                        new AraSegSegmentTextRequest
                        {
                            DocumentId = documentId,
                            Text = text,
                            Track = track
                        },
                        options: JsonOptions)
                };

                using var response = await _httpClient.SendAsync(
                    request,
                    HttpCompletionOption.ResponseHeadersRead,
                    cancellationToken);

                if (!response.IsSuccessStatusCode)
                {
                    throw await CreateFailureExceptionAsync(response, cancellationToken);
                }

                var payload = await response.Content.ReadFromJsonAsync<AraSegSegmentTextResponse>(
                    JsonOptions,
                    cancellationToken);

                return MapResponse(
                    payload ?? throw new AraSegClientException(InvalidResponseMessage, HttpStatusCode.BadGateway),
                    documentId,
                    text,
                    track);
            }
            catch (OperationCanceledException) when (!cancellationToken.IsCancellationRequested)
            {
                throw new AraSegClientException("AraSeg request timed out", HttpStatusCode.GatewayTimeout);
            }
            catch (HttpRequestException)
            {
                throw new AraSegClientException("AraSeg service is unavailable", HttpStatusCode.BadGateway);
            }
            catch (JsonException)
            {
                throw new AraSegClientException(InvalidResponseMessage, HttpStatusCode.BadGateway);
            }
        }

        private string BuildRequestPath() => _options.SegmentTextPath.TrimStart('/');

        private static async Task<AraSegClientException> CreateFailureExceptionAsync(
            HttpResponseMessage response,
            CancellationToken cancellationToken)
        {
            var payload = await response.Content.ReadAsStringAsync(cancellationToken);
            var error = TryDeserializeError(payload);
            var message = BuildFailureMessage(response.StatusCode, error?.Error?.Message);

            return new AraSegClientException(message, response.StatusCode, error?.Error?.Code);
        }

        private static AraSegErrorEnvelope? TryDeserializeError(string payload)
        {
            if (string.IsNullOrWhiteSpace(payload))
            {
                return null;
            }

            try
            {
                return JsonSerializer.Deserialize<AraSegErrorEnvelope>(payload, JsonOptions);
            }
            catch (JsonException)
            {
                return null;
            }
        }

        private static string BuildFailureMessage(HttpStatusCode statusCode, string? upstreamMessage)
        {
            if (!string.IsNullOrWhiteSpace(upstreamMessage)
                && (statusCode == HttpStatusCode.BadRequest
                    || statusCode == HttpStatusCode.UnprocessableEntity
                    || statusCode == HttpStatusCode.ServiceUnavailable))
            {
                return upstreamMessage;
            }

            return statusCode switch
            {
                HttpStatusCode.BadRequest => "AraSeg rejected the request as invalid",
                HttpStatusCode.UnprocessableEntity => "AraSeg rejected the requested segmentation track",
                HttpStatusCode.ServiceUnavailable => "AraSeg is not ready to process segmentation requests",
                _ => $"AraSeg request failed with status {(int)statusCode}"
            };
        }

        private static SegmentationResult MapResponse(
            AraSegSegmentTextResponse response,
            string expectedDocumentId,
            string expectedText,
            string expectedTrack)
        {
            if (!string.Equals(response.DocumentId, expectedDocumentId, StringComparison.Ordinal)
                || !string.Equals(response.Status, "completed", StringComparison.Ordinal)
                || !string.Equals(response.Provider, "AraSeg", StringComparison.Ordinal)
                || !string.Equals(response.Track, expectedTrack, StringComparison.Ordinal)
                || string.IsNullOrWhiteSpace(response.PipelineId)
                || response.NormalizedText is null
                || !string.Equals(response.NormalizedText, expectedText, StringComparison.Ordinal)
                || response.Segments is null
                || response.Segments.Count == 0)
            {
                throw new AraSegClientException(InvalidResponseMessage, HttpStatusCode.BadGateway);
            }

            var sentences = new List<SegmentedSentence>(response.Segments.Count);
            foreach (var segment in response.Segments)
            {
                if (segment?.Index is null
                    || segment.StartToken is null
                    || segment.EndToken is null
                    || string.IsNullOrEmpty(segment.Text)
                    || segment.Index.Value < 0
                    || segment.StartToken.Value < 0
                    || segment.EndToken.Value < segment.StartToken.Value)
                {
                    throw new AraSegClientException(InvalidResponseMessage, HttpStatusCode.BadGateway);
                }

                sentences.Add(new SegmentedSentence
                {
                    Index = segment.Index.Value,
                    Text = segment.Text,
                    StartToken = segment.StartToken.Value,
                    EndToken = segment.EndToken.Value
                });
            }

            return new SegmentationResult
            {
                DocumentId = response.DocumentId,
                Status = response.Status,
                Provider = response.Provider,
                Track = response.Track,
                PipelineId = response.PipelineId,
                NormalizedText = response.NormalizedText,
                Sentences = sentences
            };
        }
    }
}
