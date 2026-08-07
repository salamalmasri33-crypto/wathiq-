using eArchiveSystem.Application.DTOs;
using eArchiveSystem.Application.Interfaces.Persistence;
using eArchiveSystem.Application.Interfaces.Services;
using eArchiveSystem.Application.Services;
using eArchiveSystem.Domain.Models;
using Microsoft.Extensions.Logging.Abstractions;

namespace eArchiveSystem.Tests;

public sealed class IndexingServiceSentenceTests
{
    [Fact]
    public async Task SyncDocumentAsync_indexes_completed_sentence_texts_without_changing_content_or_metadata()
    {
        var document = CreateDocument();
        var search = new RecordingSearchRepository();
        var segmentation = new StubSegmentationRepository(new DocumentSegmentation
        {
            DocumentId = document.Id,
            Status = SegmentationStatus.Completed,
            Sentences =
            [
                new DocumentSentence { Index = 0, Text = "  صدر القرار رقم 25\t\n", StartToken = 0, EndToken = 5 },
                new DocumentSentence { Index = 1, Text = "ثم تم الأرشفة.", StartToken = 6, EndToken = 9 }
            ]
        });
        var service = CreateService(document, segmentation, search);

        await service.SyncDocumentAsync(document.Id);

        var indexed = Assert.Single(search.Indexed);
        Assert.Contains("existing content", indexed.Content, StringComparison.Ordinal);
        Assert.Equal("metadata description", indexed.Description);
        Assert.Equal(
            new[] { "  صدر القرار رقم 25\t\n", "ثم تم الأرشفة." },
            indexed.SentenceTexts);
    }

    [Theory]
    [InlineData(SegmentationStatus.Pending)]
    [InlineData(SegmentationStatus.Processing)]
    [InlineData(SegmentationStatus.Failed)]
    public async Task SyncDocumentAsync_omits_noncompleted_sentence_texts(SegmentationStatus status)
    {
        var document = CreateDocument();
        var search = new RecordingSearchRepository();
        var service = CreateService(
            document,
            new StubSegmentationRepository(new DocumentSegmentation
            {
                DocumentId = document.Id,
                Status = status,
                Sentences = [new DocumentSentence { Index = 0, Text = "must not be indexed" }]
            }),
            search);

        await service.SyncDocumentAsync(document.Id);

        Assert.Empty(Assert.Single(search.Indexed).SentenceTexts);
    }

    [Fact]
    public async Task SearchAsync_uses_matching_sentence_as_mongo_fallback_snippet()
    {
        var document = CreateDocument();
        var sentence = "صدر القرار رقم 25 بتاريخ اليوم.";
        var search = new RecordingSearchRepository();
        var service = CreateService(
            document,
            new StubSegmentationRepository(new DocumentSegmentation
            {
                DocumentId = document.Id,
                Status = SegmentationStatus.Completed,
                Sentences = [new DocumentSentence { Index = 0, Text = sentence }]
            }),
            search);

        var result = await service.SearchAsync(
            new SearchDocumentsDto { Query = "قرار", Page = 1, PageSize = 10 },
            new SearchAccessScope());

        Assert.Single(result.Results);
        Assert.Equal(sentence, result.Results[0].Snippet);
    }

    private static IndexingService CreateService(
        Document document,
        IDocumentSegmentationRepository segmentations,
        RecordingSearchRepository search)
    {
        return new IndexingService(
            new StubDocumentRepository(document),
            new StubMetadataRepository(),
            new StubUserRepository(),
            segmentations,
            search,
            NullLogger<IndexingService>.Instance);
    }

    private static Document CreateDocument() => new()
    {
        Id = "doc-123",
        Title = "Document title",
        FilePath = "uploads/doc.pdf",
        FileName = "doc.pdf",
        ContentType = "application/pdf",
        Size = 1,
        FileHash = "hash",
        UserId = "user-1",
        InstitutionId = "institution-1",
        DepartmentId = "department-1",
        Department = "department-1",
        Content = "existing content",
        Status = DocumentStatus.Draft,
        CreatedAt = DateTime.UtcNow,
        UpdatedAt = DateTime.UtcNow
    };

    private sealed class StubDocumentRepository : IDocumentRepository
    {
        private readonly Document _document;

