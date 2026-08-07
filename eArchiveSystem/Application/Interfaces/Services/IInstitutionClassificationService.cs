using System.Text.Json.Nodes;
using eArchiveSystem.Application.Classification.Models;

namespace eArchiveSystem.Application.Interfaces.Services;

public interface IInstitutionClassificationService
{
    Task<JsonNode> GetStatusAsync(string requesterId, string? institutionId, CancellationToken cancellationToken = default);
    Task<JsonNode> GetTaxonomyAsync(string requesterId, string? institutionId, CancellationToken cancellationToken = default);
    Task<JsonNode> GetTaxonomyOptionsAsync(string requesterId, string? institutionId, CancellationToken cancellationToken = default);
    Task<ClassifyTextResultDto> ClassifyTextAsync(string requesterId, ClassifyTextDto dto, CancellationToken cancellationToken = default);
    Task<ClassifyTextResultDto> ClassifyForDocumentAsync(string institutionId, string documentId, string text, CancellationToken cancellationToken = default);
    Task ValidateGenreSelectionAsync(string institutionId, string broadGenre, string specificGenre, CancellationToken cancellationToken = default);
    Task<JsonNode> GetBroadAsync(string requesterId, string? institutionId, string? broadId, string? query, CancellationToken cancellationToken = default);
    Task<JsonNode> CreateBroadAsync(string requesterId, string? institutionId, JsonNode body, CancellationToken cancellationToken = default);
    Task<JsonNode> UpdateBroadAsync(string requesterId, string? institutionId, string broadId, JsonNode body, CancellationToken cancellationToken = default);
    Task<JsonNode> GetBroadDeletionImpactAsync(string requesterId, string? institutionId, string broadId, CancellationToken cancellationToken = default);
    Task<JsonNode> DeleteBroadAsync(string requesterId, string? institutionId, string broadId, bool cascade, CancellationToken cancellationToken = default);
    Task<JsonNode> GetSpecificAsync(string requesterId, string? institutionId, string? specificId, string? query, CancellationToken cancellationToken = default);
    Task<JsonNode> CreateSpecificAsync(string requesterId, string? institutionId, JsonNode body, CancellationToken cancellationToken = default);
    Task<JsonNode> UpdateSpecificAsync(string requesterId, string? institutionId, string specificId, JsonNode body, CancellationToken cancellationToken = default);
    Task<JsonNode> GetSpecificDeletionImpactAsync(string requesterId, string? institutionId, string specificId, CancellationToken cancellationToken = default);
    Task<JsonNode> DeleteSpecificAsync(string requesterId, string? institutionId, string specificId, bool cascade, CancellationToken cancellationToken = default);
    Task<JsonNode> GetExamplesAsync(string requesterId, string? institutionId, string? exampleId, string? query, CancellationToken cancellationToken = default);
    Task<JsonNode> CreateExampleAsync(string requesterId, string? institutionId, JsonNode body, CancellationToken cancellationToken = default);
    Task<JsonNode> UpdateExampleAsync(string requesterId, string? institutionId, string exampleId, JsonNode body, CancellationToken cancellationToken = default);
    Task<JsonNode> DeleteExampleAsync(string requesterId, string? institutionId, string exampleId, CancellationToken cancellationToken = default);
    Task<JsonNode> ImportFileAsync(string requesterId, string? institutionId, string endpoint, Stream stream, string fileName, string? query, CancellationToken cancellationToken = default);
    Task<JsonNode> ReplaceTaxonomyAsync(string requesterId, string? institutionId, JsonNode body, string? query, CancellationToken cancellationToken = default);
    Task<JsonNode> ReplaceExamplesAsync(string requesterId, string? institutionId, JsonNode body, string? query, CancellationToken cancellationToken = default);
    Task<JsonNode> RebuildIndexAsync(string requesterId, string? institutionId, JsonNode? body, string? query, CancellationToken cancellationToken = default);
}
