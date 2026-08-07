using System.Reflection;
using System.Text.Json.Nodes;
using eArchiveSystem.Application.Classification.Abstractions;
using eArchiveSystem.Application.Classification.Models;
using eArchiveSystem.Application.DTOs;
using eArchiveSystem.Application.Exceptions;
using eArchiveSystem.Application.Interfaces.Persistence;
using eArchiveSystem.Application.Services;
using eArchiveSystem.Domain.Models;

namespace eArchiveSystem.Tests;

public sealed class GenreMetadataTests
{
    [Fact]
    public void Metadata_and_search_contracts_have_genres_and_no_legacy_field()
    {
        foreach (var type in new[] { typeof(Metadata), typeof(AddMetadataDto), typeof(UpdateMetadataDto), typeof(MetadataPreviewDto), typeof(SearchDocumentsDto), typeof(SearchDocumentIndex) })
        {
            Assert.Null(type.GetProperty("Category", BindingFlags.Public | BindingFlags.Instance));
            Assert.NotNull(type.GetProperty("BroadGenre", BindingFlags.Public | BindingFlags.Instance));
            Assert.NotNull(type.GetProperty("SpecificGenre", BindingFlags.Public | BindingFlags.Instance));
        }

        Assert.NotNull(typeof(SearchDocumentsDto).GetProperty("InstitutionId", BindingFlags.Public | BindingFlags.Instance));
    }

    [Fact]
    public void Assessment_requires_both_genres()
    {
        var metadata = new Metadata { Id = "507f1f77bcf86cd799439011", Description = "summary", DocumentType = "Decision", Tags = ["tag"] };
        var result = new OcrExtractionAssessmentService().Assess(metadata, false);
        Assert.False(result.CoreFieldsComplete);
        Assert.True(result.RequiresReview);
        Assert.Contains("broadGenre", result.MissingFields);
        Assert.Contains("specificGenre", result.MissingFields);
    }

    [Fact]
    public async Task Validates_active_specific_under_selected_broad_for_same_institution()
    {
        var client = new FakeAraGenreClient(Taxonomy());
        var service = Service(client);
        await service.ValidateGenreSelectionAsync("institution-a", "BroadA", "SpecificA");
        Assert.Equal("institution-a", client.LastInstitutionId);
    }

    [Fact]
    public async Task Validates_genres_from_actual_aragenre_taxonomy_shape()
    {
        var taxonomy = JsonNode.Parse("""
        {"broad_categories":[
          {"broad_category":"AdministrativeAndOrganizational","is_active":true,"specific_types":[
            {"specific_type":"ProcedureAndWorkflow","is_active":true}]}
        ]}
        """)!;

        var service = Service(new FakeAraGenreClient(taxonomy));
        await service.ValidateGenreSelectionAsync(
            "inst-main",
            "AdministrativeAndOrganizational",
            "ProcedureAndWorkflow");
    }

    [Fact]
    public async Task Rejects_specific_from_another_broad()
    {
        var service = Service(new FakeAraGenreClient(Taxonomy()));
        await Assert.ThrowsAsync<ValidationException>(() => service.ValidateGenreSelectionAsync("institution-a", "BroadB", "SpecificA"));
    }

    [Fact]
    public async Task Rejects_inactive_genres()
    {
        var service = Service(new FakeAraGenreClient(Taxonomy()));
        await Assert.ThrowsAsync<ValidationException>(() => service.ValidateGenreSelectionAsync("institution-a", "BroadA", "SpecificInactive"));
    }

    private static InstitutionClassificationService Service(IAraGenreClient client) => new(new EmptyUsers(), new InstitutionScopeResolver(), client);

    private static JsonNode Taxonomy() => JsonNode.Parse("""
    {"broad_genres":[
      {"id":"BroadA","is_active":true,"specific_genres":[
        {"id":"SpecificA","is_active":true},
        {"id":"SpecificInactive","is_active":false}]},
      {"id":"BroadB","is_active":true,"specific_genres":[]}
    ]}
    """)!;

