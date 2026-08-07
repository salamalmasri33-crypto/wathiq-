using System.Text.Json.Nodes;
using eArchiveSystem.Application.Classification.Abstractions;
using eArchiveSystem.Application.Classification.Models;
using eArchiveSystem.Application.Exceptions;
using eArchiveSystem.Application.Interfaces.Persistence;
using eArchiveSystem.Application.Interfaces.Services;
using eArchiveSystem.Domain.Models;

namespace eArchiveSystem.Application.Services;

public sealed class InstitutionClassificationService : IInstitutionClassificationService
{
    private readonly IUserRepository _users;
    private readonly IInstitutionScopeResolver _scope;
    private readonly IAraGenreClient _client;

    public InstitutionClassificationService(IUserRepository users, IInstitutionScopeResolver scope, IAraGenreClient client)
    {
        _users = users;
        _scope = scope;
        _client = client;
    }

    public async Task<JsonNode> GetStatusAsync(string requesterId, string? institutionId, CancellationToken ct = default) => await _client.GetStatusAsync(await AdminScope(requesterId, institutionId), ct);
    public async Task<JsonNode> GetTaxonomyAsync(string requesterId, string? institutionId, CancellationToken ct = default) => await _client.GetTaxonomyAsync(await AdminScope(requesterId, institutionId), ct);
    public async Task<JsonNode> GetTaxonomyOptionsAsync(string requesterId, string? institutionId, CancellationToken ct = default)
    {
        var requester = await Requester(requesterId);
        var scope = _scope.ResolveForMember(requester, institutionId);
        return ProjectTaxonomyOptions(scope, await _client.GetTaxonomyAsync(scope, ct));
    }

    private static JsonNode ProjectTaxonomyOptions(string institutionId, JsonNode taxonomy)
    {
        var output = new JsonObject { ["institutionId"] = institutionId, ["broadCategories"] = new JsonArray() };
        var target = (JsonArray)output["broadCategories"]!;
        var source = taxonomy["broad_categories"] as JsonArray ?? taxonomy["broadCategories"] as JsonArray ?? taxonomy["broad_genres"] as JsonArray ?? taxonomy["broadGenres"] as JsonArray;
        if (source is null) return output;
        foreach (var node in source.OfType<JsonObject>())
        {
            if (Bool(node, "is_active", "isActive") is false) continue;
            var id = Text(node, "id", "broad_category", "broadCategory", "broad_genre", "broadGenre");
            if (string.IsNullOrWhiteSpace(id)) continue;
            var broad = new JsonObject { ["id"] = id, ["nameAr"] = Text(node, "name_ar", "nameAr") ?? id, ["nameEn"] = Text(node, "name_en", "nameEn") ?? id, ["isActive"] = true, ["specificTypes"] = new JsonArray() };
            var specifics = node["specific_types"] as JsonArray ?? node["specificTypes"] as JsonArray ?? node["specific_genres"] as JsonArray ?? node["specificGenres"] as JsonArray;
            if (specifics is not null)
                foreach (var child in specifics.OfType<JsonObject>())
                {
                    if (Bool(child, "is_active", "isActive") is false) continue;
                    var specificId = Text(child, "id", "specific_type", "specificType", "specific_genre", "specificGenre");
                    if (!string.IsNullOrWhiteSpace(specificId)) ((JsonArray)broad["specificTypes"]!).Add(new JsonObject { ["id"] = specificId, ["nameAr"] = Text(child, "name_ar", "nameAr") ?? specificId, ["nameEn"] = Text(child, "name_en", "nameEn") ?? specificId, ["isActive"] = true });
                }
            target.Add(broad);
        }
        return output;
    }

    public async Task<ClassifyTextResultDto> ClassifyTextAsync(string requesterId, ClassifyTextDto dto, CancellationToken ct = default)
    {
        if (string.IsNullOrWhiteSpace(dto.Id) || string.IsNullOrWhiteSpace(dto.Text))
            throw new ValidationException("Id and Text are required");
        var requester = await Requester(requesterId);
        var institutionId = _scope.ResolveForMember(requester, dto.InstitutionId);
        return await ClassifyForDocumentAsync(institutionId, dto.Id, dto.Text, ct);
    }

    public async Task<ClassifyTextResultDto> ClassifyForDocumentAsync(string institutionId, string documentId, string text, CancellationToken ct = default)
    {
        if (string.IsNullOrWhiteSpace(institutionId)) throw new ValidationException("Document institution is required for classification");
        if (string.IsNullOrWhiteSpace(documentId) || string.IsNullOrWhiteSpace(text)) throw new ValidationException("Document id and text are required");
        var result = await _client.ClassifyAsync(institutionId.Trim(), documentId.Trim(), text, ct);
        return new ClassifyTextResultDto
        {
            Id = result.Id,
            BroadGenre = result.BroadGenre,
            SpecificGenre = result.SpecificGenre
        };
    }

