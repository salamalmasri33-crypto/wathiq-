using System.Reflection;
using eArchiveSystem.Application.DTOs;
using eArchiveSystem.Application.Interfaces.Persistence;
using eArchiveSystem.Application.Interfaces.Services;
using eArchiveSystem.Application.Segmentation.Abstractions;
using eArchiveSystem.Application.Segmentation.Services;
using eArchiveSystem.Domain.Models;
using eArchiveSystem.Infrastructure.AI.Clients;
using eArchiveSystem.Infrastructure.AI.Segmentation;
using eArchiveSystem.Infrastructure.Configuration;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Options;

namespace eArchiveSystem.Tests;

public sealed class AraSegRegistrationTests
{
    [Fact]
    public void Options_validator_accepts_valid_configuration()
    {
        var validator = new AraSegOptionsValidator();
        var result = validator.Validate(null, new AraSegOptions
        {
            BaseUrl = "http://127.0.0.1:8000",
            SegmentTextPath = "/internal/api/v1/segment-text",
            Track = "PA",
            TimeoutSeconds = 120
        });

        Assert.True(result.Succeeded);
    }

    [Theory]
    [InlineData("", "/internal/api/v1/segment-text", "PA", 120)]
    [InlineData("ftp://127.0.0.1:8000", "/internal/api/v1/segment-text", "PA", 120)]
    [InlineData("http://127.0.0.1:8000", "", "PA", 120)]
    [InlineData("http://127.0.0.1:8000", "/internal/api/v1/segment-text", "NOPNX", 120)]
    [InlineData("http://127.0.0.1:8000", "/internal/api/v1/segment-text", "PA", 0)]
    public void Options_validator_rejects_invalid_configuration(string baseUrl, string path, string track, int timeoutSeconds)
    {
        var validator = new AraSegOptionsValidator();
        var result = validator.Validate(null, new AraSegOptions
        {
            BaseUrl = baseUrl,
            SegmentTextPath = path,
            Track = track,
            TimeoutSeconds = timeoutSeconds
        });

        Assert.False(result.Succeeded);
        Assert.NotEmpty(result.Failures);
    }

    [Fact]
    public void Service_registration_binds_options_and_configures_http_client()
    {
        var configuration = new ConfigurationBuilder()
            .AddInMemoryCollection(new Dictionary<string, string?>
            {
                ["AraSeg:BaseUrl"] = "http://127.0.0.1:8000",
                ["AraSeg:SegmentTextPath"] = "/internal/api/v1/segment-text",
                ["AraSeg:Track"] = "PA",
                ["AraSeg:TimeoutSeconds"] = "120"
            })
            .Build();

        var services = new ServiceCollection();
        services.AddLogging();
        services.AddSingleton<IDocumentSegmentationRepository, StubDocumentSegmentationRepository>();
        services.AddSingleton<IDocumentRepository, StubDocumentRepository>();
        services.AddSingleton<IUserRepository, StubUserRepository>();
        services.AddSingleton<IDocumentAuthorizationService, StubDocumentAuthorizationService>();
        services.AddSingleton<IIndexingService, StubIndexingService>();
        services.AddAraSegSegmentation(configuration);

        using var provider = services.BuildServiceProvider();
        using var scope = provider.CreateScope();

        var options = scope.ServiceProvider.GetRequiredService<IOptions<AraSegOptions>>().Value;
        Assert.Equal("http://127.0.0.1:8000", options.BaseUrl);
        Assert.Equal("/internal/api/v1/segment-text", options.SegmentTextPath);
        Assert.Equal("PA", options.Track);
        Assert.Equal(120, options.TimeoutSeconds);

        var client = Assert.IsType<AraSegHttpClient>(scope.ServiceProvider.GetRequiredService<IAraSegClient>());
        Assert.IsType<AraSegSentenceSegmenter>(scope.ServiceProvider.GetRequiredService<ISentenceSegmenter>());
        Assert.IsType<DocumentSegmentationService>(scope.ServiceProvider.GetRequiredService<IDocumentSegmentationService>());

        var field = typeof(AraSegHttpClient).GetField("_httpClient", BindingFlags.Instance | BindingFlags.NonPublic);
        var httpClient = Assert.IsType<HttpClient>(field!.GetValue(client));
        Assert.Equal(new Uri("http://127.0.0.1:8000/"), httpClient.BaseAddress);
        Assert.Equal(TimeSpan.FromSeconds(120), httpClient.Timeout);
    }