    private sealed class EmptyUsers : IUserRepository
    {
        public Task<User> GetByEmailAsync(string email) => Task.FromResult<User>(null!);
        public Task CreateAsync(User user) => Task.CompletedTask;
        public Task UpdateAsync(string id, User user) => Task.CompletedTask;
        public Task DeleteAsync(string id) => Task.CompletedTask;
        public Task<List<User>> GetAllAsync() => Task.FromResult(new List<User>());
        public Task<User> GetByIdAsync(string id) => Task.FromResult<User>(null!);
        public Task<User> GetByResetToken(string token) => Task.FromResult<User>(null!);
        public Task<List<User>> GetByRoleAsync(string role) => Task.FromResult(new List<User>());
        public Task<List<User>> GetByIdsAsync(List<string> ids) => Task.FromResult(new List<User>());
    }

    private sealed class FakeAraGenreClient(JsonNode taxonomy) : IAraGenreClient
    {
        public string? LastInstitutionId { get; private set; }
        public Task<JsonNode> GetTaxonomyAsync(string institutionId, CancellationToken cancellationToken = default) { LastInstitutionId = institutionId; return Task.FromResult(taxonomy.DeepClone()); }
        private static Task<JsonNode> Json() => Task.FromResult<JsonNode>(new JsonObject());
        public Task<AraGenreClassificationResult> ClassifyAsync(string a,string b,string c,CancellationToken d=default)=>throw new NotImplementedException();
        public Task<JsonNode> GetStatusAsync(string a,CancellationToken b=default)=>Json(); public Task<JsonNode> GetBroadAsync(string a,string? b,string? c,CancellationToken d=default)=>Json();
        public Task<JsonNode> CreateBroadAsync(string a,JsonNode b,CancellationToken c=default)=>Json(); public Task<JsonNode> UpdateBroadAsync(string a,string b,JsonNode c,CancellationToken d=default)=>Json(); public Task<JsonNode> GetBroadDeletionImpactAsync(string a,string b,CancellationToken c=default)=>Json(); public Task<JsonNode> DeleteBroadAsync(string a,string b,bool c,CancellationToken d=default)=>Json();
        public Task<JsonNode> GetSpecificAsync(string a,string? b,string? c,CancellationToken d=default)=>Json(); public Task<JsonNode> CreateSpecificAsync(string a,JsonNode b,CancellationToken c=default)=>Json(); public Task<JsonNode> UpdateSpecificAsync(string a,string b,JsonNode c,CancellationToken d=default)=>Json(); public Task<JsonNode> GetSpecificDeletionImpactAsync(string a,string b,CancellationToken c=default)=>Json(); public Task<JsonNode> DeleteSpecificAsync(string a,string b,bool c,CancellationToken d=default)=>Json();
        public Task<JsonNode> GetExamplesAsync(string a,string? b,string? c,CancellationToken d=default)=>Json(); public Task<JsonNode> CreateExampleAsync(string a,JsonNode b,CancellationToken c=default)=>Json(); public Task<JsonNode> UpdateExampleAsync(string a,string b,JsonNode c,CancellationToken d=default)=>Json(); public Task<JsonNode> DeleteExampleAsync(string a,string b,CancellationToken c=default)=>Json();
        public Task<JsonNode> ImportFileAsync(string a,string b,Stream c,string d,string? e,CancellationToken f=default)=>Json(); public Task<JsonNode> ReplaceTaxonomyAsync(string a,JsonNode b,string? c,CancellationToken d=default)=>Json(); public Task<JsonNode> ReplaceExamplesAsync(string a,JsonNode b,string? c,CancellationToken d=default)=>Json(); public Task<JsonNode> RebuildIndexAsync(string a,JsonNode? b,string? c,CancellationToken d=default)=>Json();
    }
}