    public async Task ValidateGenreSelectionAsync(string institutionId, string broadGenre, string specificGenre, CancellationToken ct = default)
    {
        if (string.IsNullOrWhiteSpace(institutionId)) throw new ValidationException("Document institution is required to validate genres");
        var taxonomy = ParseTaxonomy(await _client.GetTaxonomyAsync(institutionId.Trim(), ct));
        var broadId = broadGenre.Trim();
        var specificId = specificGenre.Trim();

        if (!taxonomy.BroadGenres.TryGetValue(broadId, out var broad))
            throw new NotFoundException($"Broad genre '{broadId}' was not found for the document institution");
        if (!broad.IsActive) throw new ValidationException($"Broad genre '{broadId}' is inactive");
        if (!taxonomy.SpecificGenres.TryGetValue(specificId, out var specific))
            throw new NotFoundException($"Specific genre '{specificId}' was not found for the document institution");
        if (!specific.IsActive) throw new ValidationException($"Specific genre '{specificId}' is inactive");
        if (!string.Equals(specific.BroadId, broadId, StringComparison.OrdinalIgnoreCase))
            throw new ValidationException("SpecificGenre does not belong to the selected BroadGenre");
    }

    private static GenreTaxonomySnapshot ParseTaxonomy(JsonNode root)
    {
        var broad = new Dictionary<string, GenreTaxonomyBroad>(StringComparer.OrdinalIgnoreCase);
        var specific = new Dictionary<string, GenreTaxonomySpecific>(StringComparer.OrdinalIgnoreCase);
        Visit(root, null, broad, specific);
        if (broad.Count == 0 || specific.Count == 0)
            throw new ExternalServiceException("AraGenre returned an invalid taxonomy response");
        return new GenreTaxonomySnapshot(broad, specific);
    }

    private static void Visit(JsonNode? node, string? inheritedBroadId,
        IDictionary<string, GenreTaxonomyBroad> broad,
        IDictionary<string, GenreTaxonomySpecific> specific)
    {
        if (node is JsonArray array)
        {
            foreach (var child in array) Visit(child, inheritedBroadId, broad, specific);
            return;
        }
        if (node is not JsonObject obj) return;

        // AraGenre's taxonomy endpoint uses broad_category/specific_type, while
        // configuration imports may use the other supported aliases.
        var id = Text(obj, "id", "broad_id", "specific_id", "broad_category", "specific_type", "technical_id", "code");
        var parent = Text(obj, "broad_id", "parent_broad_id", "broadGenre", "broad_genre", "broad_category") ?? inheritedBroadId;
        var isSpecific = obj.ContainsKey("specific_id") || obj.ContainsKey("specific_type") || obj.ContainsKey("parent_broad_id") ||
                         (!string.IsNullOrWhiteSpace(parent) && !string.Equals(parent, id, StringComparison.OrdinalIgnoreCase));
        var active = Bool(obj, "is_active", "is_enabled", "active", "enabled") ?? true;

        if (!string.IsNullOrWhiteSpace(id))
        {
            if (isSpecific && !string.IsNullOrWhiteSpace(parent))
                specific[id] = new GenreTaxonomySpecific(id, parent, active);
            else
                broad[id] = new GenreTaxonomyBroad(id, active);
        }

        foreach (var pair in obj)
        {
            var childBroad = pair.Key.Contains("specific", StringComparison.OrdinalIgnoreCase) ? id ?? inheritedBroadId : inheritedBroadId;
            Visit(pair.Value, childBroad, broad, specific);
        }
    }

    private static string? Text(JsonObject obj, params string[] names)
    {
        foreach (var name in names)
            if (obj[name] is JsonValue value && value.TryGetValue<string>(out var result) && !string.IsNullOrWhiteSpace(result)) return result;
        return null;
    }

    private static bool? Bool(JsonObject obj, params string[] names)
    {
        foreach (var name in names)
            if (obj[name] is JsonValue value && value.TryGetValue<bool>(out var result)) return result;
        return null;
    }

