using System.Net;
using eArchiveSystem.Application.DTOs;
using eArchiveSystem.Application.Exceptions;
using eArchiveSystem.Application.Interfaces.Persistence;
using eArchiveSystem.Application.Interfaces.Security;
using eArchiveSystem.Application.Interfaces.Services;
using eArchiveSystem.Application.Segmentation.Abstractions;
using eArchiveSystem.Application.Services;
using eArchiveSystem.Domain.Models;
using Microsoft.AspNetCore.Http;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.Logging.Abstractions;

namespace eArchiveSystem.Tests;

public sealed class DocumentServiceAutomaticSegmentationTests
{
    [Fact]
    public async Task AddDocumentAsync_pdf_path_persists_exact_text_indexes_and_triggers_automatic_segmentation_once()
    {
        var events = new List<string>();
        var tempFilePath = CreateTempPdfPath();

        try
        {
            var repository = new RecordingDocumentRepository(events);
            var extractor = new RecordingPdfTextExtractor(events)
            {
                Result = "  النص الأصلي\t\n\\n [PAR]؟ "
            };
            var preprocessor = new RecordingTextPreprocessor(events)
            {
                Result = "cleaned text"
            };
            var indexing = new RecordingIndexingService(events);
            var segmentation = new RecordingDocumentSegmentationService(events);
            var ocrHandler = new RecordingOcrHandler();
            var service = CreateService(
                repository,
                extractor,
                preprocessor,
                indexing,
                segmentation,
                tempFilePath,
                ocrHandler);

            var result = await service.AddDocumentAsync(
                "user-1",
                new AddDocumentDto
                {
                    File = CreatePdfFile(),
                    EnableOcr = false
                });

            Assert.False(result.IsDuplicate);
            Assert.Equal("doc-123", repository.StoredDocument!.Id);
            Assert.Equal("cleaned text", repository.StoredDocument.Content);
            Assert.Equal("  النص الأصلي\t\n\\n [PAR]؟ ", repository.StoredDocument.RawOcrText);
            Assert.Equal("  النص الأصلي\t\n\\n [PAR]؟ ", repository.StoredDocument.NormalizedOcrText);
            Assert.Equal(DocumentStatus.Draft, repository.StoredDocument.Status);
            Assert.Equal("  النص الأصلي\t\n\\n [PAR]؟ ", preprocessor.Input);
            Assert.Equal(1, indexing.SyncCount);
            Assert.Equal(1, segmentation.CallCount);
            Assert.Equal(0, ocrHandler.RequestCount);
            Assert.Equal("doc-123", segmentation.DocumentId);
            Assert.Equal(tempFilePath, extractor.FilePath);
            Assert.True(events.IndexOf("repo:updateextracted:doc-123") < events.IndexOf("index:sync:doc-123"));
            Assert.True(events.IndexOf("index:sync:doc-123") < events.IndexOf("segmentation:process:doc-123"));
        }
        finally
        {
            DeleteIfExists(tempFilePath);
        }
    }

    [Fact]
    public async Task AddDocumentAsync_pdf_path_keeps_successful_result_when_automatic_segmentation_fails()
    {
        var events = new List<string>();
        var tempFilePath = CreateTempPdfPath();

        try
        {
            var repository = new RecordingDocumentRepository(events);
            var extractor = new RecordingPdfTextExtractor(events)
            {
                Result = "  النص الأصلي\t\n"
            };
            var preprocessor = new RecordingTextPreprocessor(events)
            {
                Result = "cleaned text"
            };
            var indexing = new RecordingIndexingService(events);
            var segmentation = new RecordingDocumentSegmentationService(events)
            {
                Exception = new AraSegClientException(
                    "Segmentation service is not ready.",
                    HttpStatusCode.ServiceUnavailable,
                    "MODEL_NOT_READY")
            };
            var service = CreateService(
                repository,
                extractor,
                preprocessor,
                indexing,
                segmentation,
                tempFilePath);

            var result = await service.AddDocumentAsync(
                "user-1",
                new AddDocumentDto
                {
                    File = CreatePdfFile(),
                    EnableOcr = false
                });

            Assert.False(result.IsDuplicate);
            Assert.Equal("cleaned text", repository.StoredDocument!.Content);
            Assert.Equal("  النص الأصلي\t\n", repository.StoredDocument.RawOcrText);
            Assert.Equal("  النص الأصلي\t\n", repository.StoredDocument.NormalizedOcrText);
            Assert.Equal(DocumentStatus.Draft, repository.StoredDocument.Status);
            Assert.Equal(1, indexing.SyncCount);
            Assert.Equal(1, segmentation.CallCount);
            Assert.True(events.Contains("repo:updateextracted:doc-123"));
            Assert.True(events.Contains("segmentation:process:doc-123"));
        }
        finally
        {
            DeleteIfExists(tempFilePath);
        }
    }

