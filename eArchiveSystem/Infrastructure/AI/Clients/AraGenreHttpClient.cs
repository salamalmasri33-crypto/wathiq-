using System.Diagnostics;
using System.Net;
using System.Net.Http.Json;
using System.Text.Json;
using System.Text.Json.Nodes;
using eArchiveSystem.Application.Classification.Abstractions;
using eArchiveSystem.Application.Classification.Models;
using eArchiveSystem.Application.Exceptions;
using eArchiveSystem.Infrastructure.Configuration;
using Microsoft.Extensions.Options;

namespace eArchiveSystem.Infrastructure.AI.Clients;

public sealed class AraGenreHttpClient : IAraGenreClient
{
    private static readonly JsonSerializerOptions JsonOptions = new(JsonSerializerDefaults.Web);
    private readonly HttpClient _httpClient;
    private readonly AraGenreOptions _options;
    private readonly ILogger<AraGenreHttpClient> _logger;

    public AraGenreHttpClient(HttpClient httpClient, IOptions<AraGenreOptions> options, ILogger<AraGenreHttpClient> logger)
    {
        _httpClient = httpClient;
        _options = options.Value;
        _logger = logger;
    }

    public async Task<AraGenreClassificationResult> ClassifyAsync(string institutionId, string documentId, string text, CancellationToken cancellationToken = default)
    {
        Validate(institutionId, nameof(institutionId));
        Validate(documentId, nameof(documentId));
        Validate(text, nameof(text));
        EnsureEnabled();

        var stopwatch = Stopwatch.StartNew();
        try
        {
            using var response = await _httpClient.PostAsJsonAsync(
                InstitutionPath(institutionId, "classify"),
                new AraGenreClassificationRequest { Id = documentId, Text = text },
                JsonOptions,
                cancellationToken);
            await EnsureSuccessAsync(response, institutionId, cancellationToken);
            var result = await response.Content.ReadFromJsonAsync<AraGenreClassificationResult>(JsonOptions, cancellationToken);
            return result ?? throw new ExternalServiceException("AraGenre returned an invalid classification response");
        }
        catch (OperationCanceledException) when (!cancellationToken.IsCancellationRequested)
        {
            throw new ExternalServiceException("AraGenre classification request timed out");
        }
        catch (HttpRequestException)
        {
            throw new ExternalServiceException("AraGenre service is unavailable");
        }
        catch (JsonException)
        {
            throw new ExternalServiceException("AraGenre returned an invalid classification response");
        }
        finally
        {
            _logger.LogInformation("AraGenre classification completed for document {DocumentId}, institution {InstitutionId}, in {ElapsedMs} ms", documentId, institutionId, stopwatch.ElapsedMilliseconds);
        }
    }

    public Task<JsonNode> GetStatusAsync(string institutionId, CancellationToken cancellationToken = default) => SendAsync(HttpMethod.Get, institutionId, "config/status", null, cancellationToken);
    public Task<JsonNode> GetTaxonomyAsync(string institutionId, CancellationToken cancellationToken = default) => SendAsync(HttpMethod.Get, institutionId, "config/taxonomy", null, cancellationToken);
    public Task<JsonNode> GetBroadAsync(string institutionId, string? broadId, string? query, CancellationToken cancellationToken = default) => SendAsync(HttpMethod.Get, institutionId, "config/broad" + IdSegment(broadId) + Query(query), null, cancellationToken);
    public Task<JsonNode> CreateBroadAsync(string institutionId, JsonNode body, CancellationToken cancellationToken = default) => SendJsonAsync(HttpMethod.Post, institutionId, "config/broad", body, cancellationToken);
    public Task<JsonNode> UpdateBroadAsync(string institutionId, string broadId, JsonNode body, CancellationToken cancellationToken = default) => SendJsonAsync(HttpMethod.Patch, institutionId, "config/broad" + IdSegment(broadId), body, cancellationToken);
    public Task<JsonNode> GetBroadDeletionImpactAsync(string institutionId, string broadId, CancellationToken cancellationToken = default) => SendAsync(HttpMethod.Get, institutionId, "config/broad" + IdSegment(broadId) + "/deletion-impact", null, cancellationToken);
    public Task<JsonNode> DeleteBroadAsync(string institutionId, string broadId, bool cascade, CancellationToken cancellationToken = default) => SendAsync(HttpMethod.Delete, institutionId, "config/broad" + IdSegment(broadId) + $"?cascade={cascade.ToString().ToLowerInvariant()}", null, cancellationToken);
    public Task<JsonNode> GetSpecificAsync(string institutionId, string? specificId, string? query, CancellationToken cancellationToken = default) => SendAsync(HttpMethod.Get, institutionId, "config/specific" + IdSegment(specificId) + Query(query), null, cancellationToken);
    public Task<JsonNode> CreateSpecificAsync(string institutionId, JsonNode body, CancellationToken cancellationToken = default) => SendJsonAsync(HttpMethod.Post, institutionId, "config/specific", body, cancellationToken);
    public Task<JsonNode> UpdateSpecificAsync(string institutionId, string specificId, JsonNode body, CancellationToken cancellationToken = default) => SendJsonAsync(HttpMethod.Patch, institutionId, "config/specific" + IdSegment(specificId), body, cancellationToken);
    public Task<JsonNode> GetSpecificDeletionImpactAsync(string institutionId, string specificId, CancellationToken cancellationToken = default) => SendAsync(HttpMethod.Get, institutionId, "config/specific" + IdSegment(specificId) + "/deletion-impact", null, cancellationToken);
    public Task<JsonNode> DeleteSpecificAsync(string institutionId, string specificId, bool cascade, CancellationToken cancellationToken = default) => SendAsync(HttpMethod.Delete, institutionId, "config/specific" + IdSegment(specificId) + $"?cascade={cascade.ToString().ToLowerInvariant()}", null, cancellationToken);
    public Task<JsonNode> GetExamplesAsync(string institutionId, string? exampleId, string? query, CancellationToken cancellationToken = default) => SendAsync(HttpMethod.Get, institutionId, "config/examples" + IdSegment(exampleId) + Query(query), null, cancellationToken);
    public Task<JsonNode> CreateExampleAsync(string institutionId, JsonNode body, CancellationToken cancellationToken = default) => SendJsonAsync(HttpMethod.Post, institutionId, "config/examples", body, cancellationToken);
    public Task<JsonNode> UpdateExampleAsync(string institutionId, string exampleId, JsonNode body, CancellationToken cancellationToken = default) => SendJsonAsync(HttpMethod.Patch, institutionId, "config/examples" + IdSegment(exampleId), body, cancellationToken);
    public Task<JsonNode> DeleteExampleAsync(string institutionId, string exampleId, CancellationToken cancellationToken = default) => SendAsync(HttpMethod.Delete, institutionId, "config/examples" + IdSegment(exampleId), null, cancellationToken);
    public Task<JsonNode> ReplaceTaxonomyAsync(string institutionId, JsonNode body, string? query, CancellationToken cancellationToken = default) => SendJsonAsync(HttpMethod.Put, institutionId, "config/taxonomy" + Query(query), body, cancellationToken);
    public Task<JsonNode> ReplaceExamplesAsync(string institutionId, JsonNode body, string? query, CancellationToken cancellationToken = default) => SendJsonAsync(HttpMethod.Put, institutionId, "config/examples" + Query(query), body, cancellationToken);
    public Task<JsonNode> RebuildIndexAsync(string institutionId, JsonNode? body, string? query, CancellationToken cancellationToken = default) => SendJsonAsync(HttpMethod.Post, institutionId, "config/rebuild-index" + Query(query), body ?? new JsonObject(), cancellationToken);