    private sealed class StubDocumentSegmentationRepository : IDocumentSegmentationRepository
    {
        public Task<DocumentSegmentation?> GetByDocumentIdAsync(string documentId, CancellationToken cancellationToken = default) =>
            Task.FromResult<DocumentSegmentation?>(null);

        public Task UpsertAsync(DocumentSegmentation segmentation, CancellationToken cancellationToken = default) =>
            Task.CompletedTask;

        public Task SetProcessingAsync(string documentId, string track, string normalizedText, CancellationToken cancellationToken = default) =>
            Task.CompletedTask;

        public Task SetCompletedAsync(DocumentSegmentation segmentation, CancellationToken cancellationToken = default) =>
            Task.CompletedTask;

        public Task SetFailedAsync(string documentId, string track, string normalizedText, string? errorCode, string errorMessage, CancellationToken cancellationToken = default) =>
            Task.CompletedTask;
    }

    private sealed class StubIndexingService : IIndexingService
    {
        public Task SyncDocumentAsync(string documentId) => Task.CompletedTask;
        public Task RemoveDocumentAsync(string documentId) => Task.CompletedTask;
        public Task EnsureIndexReadyAsync() => Task.CompletedTask;
        public Task ReindexAllAsync(bool recreateIndex = false) => Task.CompletedTask;
        public Task<(List<SearchDocumentIndex> Results, long Total)> SearchAsync(SearchDocumentsDto dto, SearchAccessScope scope) =>
            Task.FromResult((new List<SearchDocumentIndex>(), 0L));
    }

    private sealed class StubDocumentRepository : IDocumentRepository
    {
        public Task<Document?> GetByIdAsync(string id) => Task.FromResult<Document?>(null);
        public Task<Document> GetByHashAsync(string fileHash) => Task.FromResult<Document>(null!);
        public Task CreateAsync(Document document) => Task.CompletedTask;
        public Task<List<Document>> GetByUserAsync(string userId) => Task.FromResult(new List<Document>());
        public Task UpdateAsync(string id, Document document) => Task.CompletedTask;
        public Task UpdateStatusAsync(string id, DocumentStatus status) => Task.CompletedTask;
        public Task UpdateExtractedContentAsync(string documentId, string content, string rawOcrText, string normalizedOcrText) => Task.CompletedTask;
        public Task<bool> DeleteAsync(string id) => Task.FromResult(false);
        public Task<List<Document>> GetAllAsync() => Task.FromResult(new List<Document>());
        public Task<List<Document>> GetByIdsAsync(IReadOnlyCollection<string> ids) => Task.FromResult(new List<Document>());
        public Task AttachMetadataAsync(string documentId) => Task.CompletedTask;
        public Task UpdateMetadataFieldsAsync(string documentId, Metadata metadata) => Task.CompletedTask;
        public Task UpdateContentAsync(string documentId, string content, string rawOcrText, string normalizedOcrText, string? ocrProvider, string? ocrLanguage, int? ocrPages, string? department, string? departmentId) => Task.CompletedTask;
    }

    private sealed class StubUserRepository : IUserRepository
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

    private sealed class StubDocumentAuthorizationService : IDocumentAuthorizationService
    {
        public bool CanAddForOwner(User actor, User owner) => true;
        public bool CanView(User actor, Document document) => true;
        public bool CanEdit(User actor, Document document) => true;
        public bool CanDelete(User actor, Document document) => true;
        public SearchAccessScope BuildSearchScope(User actor) => new();
        public bool CanSubmit(User actor, Document document) => true;
        public bool CanStartReview(User actor, Document document) => true;
        public bool CanApprove(User actor, Document document) => true;
        public bool CanReject(User actor, Document document) => true;
        public bool CanPublish(User actor, Document document) => true;
        public bool CanArchive(User actor, Document document) => true;
        public bool CanTransfer(User actor, Document document, Department targetDepartment) => true;
    }
}