    [Theory]
    [MemberData(nameof(UnusablePdfText))]
    public async Task AddDocumentAsync_pdf_without_usable_text_layer_submits_ocr_once_without_segmentation(string? extractedText)
    {
        var events = new List<string>();
        var tempFilePath = CreateTempPdfPath();

        try
        {
            var repository = new RecordingDocumentRepository(events);
            var extractor = new RecordingPdfTextExtractor(events) { Result = extractedText };
            var preprocessor = new RecordingTextPreprocessor(events);
            var indexing = new RecordingIndexingService(events);
            var segmentation = new RecordingDocumentSegmentationService(events);
            var ocrHandler = new RecordingOcrHandler();
            var service = CreateService(
                repository,
                extractor,
                preprocessor,
                indexing,
                segmentation,
                tempFilePath,
                ocrHandler);

            var result = await service.AddDocumentAsync(
                "user-1",
                new AddDocumentDto { File = CreatePdfFile(), EnableOcr = false });

            Assert.False(result.IsDuplicate);
            Assert.Equal(1, ocrHandler.RequestCount);
            Assert.Equal("http://ocr.local/api/ocr/process", ocrHandler.RequestUri?.ToString());
            Assert.Equal(0, segmentation.CallCount);
            Assert.Equal(0, indexing.SyncCount);
            Assert.Null(repository.StoredDocument!.RawOcrText);
            Assert.Null(repository.StoredDocument.NormalizedOcrText);
            Assert.Null(repository.StoredDocument.Content);
            Assert.DoesNotContain("repo:updateextracted:doc-123", events);
        }
        finally
        {
            DeleteIfExists(tempFilePath);
        }
    }

    [Fact]
    public async Task UpdateDocumentAsync_scanned_pdf_replacement_submits_ocr_once_without_segmentation()
    {
        var events = new List<string>();
        var oldPath = CreateTempPdfPath();
        var replacementPath = CreateTempPdfPath();

        try
        {
            var repository = new RecordingDocumentRepository(events);
            repository.Seed(new Document
            {
                Id = "doc-123",
                Title = "Existing document",
                FileName = "old.pdf",
                FilePath = oldPath,
                ContentType = "application/pdf",
                Size = 4,
                FileHash = "old-hash",
                UserId = "user-1",
                InstitutionId = "institution-1",
                DepartmentId = "department-1",
                Department = "department-1",
                Status = DocumentStatus.Draft,
                CreatedAt = DateTime.UtcNow,
                UpdatedAt = DateTime.UtcNow
            });
            var indexing = new RecordingIndexingService(events);
            var segmentation = new RecordingDocumentSegmentationService(events);
            var ocrHandler = new RecordingOcrHandler();
            var service = CreateService(
                repository,
                new RecordingPdfTextExtractor(events) { Result = string.Empty },
                new RecordingTextPreprocessor(events),
                indexing,
                segmentation,
                replacementPath,
                ocrHandler);

            var result = await service.UpdateDocumentAsync(
                "doc-123",
                new UpdateDocumentDto { File = CreatePdfFile() },
                "user-1",
                "Employee");

            Assert.True(result.Success);
            Assert.Equal(1, ocrHandler.RequestCount);
            Assert.Equal(0, segmentation.CallCount);
            Assert.Equal(0, indexing.SyncCount);
            Assert.DoesNotContain("repo:updateextracted:doc-123", events);
        }
        finally
        {
            DeleteIfExists(oldPath);
            DeleteIfExists(replacementPath);
        }
    }

