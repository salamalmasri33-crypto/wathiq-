using System.Net;
using eArchiveSystem.Application.DTOs;
using eArchiveSystem.Application.Exceptions;
using eArchiveSystem.Application.Interfaces.Persistence;
using eArchiveSystem.Application.Interfaces.Services;
using eArchiveSystem.Application.Segmentation.Abstractions;
using eArchiveSystem.Domain.Models;
using eArchiveSystem.Presentation.Controllers;
using Microsoft.AspNetCore.Mvc;
using Microsoft.Extensions.Logging.Abstractions;

namespace eArchiveSystem.Tests;

public sealed class OcrCallbackControllerTests
{
    [Fact]
    public async Task ReceiveResult_persists_status_indexes_and_then_triggers_automatic_segmentation()
    {
        var events = new List<string>();
        var repository = new RecordingDocumentRepository(events);
        var preprocessor = new RecordingTextPreprocessor(events)
        {
            Result = "cleaned text"
        };
        var indexing = new RecordingIndexingService(events);
        var segmentation = new RecordingDocumentSegmentationService(events);
        var controller = new OcrCallbackController(
            repository,
            preprocessor,
            indexing,
            segmentation,
            NullLogger<OcrCallbackController>.Instance);

        var payload = new OcrCallbackDto
        {
            Text = "ignored fallback",
            RawText = "  النص الخام\t\n",
            NormalizedText = "  النص الأصلي\t\n",
            Language = "ara+eng",
            Pages = 2,
            Provider = "GroqVision"
        };

        var result = await controller.ReceiveResult("doc-123", payload);

        var ok = Assert.IsType<OkObjectResult>(result);
        Assert.Equal("OCR text stored successfully", ok.Value);
        Assert.Equal("  النص الأصلي\t\n", preprocessor.Input);
        Assert.Equal("cleaned text", repository.LastContent);
        Assert.Equal("  النص الخام\t\n", repository.LastRawText);
        Assert.Equal("  النص الأصلي\t\n", repository.LastNormalizedText);
        Assert.Equal(DocumentStatus.Draft, repository.StoredDocument.Status);
        Assert.Equal(1, segmentation.CallCount);
        Assert.Equal("doc-123", segmentation.DocumentId);
        Assert.Equal(
            new[]
            {
                "repo:get:doc-123",
                "preprocessor:clean",
                "repo:updatecontent:doc-123",
                "repo:status:doc-123",
                "index:sync:doc-123",
                "segmentation:process:doc-123"
            },
            events);
    }

    [Fact]
    public async Task ReceiveResult_keeps_successful_response_when_automatic_segmentation_fails()
    {
        var events = new List<string>();
        var repository = new RecordingDocumentRepository(events);
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
        var controller = new OcrCallbackController(
            repository,
            preprocessor,
            indexing,
            segmentation,
            NullLogger<OcrCallbackController>.Instance);

        var payload = new OcrCallbackDto
        {
            Text = "ignored fallback",
            RawText = "RAW",
            NormalizedText = "  النص الأصلي\t\n",
            Language = "ara+eng",
            Pages = 1,
            Provider = "GroqVision"
        };

        var result = await controller.ReceiveResult("doc-123", payload);

        var ok = Assert.IsType<OkObjectResult>(result);
        Assert.Equal("OCR text stored successfully", ok.Value);
        Assert.Equal("cleaned text", repository.LastContent);
        Assert.Equal("RAW", repository.LastRawText);
        Assert.Equal("  النص الأصلي\t\n", repository.LastNormalizedText);
        Assert.Equal(DocumentStatus.Draft, repository.StoredDocument.Status);
        Assert.Equal(1, indexing.SyncCount);
        Assert.Equal(1, segmentation.CallCount);
    }

    private sealed class RecordingDocumentRepository : IDocumentRepository
    {
        private readonly List<string> _events;

        public RecordingDocumentRepository(List<string> events)
        {
            _events = events;
        }

        public Document StoredDocument { get; } = new()
        {
            Id = "doc-123",
            Title = "Document",
            FilePath = "uploads/doc.png",
            FileName = "doc.png",
            ContentType = "image/png",
            Size = 10,
            FileHash = "hash",
            UserId = "user-1",
            InstitutionId = "institution-1",
            DepartmentId = "department-1",
            Department = "department-1",
            Status = DocumentStatus.Processing,
            CreatedAt = new DateTime(2026, 8, 7, 12, 0, 0, DateTimeKind.Utc),
            UpdatedAt = new DateTime(2026, 8, 7, 12, 0, 0, DateTimeKind.Utc)
        };

        public string? LastContent { get; private set; }
        public string? LastRawText { get; private set; }
        public string? LastNormalizedText { get; private set; }

        public Task<Document?> GetByIdAsync(string id)
        {
            _events.Add($"repo:get:{id}");
            return Task.FromResult(id == StoredDocument.Id ? StoredDocument : null);
        }

        public Task<Document> GetByHashAsync(string fileHash) => Task.FromResult<Document>(null!);
        public Task CreateAsync(Document document) => Task.CompletedTask;
        public Task<List<Document>> GetByUserAsync(string userId) => Task.FromResult(new List<Document>());
        public Task UpdateAsync(string id, Document document) => Task.CompletedTask;

        public Task UpdateStatusAsync(string id, DocumentStatus status)
        {
            _events.Add($"repo:status:{id}");
            StoredDocument.Status = status;
            return Task.CompletedTask;
        }

        public Task UpdateExtractedContentAsync(string documentId, string content, string rawOcrText, string normalizedOcrText) =>
            Task.CompletedTask;

        public Task<bool> DeleteAsync(string id) => Task.FromResult(false);
        public Task<List<Document>> GetAllAsync() => Task.FromResult(new List<Document>());
        public Task<List<Document>> GetByIdsAsync(IReadOnlyCollection<string> ids) => Task.FromResult(new List<Document>());
        public Task AttachMetadataAsync(string documentId) => Task.CompletedTask;
        public Task UpdateMetadataFieldsAsync(string documentId, Metadata metadata) => Task.CompletedTask;

        public Task UpdateContentAsync(string documentId, string content, string rawOcrText, string normalizedOcrText, string? ocrProvider, string? ocrLanguage, int? ocrPages, string? department, string? departmentId)
        {
            _events.Add($"repo:updatecontent:{documentId}");
            LastContent = content;
            LastRawText = rawOcrText;
            LastNormalizedText = normalizedOcrText;
            StoredDocument.Content = content;
            StoredDocument.RawOcrText = rawOcrText;
            StoredDocument.NormalizedOcrText = normalizedOcrText;
            StoredDocument.OcrProvider = ocrProvider;
            StoredDocument.OcrLanguage = ocrLanguage;
            StoredDocument.OcrPages = ocrPages;
            StoredDocument.Department = department;
            StoredDocument.DepartmentId = departmentId;
            return Task.CompletedTask;
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
}