    public async Task<JsonNode> GetBroadAsync(string r, string? i, string? id, string? q, CancellationToken ct = default) => await _client.GetBroadAsync(await AdminScope(r, i), id, q, ct);
    public async Task<JsonNode> CreateBroadAsync(string r, string? i, JsonNode b, CancellationToken ct = default) => await _client.CreateBroadAsync(await AdminScope(r, i), RequireBody(b), ct);
    public async Task<JsonNode> UpdateBroadAsync(string r, string? i, string id, JsonNode b, CancellationToken ct = default) => await _client.UpdateBroadAsync(await AdminScope(r, i), RequireId(id), RequireBody(b), ct);
    public async Task<JsonNode> GetBroadDeletionImpactAsync(string r, string? i, string id, CancellationToken ct = default) => await _client.GetBroadDeletionImpactAsync(await AdminScope(r, i), RequireId(id), ct);
    public async Task<JsonNode> DeleteBroadAsync(string r, string? i, string id, bool cascade, CancellationToken ct = default) => await _client.DeleteBroadAsync(await AdminScope(r, i), RequireId(id), cascade, ct);
    public async Task<JsonNode> GetSpecificAsync(string r, string? i, string? id, string? q, CancellationToken ct = default) => await _client.GetSpecificAsync(await AdminScope(r, i), id, q, ct);
    public async Task<JsonNode> CreateSpecificAsync(string r, string? i, JsonNode b, CancellationToken ct = default) => await _client.CreateSpecificAsync(await AdminScope(r, i), RequireBody(b), ct);
    public async Task<JsonNode> UpdateSpecificAsync(string r, string? i, string id, JsonNode b, CancellationToken ct = default) => await _client.UpdateSpecificAsync(await AdminScope(r, i), RequireId(id), RequireBody(b), ct);
    public async Task<JsonNode> GetSpecificDeletionImpactAsync(string r, string? i, string id, CancellationToken ct = default) => await _client.GetSpecificDeletionImpactAsync(await AdminScope(r, i), RequireId(id), ct);
    public async Task<JsonNode> DeleteSpecificAsync(string r, string? i, string id, bool cascade, CancellationToken ct = default) => await _client.DeleteSpecificAsync(await AdminScope(r, i), RequireId(id), cascade, ct);
    public async Task<JsonNode> GetExamplesAsync(string r, string? i, string? id, string? q, CancellationToken ct = default) => await _client.GetExamplesAsync(await AdminScope(r, i), id, q, ct);
    public async Task<JsonNode> CreateExampleAsync(string r, string? i, JsonNode b, CancellationToken ct = default) => await _client.CreateExampleAsync(await AdminScope(r, i), RequireBody(b), ct);
    public async Task<JsonNode> UpdateExampleAsync(string r, string? i, string id, JsonNode b, CancellationToken ct = default) => await _client.UpdateExampleAsync(await AdminScope(r, i), RequireId(id), RequireBody(b), ct);
    public async Task<JsonNode> DeleteExampleAsync(string r, string? i, string id, CancellationToken ct = default) => await _client.DeleteExampleAsync(await AdminScope(r, i), RequireId(id), ct);
    public async Task<JsonNode> ImportFileAsync(string r, string? i, string endpoint, Stream stream, string fileName, string? q, CancellationToken ct = default) => await _client.ImportFileAsync(await AdminScope(r, i), endpoint, stream, fileName, q, ct);
    public async Task<JsonNode> ReplaceTaxonomyAsync(string r, string? i, JsonNode b, string? q, CancellationToken ct = default) => await _client.ReplaceTaxonomyAsync(await AdminScope(r, i), RequireBody(b), q, ct);
    public async Task<JsonNode> ReplaceExamplesAsync(string r, string? i, JsonNode b, string? q, CancellationToken ct = default) => await _client.ReplaceExamplesAsync(await AdminScope(r, i), RequireBody(b), q, ct);
    public async Task<JsonNode> RebuildIndexAsync(string r, string? i, JsonNode? b, string? q, CancellationToken ct = default) => await _client.RebuildIndexAsync(await AdminScope(r, i), b, q, ct);

    private async Task<string> AdminScope(string requesterId, string? institutionId) => _scope.ResolveForAdministration(await Requester(requesterId), institutionId);
    private async Task<User> Requester(string requesterId) => string.IsNullOrWhiteSpace(requesterId)
        ? throw new UnauthorizedActionException("Authenticated user identifier is missing")
        : await _users.GetByIdAsync(requesterId) ?? throw new NotFoundException("User not found");
    private static JsonNode RequireBody(JsonNode? body) => body ?? throw new ValidationException("A JSON request body is required");
    private static string RequireId(string? id) => string.IsNullOrWhiteSpace(id) ? throw new ValidationException("Id is required") : id.Trim();
}