    public static IEnumerable<object?[]> UnusablePdfText =>
    [
        new object?[] { null },
        new object?[] { string.Empty },
        new object?[] { " \t\r\n" }
    ];

    private static DocumentService CreateService(
        RecordingDocumentRepository repository,
        RecordingPdfTextExtractor extractor,
        RecordingTextPreprocessor preprocessor,
        RecordingIndexingService indexing,
        RecordingDocumentSegmentationService segmentation,
        string savedPath,
        HttpMessageHandler? ocrHandler = null)
    {
        var configuration = new ConfigurationBuilder()
            .AddInMemoryCollection(new Dictionary<string, string?>
            {
                ["OcrService:BaseUrl"] = "http://ocr.local",
                ["App:BaseUrl"] = "http://backend.local"
            })
            .Build();

        return new DocumentService(
            repository,
            new StubFileHashCalculator(),
            new StubStorageService(savedPath),
            new StubUserRepository(),
            new StubMetadataRepository(),
            new RecordingAuditService(),
            new HttpClient(ocrHandler ?? new RecordingOcrHandler()),
            configuration,
            indexing,
            new StubDocumentAuthorizationService(),
            new StubNotificationService(),
            new StubDocumentWatermarkService(),
            extractor,
            preprocessor,
            segmentation,
            NullLogger<DocumentService>.Instance);
    }

    private static IFormFile CreatePdfFile()
    {
        var bytes = new byte[] { 1, 2, 3, 4 };
        var stream = new MemoryStream(bytes);
        return new FormFile(stream, 0, bytes.Length, "file", "doc.pdf")
        {
            Headers = new HeaderDictionary(),
            ContentType = "application/pdf"
        };
    }

    private static string CreateTempPdfPath()
    {
        var path = Path.Combine(Path.GetTempPath(), $"{Guid.NewGuid():N}.pdf");
        File.WriteAllBytes(path, new byte[] { 1, 2, 3, 4 });
        return path;
    }

    private static void DeleteIfExists(string path)
    {
        if (File.Exists(path))
        {
            File.Delete(path);
        }
    }

    private sealed class RecordingDocumentRepository : IDocumentRepository
    {
        private readonly List<string> _events;

        public RecordingDocumentRepository(List<string> events)
        {
            _events = events;
        }

        public Document? StoredDocument { get; private set; }

        public void Seed(Document document) => StoredDocument = document;

        public Task<Document?> GetByIdAsync(string id) =>
            Task.FromResult(StoredDocument != null && StoredDocument.Id == id ? StoredDocument : null);

        public Task<Document> GetByHashAsync(string fileHash) => Task.FromResult<Document>(null!);

        public Task CreateAsync(Document document)
        {
            document.Id = "doc-123";
            StoredDocument = document;
            _events.Add("repo:create:doc-123");
            return Task.CompletedTask;
        }

        public Task<List<Document>> GetByUserAsync(string userId) => Task.FromResult(new List<Document>());
        public Task UpdateAsync(string id, Document document) => Task.CompletedTask;
        public Task UpdateStatusAsync(string id, DocumentStatus status) => Task.CompletedTask;

        public Task UpdateExtractedContentAsync(string documentId, string content, string rawOcrText, string normalizedOcrText)
        {
            _events.Add($"repo:updateextracted:{documentId}");
            StoredDocument!.Content = content;
            StoredDocument.RawOcrText = rawOcrText;
            StoredDocument.NormalizedOcrText = normalizedOcrText;
            StoredDocument.Status = DocumentStatus.Draft;
            return Task.CompletedTask;
        }