        public StubDocumentRepository(Document document) => _document = document;
        public Task<Document?> GetByIdAsync(string id) => Task.FromResult(id == _document.Id ? _document : null);
        public Task<Document> GetByHashAsync(string fileHash) => Task.FromResult<Document>(null!);
        public Task CreateAsync(Document document) => Task.CompletedTask;
        public Task<List<Document>> GetByUserAsync(string userId) => Task.FromResult(new List<Document>());
        public Task UpdateAsync(string id, Document document) => Task.CompletedTask;
        public Task UpdateStatusAsync(string id, DocumentStatus status) => Task.CompletedTask;
        public Task UpdateExtractedContentAsync(string documentId, string content, string rawOcrText, string normalizedOcrText) => Task.CompletedTask;
        public Task<bool> DeleteAsync(string id) => Task.FromResult(false);
        public Task<List<Document>> GetAllAsync() => Task.FromResult(new List<Document> { _document });
        public Task<List<Document>> GetByIdsAsync(IReadOnlyCollection<string> ids) => Task.FromResult(ids.Contains(_document.Id) ? new List<Document> { _document } : new List<Document>());
        public Task AttachMetadataAsync(string documentId) => Task.CompletedTask;
        public Task UpdateMetadataFieldsAsync(string documentId, Metadata metadata) => Task.CompletedTask;
        public Task UpdateContentAsync(string documentId, string content, string rawOcrText, string normalizedOcrText, string? ocrProvider, string? ocrLanguage, int? ocrPages, string? department, string? departmentId) => Task.CompletedTask;
    }

    private sealed class StubMetadataRepository : IMetadataRepository
    {
        public Task<Metadata?> GetByDocumentIdAsync(string documentId) => Task.FromResult<Metadata?>(new Metadata
        {
            DocumentId = documentId,
            Description = "metadata description",
            Tags = ["archive"]
        });
        public Task UpsertAsync(Metadata metadata) => Task.CompletedTask;
        public Task<bool> DeleteByDocumentIdAsync(string documentId) => Task.FromResult(false);
    }

    private sealed class StubUserRepository : IUserRepository
    {
        public Task<User> GetByIdAsync(string id) => Task.FromResult(new User { Id = id, InstitutionId = "institution-1", DepartmentId = "department-1", Department = "department-1" });
        public Task<User> GetByEmailAsync(string email) => Task.FromResult<User>(null!);
        public Task CreateAsync(User user) => Task.CompletedTask;
        public Task UpdateAsync(string id, User user) => Task.CompletedTask;
        public Task DeleteAsync(string id) => Task.CompletedTask;
        public Task<List<User>> GetAllAsync() => Task.FromResult(new List<User>());
        public Task<User> GetByResetToken(string token) => Task.FromResult<User>(null!);
        public Task<List<User>> GetByRoleAsync(string role) => Task.FromResult(new List<User>());
        public Task<List<User>> GetByIdsAsync(List<string> ids) => Task.FromResult(new List<User>());
    }

    private sealed class StubSegmentationRepository : IDocumentSegmentationRepository
    {
        private readonly DocumentSegmentation? _segmentation;
        public StubSegmentationRepository(DocumentSegmentation? segmentation) => _segmentation = segmentation;
        public Task<DocumentSegmentation?> GetByDocumentIdAsync(string documentId, CancellationToken cancellationToken = default) => Task.FromResult(_segmentation?.DocumentId == documentId ? _segmentation : null);
        public Task UpsertAsync(DocumentSegmentation segmentation, CancellationToken cancellationToken = default) => Task.CompletedTask;
        public Task SetProcessingAsync(string documentId, string track, string normalizedText, CancellationToken cancellationToken = default) => Task.CompletedTask;
        public Task SetCompletedAsync(DocumentSegmentation segmentation, CancellationToken cancellationToken = default) => Task.CompletedTask;
        public Task SetFailedAsync(string documentId, string track, string normalizedText, string? errorCode, string errorMessage, CancellationToken cancellationToken = default) => Task.CompletedTask;
    }

    private sealed class RecordingSearchRepository : IDocumentSearchRepository
    {
        public List<SearchDocumentIndex> Indexed { get; } = new();
        public Task IndexAsync(SearchDocumentIndex document) { Indexed.Add(document); return Task.CompletedTask; }
        public Task DeleteAsync(string documentId) => Task.CompletedTask;
        public Task EnsureIndexExistsAsync() => Task.CompletedTask;
        public Task RecreateIndexAsync() => Task.CompletedTask;
        public Task<(IReadOnlyList<SearchDocumentHit> Hits, long Total)> SearchAsync(SearchDocumentsDto dto, SearchAccessScope scope) => Task.FromResult(((IReadOnlyList<SearchDocumentHit>)Array.Empty<SearchDocumentHit>(), 0L));
    }
}