    public async Task<JsonNode> ImportFileAsync(string institutionId, string endpoint, Stream stream, string fileName, string? query, CancellationToken cancellationToken = default)
    {
        Validate(endpoint, nameof(endpoint));
        using var multipart = new MultipartFormDataContent();
        using var fileContent = new StreamContent(stream);
        fileContent.Headers.ContentType = new("application/json");
        multipart.Add(fileContent, "file", Path.GetFileName(fileName));
        return await SendAsync(HttpMethod.Post, institutionId, "config/" + endpoint + Query(query), multipart, cancellationToken);
    }

    private Task<JsonNode> SendJsonAsync(HttpMethod method, string institutionId, string path, JsonNode body, CancellationToken cancellationToken)
    {
        var content = JsonContent.Create(body, options: JsonOptions);
        return SendAsync(method, institutionId, path, content, cancellationToken);
    }

    private async Task<JsonNode> SendAsync(HttpMethod method, string institutionId, string path, HttpContent? content, CancellationToken cancellationToken)
    {
        Validate(institutionId, nameof(institutionId));
        EnsureEnabled();
        try
        {
            using var request = new HttpRequestMessage(method, InstitutionPath(institutionId, path)) { Content = content };
            using var response = await _httpClient.SendAsync(request, HttpCompletionOption.ResponseHeadersRead, cancellationToken);
            await EnsureSuccessAsync(response, institutionId, cancellationToken);
            var json = await response.Content.ReadAsStringAsync(cancellationToken);
            return string.IsNullOrWhiteSpace(json) ? new JsonObject() : JsonNode.Parse(json) ?? new JsonObject();
        }
        catch (OperationCanceledException) when (!cancellationToken.IsCancellationRequested)
        {
            throw new ExternalServiceException("AraGenre request timed out");
        }
        catch (HttpRequestException)
        {
            throw new ExternalServiceException("AraGenre service is unavailable");
        }
        catch (JsonException)
        {
            throw new ExternalServiceException("AraGenre returned an invalid JSON response");
        }
    }

    private static async Task EnsureSuccessAsync(HttpResponseMessage response, string institutionId, CancellationToken cancellationToken)
    {
        if (response.IsSuccessStatusCode) return;
        if (response.StatusCode == HttpStatusCode.NotFound)
            throw new NotFoundException($"Classification configuration was not found for institution '{institutionId}'");
        if (response.StatusCode == HttpStatusCode.Conflict)
            throw new ConflictException("The institution classifier must be rebuilt before this operation can complete");

        // Consume the upstream error payload so the connection can be reused, but do
        // not expose it because it may contain Python stack traces or service details.
        _ = await response.Content.ReadAsStringAsync(cancellationToken);
        throw new ExternalServiceException($"AraGenre rejected the request with status {(int)response.StatusCode}");
    }

    private string InstitutionPath(string institutionId, string suffix) => $"institutions/{Uri.EscapeDataString(institutionId.Trim())}/{suffix}";
    private static string IdSegment(string? id) => string.IsNullOrWhiteSpace(id) ? string.Empty : "/" + Uri.EscapeDataString(id.Trim());
    private static string Query(string? query) => string.IsNullOrWhiteSpace(query) ? string.Empty : "?" + query.TrimStart('?');
    private void EnsureEnabled() { if (!_options.Enabled) throw new ExternalServiceException("AraGenre integration is disabled"); }
    private static void Validate(string value, string name) { if (string.IsNullOrWhiteSpace(value)) throw new ValidationException($"{name} is required"); }
}