        public Task<bool> DeleteAsync(string id) => Task.FromResult(false);
        public Task<List<Document>> GetAllAsync() => Task.FromResult(new List<Document>());
        public Task<List<Document>> GetByIdsAsync(IReadOnlyCollection<string> ids) => Task.FromResult(new List<Document>());
        public Task AttachMetadataAsync(string documentId) => Task.CompletedTask;
        public Task UpdateMetadataFieldsAsync(string documentId, Metadata metadata) => Task.CompletedTask;
        public Task UpdateContentAsync(string documentId, string content, string rawOcrText, string normalizedOcrText, string? ocrProvider, string? ocrLanguage, int? ocrPages, string? department, string? departmentId) => Task.CompletedTask;
    }

    private sealed class RecordingPdfTextExtractor : IPdfTextExtractor
    {
        private readonly List<string> _events;

        public RecordingPdfTextExtractor(List<string> events)
        {
            _events = events;
        }

        public string? Result { get; set; } = string.Empty;
        public string? FilePath { get; private set; }

        public Task<string> ExtractTextAsync(string filePath, CancellationToken cancellationToken = default)
        {
            _events.Add("pdf:extract");
            FilePath = filePath;
            return Task.FromResult(Result!);
        }
    }

    private sealed class RecordingOcrHandler : HttpMessageHandler
    {
        public int RequestCount { get; private set; }
        public Uri? RequestUri { get; private set; }

        protected override Task<HttpResponseMessage> SendAsync(
            HttpRequestMessage request,
            CancellationToken cancellationToken)
        {
            RequestCount++;
            RequestUri = request.RequestUri;

            return Task.FromResult(new HttpResponseMessage(HttpStatusCode.OK));
        }
    }

    private sealed class RecordingTextPreprocessor : ITextPreprocessorService
    {
        private readonly List<string> _events;

        public RecordingTextPreprocessor(List<string> events)
        {
            _events = events;
        }

        public string Result { get; set; } = string.Empty;
        public string? Input { get; private set; }

        public string Clean(string text)
        {
            _events.Add("preprocessor:clean");
            Input = text;
            return Result;
        }
    }

    private sealed class RecordingIndexingService : IIndexingService
    {
        private readonly List<string> _events;

        public RecordingIndexingService(List<string> events)
        {
            _events = events;
        }

        public int SyncCount { get; private set; }

        public Task SyncDocumentAsync(string documentId)
        {
            SyncCount++;
            _events.Add($"index:sync:{documentId}");
            return Task.CompletedTask;
        }

        public Task RemoveDocumentAsync(string documentId) => Task.CompletedTask;
        public Task EnsureIndexReadyAsync() => Task.CompletedTask;
        public Task ReindexAllAsync(bool recreateIndex = false) => Task.CompletedTask;
        public Task<(List<SearchDocumentIndex> Results, long Total)> SearchAsync(SearchDocumentsDto dto, SearchAccessScope scope) =>
            Task.FromResult((new List<SearchDocumentIndex>(), 0L));
    }

    private sealed class RecordingDocumentSegmentationService : IDocumentSegmentationService
    {
        private readonly List<string> _events;

        public RecordingDocumentSegmentationService(List<string> events)
        {
            _events = events;
        }

        public Exception? Exception { get; set; }
        public int CallCount { get; private set; }
        public string? DocumentId { get; private set; }

        public Task<DocumentSegmentationDto> GetSegmentationAsync(string documentId, string userId, CancellationToken cancellationToken = default) =>
            Task.FromResult(new DocumentSegmentationDto());

        public Task<DocumentSegmentationDto> SegmentDocumentAsync(string documentId, string userId, CancellationToken cancellationToken = default) =>
            Task.FromResult(new DocumentSegmentationDto());

        public Task<DocumentSegmentationDto> RetrySegmentationAsync(string documentId, string userId, CancellationToken cancellationToken = default) =>
            Task.FromResult(new DocumentSegmentationDto());

        public Task ProcessStoredDocumentAsync(string documentId, CancellationToken cancellationToken = default)
        {
            CallCount++;
            DocumentId = documentId;
            _events.Add($"segmentation:process:{documentId}");

            if (Exception != null)
            {
                return Task.FromException(Exception);
            }

            return Task.CompletedTask;
        }
    }

