using System.Text.Json.Nodes;
using eArchiveSystem.Application.Classification.Models;

namespace eArchiveSystem.Application.Classification.Abstractions;

public interface IAraGenreClient
{
    Task<AraGenreClassificationResult> ClassifyAsync(string institutionId, string documentId, string text, CancellationToken cancellationToken = default);
    Task<JsonNode> GetStatusAsync(string institutionId, CancellationToken cancellationToken = default);
    Task<JsonNode> GetTaxonomyAsync(string institutionId, CancellationToken cancellationToken = default);
    Task<JsonNode> GetBroadAsync(string institutionId, string? broadId, string? query, CancellationToken cancellationToken = default);
    Task<JsonNode> CreateBroadAsync(string institutionId, JsonNode body, CancellationToken cancellationToken = default);
    Task<JsonNode> UpdateBroadAsync(string institutionId, string broadId, JsonNode body, CancellationToken cancellationToken = default);
    Task<JsonNode> GetBroadDeletionImpactAsync(string institutionId, string broadId, CancellationToken cancellationToken = default);
    Task<JsonNode> DeleteBroadAsync(string institutionId, string broadId, bool cascade, CancellationToken cancellationToken = default);
    Task<JsonNode> GetSpecificAsync(string institutionId, string? specificId, string? query, CancellationToken cancellationToken = default);
    Task<JsonNode> CreateSpecificAsync(string institutionId, JsonNode body, CancellationToken cancellationToken = default);
    Task<JsonNode> UpdateSpecificAsync(string institutionId, string specificId, JsonNode body, CancellationToken cancellationToken = default);
    Task<JsonNode> GetSpecificDeletionImpactAsync(string institutionId, string specificId, CancellationToken cancellationToken = default);
    Task<JsonNode> DeleteSpecificAsync(string institutionId, string specificId, bool cascade, CancellationToken cancellationToken = default);
    Task<JsonNode> GetExamplesAsync(string institutionId, string? exampleId, string? query, CancellationToken cancellationToken = default);
    Task<JsonNode> CreateExampleAsync(string institutionId, JsonNode body, CancellationToken cancellationToken = default);
    Task<JsonNode> UpdateExampleAsync(string institutionId, string exampleId, JsonNode body, CancellationToken cancellationToken = default);
    Task<JsonNode> DeleteExampleAsync(string institutionId, string exampleId, CancellationToken cancellationToken = default);
    Task<JsonNode> ImportFileAsync(string institutionId, string endpoint, Stream stream, string fileName, string? query, CancellationToken cancellationToken = default);
    Task<JsonNode> ReplaceTaxonomyAsync(string institutionId, JsonNode body, string? query, CancellationToken cancellationToken = default);
    Task<JsonNode> ReplaceExamplesAsync(string institutionId, JsonNode body, string? query, CancellationToken cancellationToken = default);
    Task<JsonNode> RebuildIndexAsync(string institutionId, JsonNode? body, string? query, CancellationToken cancellationToken = default);
}