    private sealed class StubFileHashCalculator : IFileHashCalculator
    {
        public Task<string> ComputeHashAsync(IFormFile file) => Task.FromResult("hash");
    }

    private sealed class StubStorageService : IStorageService
    {
        private readonly string _savedPath;

        public StubStorageService(string savedPath)
        {
            _savedPath = savedPath;
        }

        public Task<string> SaveFileAsync(IFormFile file, string folderName) => Task.FromResult(_savedPath);
    }

    private sealed class StubUserRepository : IUserRepository
    {
        public Task<User> GetByEmailAsync(string email) => Task.FromResult<User>(null!);
        public Task CreateAsync(User user) => Task.CompletedTask;
        public Task UpdateAsync(string id, User user) => Task.CompletedTask;
        public Task DeleteAsync(string id) => Task.CompletedTask;
        public Task<List<User>> GetAllAsync() => Task.FromResult(new List<User>());
        public Task<User> GetByIdAsync(string id) => Task.FromResult(new User
        {
            Id = id,
            Name = "Test User",
            Email = "test@example.com",
            Password = "x",
            Role = "Employee",
            InstitutionId = "institution-1",
            DepartmentId = "department-1",
            Department = "department-1"
        });
        public Task<User> GetByResetToken(string token) => Task.FromResult<User>(null!);
        public Task<List<User>> GetByRoleAsync(string role) => Task.FromResult(new List<User>());
        public Task<List<User>> GetByIdsAsync(List<string> ids) => Task.FromResult(new List<User>());
    }

    private sealed class StubMetadataRepository : IMetadataRepository
    {
        public Task UpsertAsync(Metadata metadata) => Task.CompletedTask;
        public Task<Metadata?> GetByDocumentIdAsync(string documentId) => Task.FromResult<Metadata?>(null);
        public Task<bool> DeleteByDocumentIdAsync(string documentId) => Task.FromResult(false);
    }

    private sealed class RecordingAuditService : IAuditService
    {
        public Task LogAsync(string userId, string role, string action, string? documentId, string description) => Task.CompletedTask;
        public Task<List<AuditLog>> GetAllAsync() => Task.FromResult(new List<AuditLog>());
        public Task<(List<AuditLog> Logs, long TotalCount)> GetFilteredAsync(string? userId, string? role, string? action, DateTime? from, DateTime? to, int page, int pageSize) =>
            Task.FromResult((new List<AuditLog>(), 0L));
        public Task<List<AuditLogDto>> GetAllWithUsersAsync(string requesterId) => Task.FromResult(new List<AuditLogDto>());
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

    private sealed class StubNotificationService : INotificationService
    {
        public Task<NotificationsPageDto> GetMyNotificationsAsync(string userId, bool unreadOnly, int page, int pageSize) => Task.FromResult<NotificationsPageDto>(null!);
        public Task<long> GetUnreadCountAsync(string userId) => Task.FromResult(0L);
        public Task MarkAsReadAsync(string userId, string notificationId) => Task.CompletedTask;
        public Task MarkAllAsReadAsync(string userId) => Task.CompletedTask;
        public Task NotifyDocumentUpdatedAsync(Document document, User actor) => Task.CompletedTask;
        public Task NotifyDocumentApprovedAsync(Document document, User actor) => Task.CompletedTask;
        public Task NotifyDocumentRejectedAsync(Document document, User actor, string? reason) => Task.CompletedTask;
        public Task NotifyDocumentTransferredAsync(Document document, User actor, string? previousDepartmentName, Department targetDepartment, string justification) => Task.CompletedTask;
    }

    private sealed class StubDocumentWatermarkService : IDocumentWatermarkService
    {
        public Task<(Stream FileStream, string FileName, string ContentType)> PrepareDownloadAsync(Document document, User actor, string sourcePath) =>
            Task.FromResult<(Stream FileStream, string FileName, string ContentType)>((Stream.Null, "doc.pdf", "application/pdf"));
    }
}
