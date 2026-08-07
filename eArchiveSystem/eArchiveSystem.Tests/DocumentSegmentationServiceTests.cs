using System.Net;
using eArchiveSystem.Application.DTOs;
using eArchiveSystem.Application.Exceptions;
using eArchiveSystem.Application.Interfaces.Persistence;
using eArchiveSystem.Application.Interfaces.Services;
using eArchiveSystem.Application.Segmentation.Abstractions;
using eArchiveSystem.Application.Segmentation.Models;
using eArchiveSystem.Application.Segmentation.Services;
using eArchiveSystem.Domain.Models;
using Microsoft.Extensions.Logging.Abstractions;

namespace eArchiveSystem.Tests;

public sealed class DocumentSegmentationServiceTests
{
    [Fact]
    public async Task SegmentDocumentAsync_uses_exact_normalized_text_and_persists_completed_result()
    {
        var events = new List<string>();
        var repository = new RecordingDocumentSegmentationRepository(events);
        var document = CreateDocument(
            normalizedText: "  السطر الأول\t\n\\n [PAR]؟ ",
            content: "CLEANED CONTENT",
            rawOcrText: "RAW OCR TEXT");
        var segmenter = new RecordingSentenceSegmenter(events)
        {
            Result = CreateResult(document.Id, document.NormalizedOcrText!)
        };

        var service = CreateService(
            segmenter,
            repository,
            document,
            canView: true,
            canEdit: true);

        var result = await service.SegmentDocumentAsync(document.Id, "user-1");

        Assert.Equal(document.NormalizedOcrText, segmenter.Text);
        Assert.NotEqual(document.Content, segmenter.Text);
        Assert.NotEqual(document.RawOcrText, segmenter.Text);
        Assert.Equal(1, segmenter.CallCount);
        Assert.Equal(document.Id, result.DocumentId);
        Assert.Equal(SegmentationStatus.Completed, result.Status);
        Assert.Equal("AraSeg", result.Provider);
        Assert.Equal("PA", result.Track);
        Assert.Equal("pa-current-1", result.PipelineId);
        Assert.Equal(document.NormalizedOcrText, result.NormalizedText);
        Assert.Equal(document.NormalizedOcrText, repository.Store[document.Id].NormalizedText);
        Assert.Equal("  السطر الأول\t\n\\n [PAR]؟ ", repository.Store[document.Id].Sentences![0].Text);
        Assert.Equal(0, repository.Store[document.Id].Sentences![0].StartToken);
        Assert.Equal(5, repository.Store[document.Id].Sentences![0].EndToken);
        Assert.Equal(
            new[]
            {
                "repo:get:doc-123",
                "repo:processing:doc-123",
                "segmenter:call:doc-123",
                "repo:completed:doc-123"
            },
            events);
    }

    [Fact]
    public async Task SegmentDocumentAsync_rejects_existing_processing_state()
    {
        var repository = new RecordingDocumentSegmentationRepository(new List<string>())
        {
            Initial = new DocumentSegmentation
            {
                DocumentId = "doc-123",
                Status = SegmentationStatus.Processing,
                Track = "PA",
                NormalizedText = "text"
            }
        };

        var segmenter = new RecordingSentenceSegmenter(new List<string>());
        var service = CreateService(segmenter, repository, CreateDocument(), canView: true, canEdit: true);

        var exception = await Assert.ThrowsAsync<ConflictException>(() =>
            service.SegmentDocumentAsync("doc-123", "user-1"));

        Assert.Equal("Document segmentation is already processing", exception.Message);
        Assert.Equal(0, segmenter.CallCount);
    }

    [Fact]
    public async Task SegmentDocumentAsync_rejects_existing_completed_state()
    {
        var repository = new RecordingDocumentSegmentationRepository(new List<string>())
        {
            Initial = new DocumentSegmentation
            {
                DocumentId = "doc-123",
                Status = SegmentationStatus.Completed,
                Track = "PA",
                Provider = "AraSeg",
                PipelineId = "pa-current-1",
                NormalizedText = "text",
                Sentences = new List<DocumentSentence>()
            }
        };

        var segmenter = new RecordingSentenceSegmenter(new List<string>());
        var service = CreateService(segmenter, repository, CreateDocument(), canView: true, canEdit: true);

        var exception = await Assert.ThrowsAsync<ConflictException>(() =>
            service.SegmentDocumentAsync("doc-123", "user-1"));

        Assert.Equal("Document segmentation has already completed", exception.Message);
        Assert.Equal(0, segmenter.CallCount);
    }

    [Fact]
    public async Task SegmentDocumentAsync_rejects_failed_record_and_requires_retry_endpoint()
    {
        var repository = new RecordingDocumentSegmentationRepository(new List<string>())
        {
            Initial = new DocumentSegmentation
            {
                DocumentId = "doc-123",
                Status = SegmentationStatus.Failed,
                Track = "PA",
                NormalizedText = "text",
                ErrorCode = "MODEL_NOT_READY",
                ErrorMessage = "Segmentation service is not ready."
            }
        };

        var segmenter = new RecordingSentenceSegmenter(new List<string>());
        var service = CreateService(segmenter, repository, CreateDocument(), canView: true, canEdit: true);

        var exception = await Assert.ThrowsAsync<ConflictException>(() =>
            service.SegmentDocumentAsync("doc-123", "user-1"));

        Assert.Equal("Document segmentation previously failed. Use the retry endpoint", exception.Message);
        Assert.Equal(0, segmenter.CallCount);
    }

    [Fact]
    public async Task SegmentDocumentAsync_requires_exact_normalized_text_and_never_falls_back_to_content_or_raw()
    {
        var repository = new RecordingDocumentSegmentationRepository(new List<string>());
        var document = CreateDocument(
            normalizedText: null,
            content: "CLEANED CONTENT",
            rawOcrText: "RAW OCR TEXT");
        var segmenter = new RecordingSentenceSegmenter(new List<string>());
        var service = CreateService(segmenter, repository, document, canView: true, canEdit: true);

        var exception = await Assert.ThrowsAsync<ValidationException>(() =>
            service.SegmentDocumentAsync(document.Id, "user-1"));

        Assert.Equal("Normalized OCR text is not available for this document", exception.Message);
        Assert.Equal(0, segmenter.CallCount);
        Assert.Empty(repository.Store);
    }

    [Fact]
    public async Task SegmentDocumentAsync_persists_failed_state_with_safe_araseg_error()
    {
        var events = new List<string>();
        var repository = new RecordingDocumentSegmentationRepository(events);
        var document = CreateDocument(normalizedText: "  النص\t\n");
        var segmenter = new RecordingSentenceSegmenter(events)
        {
            Exception = new AraSegClientException(
                "Segmentation service is not ready.",
                HttpStatusCode.ServiceUnavailable,
                "MODEL_NOT_READY")
        };

        var service = CreateService(segmenter, repository, document, canView: true, canEdit: true);

        var exception = await Assert.ThrowsAsync<AraSegClientException>(() =>
            service.SegmentDocumentAsync(document.Id, "user-1"));

        Assert.Equal("MODEL_NOT_READY", exception.ErrorCode);
        Assert.Equal(
            new[]
            {
                "repo:get:doc-123",
                "repo:processing:doc-123",
                "segmenter:call:doc-123",
                "repo:failed:doc-123"
            },
            events);

        var stored = repository.Store[document.Id];
        Assert.Equal(SegmentationStatus.Failed, stored.Status);
        Assert.Equal("MODEL_NOT_READY", stored.ErrorCode);
        Assert.Equal("Segmentation service is not ready.", stored.ErrorMessage);
        Assert.Equal(document.NormalizedOcrText, stored.NormalizedText);
        Assert.Null(stored.Provider);
        Assert.Null(stored.PipelineId);
        Assert.Null(stored.Sentences);
        Assert.Null(stored.CompletedAt);
    }

    [Fact]
    public async Task SegmentDocumentAsync_persists_generic_safe_failure_without_leaking_paths()
    {
        var repository = new RecordingDocumentSegmentationRepository(new List<string>());
        var document = CreateDocument(normalizedText: "  النص\t\n");
        var segmenter = new RecordingSentenceSegmenter(new List<string>())
        {
            Exception = new InvalidOperationException(@"C:\models\pa\manifest.json")
        };

        var service = CreateService(segmenter, repository, document, canView: true, canEdit: true);

        await Assert.ThrowsAsync<InvalidOperationException>(() =>
            service.SegmentDocumentAsync(document.Id, "user-1"));

        var stored = repository.Store[document.Id];
        Assert.Equal(SegmentationStatus.Failed, stored.Status);
        Assert.Equal("SEGMENTATION_FAILED", stored.ErrorCode);
        Assert.Equal("Document segmentation failed.", stored.ErrorMessage);
        Assert.DoesNotContain("C:\\", stored.ErrorMessage, StringComparison.OrdinalIgnoreCase);
    }

    [Fact]
    public async Task SegmentDocumentAsync_preserves_cancellation_and_resets_state_to_pending()
    {
        var events = new List<string>();
        var repository = new RecordingDocumentSegmentationRepository(events);
        var document = CreateDocument(normalizedText: "  النص\t\n");
        using var cts = new CancellationTokenSource();

        var segmenter = new RecordingSentenceSegmenter(events)
        {
            OnCall = () => cts.Cancel(),
            Exception = new OperationCanceledException(cts.Token)
        };

        var service = CreateService(segmenter, repository, document, canView: true, canEdit: true);

        await Assert.ThrowsAnyAsync<OperationCanceledException>(() =>
            service.SegmentDocumentAsync(document.Id, "user-1", cts.Token));

        Assert.Equal(
            new[]
            {
                "repo:get:doc-123",
                "repo:processing:doc-123",
                "segmenter:call:doc-123",
                "repo:upsert:doc-123"
            },
            events);
        Assert.Equal(SegmentationStatus.Pending, repository.Store[document.Id].Status);
        Assert.Null(repository.Store[document.Id].ErrorCode);
        Assert.Null(repository.Store[document.Id].ErrorMessage);
        Assert.Equal(document.NormalizedOcrText, repository.Store[document.Id].NormalizedText);
        Assert.Null(repository.Store[document.Id].CompletedAt);
    }

    [Fact]
    public async Task GetSegmentationAsync_returns_existing_backend_dto_for_view_authorized_user()
    {
        var repository = new RecordingDocumentSegmentationRepository(new List<string>())
        {
            Initial = new DocumentSegmentation
            {
                DocumentId = "doc-123",
                Status = SegmentationStatus.Completed,
                Provider = "AraSeg",
                Track = "PA",
                PipelineId = "pa-current-1",
                NormalizedText = "  النص\t\n",
                Sentences = new List<DocumentSentence>
                {
                    new() { Index = 0, Text = "  النص\t\n", StartToken = 0, EndToken = 5 }
                },
                CreatedAt = new DateTime(2026, 8, 7, 13, 0, 0, DateTimeKind.Utc),
                UpdatedAt = new DateTime(2026, 8, 7, 13, 0, 0, DateTimeKind.Utc),
                CompletedAt = new DateTime(2026, 8, 7, 13, 0, 0, DateTimeKind.Utc)
            }
        };

        var service = CreateService(
            new RecordingSentenceSegmenter(new List<string>()),
            repository,
            CreateDocument(),
            canView: true,
            canEdit: true);

        var result = await service.GetSegmentationAsync("doc-123", "user-1");

        Assert.IsType<DocumentSegmentationDto>(result);
        Assert.Equal("doc-123", result.DocumentId);
        Assert.Equal("  النص\t\n", result.NormalizedText);
        Assert.Single(result.Sentences);
        Assert.Equal("  النص\t\n", result.Sentences[0].Text);
    }

    [Fact]
    public async Task GetSegmentationAsync_throws_not_found_when_segmentation_has_not_run()
    {
        var service = CreateService(
            new RecordingSentenceSegmenter(new List<string>()),
            new RecordingDocumentSegmentationRepository(new List<string>()),
            CreateDocument(),
            canView: true,
            canEdit: true);

        await Assert.ThrowsAsync<NotFoundException>(() =>
            service.GetSegmentationAsync("doc-123", "user-1"));
    }

    [Fact]
    public async Task GetSegmentationAsync_requires_view_authorization()
    {
        var service = CreateService(
            new RecordingSentenceSegmenter(new List<string>()),
            new RecordingDocumentSegmentationRepository(new List<string>()),
            CreateDocument(),
            canView: false,
            canEdit: true);

        await Assert.ThrowsAsync<UnauthorizedActionException>(() =>
            service.GetSegmentationAsync("doc-123", "user-1"));
    }

    [Fact]
    public async Task SegmentDocumentAsync_requires_edit_authorization()
    {
        var service = CreateService(
            new RecordingSentenceSegmenter(new List<string>()),
            new RecordingDocumentSegmentationRepository(new List<string>()),
            CreateDocument(),
            canView: true,
            canEdit: false);

        await Assert.ThrowsAsync<UnauthorizedActionException>(() =>
            service.SegmentDocumentAsync("doc-123", "user-1"));
    }

    [Fact]
    public async Task RetrySegmentationAsync_requires_edit_authorization()
    {
        var repository = new RecordingDocumentSegmentationRepository(new List<string>())
        {
            Initial = new DocumentSegmentation
            {
                DocumentId = "doc-123",
                Status = SegmentationStatus.Failed,
                Track = "PA",
                NormalizedText = "text"
            }
        };

        var service = CreateService(
            new RecordingSentenceSegmenter(new List<string>()),
            repository,
            CreateDocument(),
            canView: true,
            canEdit: false);

        await Assert.ThrowsAsync<UnauthorizedActionException>(() =>
            service.RetrySegmentationAsync("doc-123", "user-1"));
    }

    [Fact]
    public async Task RetrySegmentationAsync_reuses_same_processing_flow_and_completes_from_failed_state()
    {
        var events = new List<string>();
        var repository = new RecordingDocumentSegmentationRepository(events)
        {
            Initial = new DocumentSegmentation
            {
                DocumentId = "doc-123",
                Status = SegmentationStatus.Failed,
                Track = "PA",
                NormalizedText = "old text",
                ErrorCode = "MODEL_NOT_READY",
                ErrorMessage = "Segmentation service is not ready."
            }
        };
        var document = CreateDocument(normalizedText: "  إعادة المحاولة\n");
        var segmenter = new RecordingSentenceSegmenter(events)
        {
            Result = CreateResult(document.Id, document.NormalizedOcrText!)
        };

        var service = CreateService(segmenter, repository, document, canView: true, canEdit: true);

        var result = await service.RetrySegmentationAsync(document.Id, "user-1");

        Assert.Equal(SegmentationStatus.Completed, result.Status);
        Assert.Equal(
            new[]
            {
                "repo:get:doc-123",
                "repo:processing:doc-123",
                "segmenter:call:doc-123",
                "repo:completed:doc-123"
            },
            events);
        Assert.Equal(1, repository.Store.Count);
        Assert.Equal("  إعادة المحاولة\n", repository.Store[document.Id].NormalizedText);
    }

    [Fact]
    public async Task RetrySegmentationAsync_requires_existing_failed_record()
    {
        var repository = new RecordingDocumentSegmentationRepository(new List<string>())
        {
            Initial = new DocumentSegmentation
            {
                DocumentId = "doc-123",
                Status = SegmentationStatus.Completed,
                Track = "PA",
                NormalizedText = "text"
            }
        };

        var service = CreateService(
            new RecordingSentenceSegmenter(new List<string>()),
            repository,
            CreateDocument(),
            canView: true,
            canEdit: true);

        var exception = await Assert.ThrowsAsync<ConflictException>(() =>
            service.RetrySegmentationAsync("doc-123", "user-1"));

        Assert.Equal("Document segmentation has already completed", exception.Message);
    }

    [Fact]
    public async Task RetrySegmentationAsync_throws_not_found_when_record_does_not_exist()
    {
        var service = CreateService(
            new RecordingSentenceSegmenter(new List<string>()),
            new RecordingDocumentSegmentationRepository(new List<string>()),
            CreateDocument(),
            canView: true,
            canEdit: true);

        await Assert.ThrowsAsync<NotFoundException>(() =>
            service.RetrySegmentationAsync("doc-123", "user-1"));
    }

    [Fact]
    public async Task ProcessStoredDocumentAsync_uses_exact_normalized_text_and_processes_once_when_no_record_exists()
    {
        var events = new List<string>();
        var repository = new RecordingDocumentSegmentationRepository(events);
        var document = CreateDocument(
            normalizedText: "  السطر الأول\t\n\\n [PAR]؟ ",
            content: "CLEANED CONTENT",
            rawOcrText: "RAW OCR TEXT");
        var segmenter = new RecordingSentenceSegmenter(events)
        {
            Result = CreateResult(document.Id, document.NormalizedOcrText!)
        };

        var service = CreateService(segmenter, repository, document, canView: true, canEdit: true);

        await service.ProcessStoredDocumentAsync(document.Id);

        Assert.Equal(document.NormalizedOcrText, segmenter.Text);
        Assert.NotEqual(document.Content, segmenter.Text);
        Assert.NotEqual(document.RawOcrText, segmenter.Text);
        Assert.Equal(1, segmenter.CallCount);
        Assert.Equal(
            new[]
            {
                "repo:get:doc-123",
                "repo:processing:doc-123",
                "segmenter:call:doc-123",
                "repo:completed:doc-123"
            },
            events);
    }

    [Fact]
    public async Task ProcessStoredDocumentAsync_skips_when_processing_record_exists()
    {
        var repository = new RecordingDocumentSegmentationRepository(new List<string>())
        {
            Initial = new DocumentSegmentation
            {
                DocumentId = "doc-123",
                Status = SegmentationStatus.Processing,
                Track = "PA",
                NormalizedText = "text"
            }
        };

        var segmenter = new RecordingSentenceSegmenter(new List<string>());
        var service = CreateService(segmenter, repository, CreateDocument(normalizedText: "changed"), canView: true, canEdit: true);

        await service.ProcessStoredDocumentAsync("doc-123");

        Assert.Equal(0, segmenter.CallCount);
        Assert.Empty(repository.Store);
    }

    [Fact]
    public async Task ProcessStoredDocumentAsync_skips_when_completed_record_has_same_exact_source()
    {
        var repository = new RecordingDocumentSegmentationRepository(new List<string>())
        {
            Initial = new DocumentSegmentation
            {
                DocumentId = "doc-123",
                Status = SegmentationStatus.Completed,
                Track = "PA",
                Provider = "AraSeg",
                PipelineId = "pa-current-1",
                NormalizedText = "  النص\t\n",
                Sentences = new List<DocumentSentence>()
            }
        };

        var document = CreateDocument(normalizedText: "  النص\t\n");
        var segmenter = new RecordingSentenceSegmenter(new List<string>());
        var service = CreateService(segmenter, repository, document, canView: true, canEdit: true);

        await service.ProcessStoredDocumentAsync(document.Id);

        Assert.Equal(0, segmenter.CallCount);
        Assert.Empty(repository.Store);
    }

    [Fact]
    public async Task ProcessStoredDocumentAsync_skips_when_failed_record_has_same_exact_source()
    {
        var repository = new RecordingDocumentSegmentationRepository(new List<string>())
        {
            Initial = new DocumentSegmentation
            {
                DocumentId = "doc-123",
                Status = SegmentationStatus.Failed,
                Track = "PA",
                NormalizedText = "  النص\t\n",
                ErrorCode = "MODEL_NOT_READY",
                ErrorMessage = "Segmentation service is not ready."
            }
        };

        var document = CreateDocument(normalizedText: "  النص\t\n");
        var segmenter = new RecordingSentenceSegmenter(new List<string>());
        var service = CreateService(segmenter, repository, document, canView: true, canEdit: true);

        await service.ProcessStoredDocumentAsync(document.Id);

        Assert.Equal(0, segmenter.CallCount);
        Assert.Empty(repository.Store);
    }

    [Fact]
    public async Task ProcessStoredDocumentAsync_reprocesses_when_completed_record_source_changed()
    {
        var events = new List<string>();
        var repository = new RecordingDocumentSegmentationRepository(events)
        {
            Initial = new DocumentSegmentation
            {
                DocumentId = "doc-123",
                Status = SegmentationStatus.Completed,
                Track = "PA",
                Provider = "AraSeg",
                PipelineId = "old-pipeline",
                NormalizedText = "old source",
                Sentences = new List<DocumentSentence>()
            }
        };

        var document = CreateDocument(normalizedText: "new source");
        var segmenter = new RecordingSentenceSegmenter(events)
        {
            Result = CreateResult(document.Id, document.NormalizedOcrText!)
        };

        var service = CreateService(segmenter, repository, document, canView: true, canEdit: true);

        await service.ProcessStoredDocumentAsync(document.Id);

        Assert.Equal(1, segmenter.CallCount);
        Assert.Single(repository.Store);
        Assert.Equal("new source", repository.Store[document.Id].NormalizedText);
        Assert.Equal(
            new[]
            {
                "repo:get:doc-123",
                "repo:processing:doc-123",
                "segmenter:call:doc-123",
                "repo:completed:doc-123"
            },
            events);
    }

    [Fact]
    public async Task ProcessStoredDocumentAsync_reprocesses_when_failed_record_source_changed()
    {
        var events = new List<string>();
        var repository = new RecordingDocumentSegmentationRepository(events)
        {
            Initial = new DocumentSegmentation
            {
                DocumentId = "doc-123",
                Status = SegmentationStatus.Failed,
                Track = "PA",
                NormalizedText = "old source",
                ErrorCode = "MODEL_NOT_READY",
                ErrorMessage = "Segmentation service is not ready."
            }
        };

        var document = CreateDocument(normalizedText: "new source");
        var segmenter = new RecordingSentenceSegmenter(events)
        {
            Result = CreateResult(document.Id, document.NormalizedOcrText!)
        };

        var service = CreateService(segmenter, repository, document, canView: true, canEdit: true);

        await service.ProcessStoredDocumentAsync(document.Id);

        Assert.Equal(1, segmenter.CallCount);
        Assert.Single(repository.Store);
        Assert.Equal("new source", repository.Store[document.Id].NormalizedText);
        Assert.Equal(
            new[]
            {
                "repo:get:doc-123",
                "repo:processing:doc-123",
                "segmenter:call:doc-123",
                "repo:completed:doc-123"
            },
            events);
    }

    private static DocumentSegmentationService CreateService(
        RecordingSentenceSegmenter segmenter,
        RecordingDocumentSegmentationRepository repository,
        Document document,
        bool canView,
        bool canEdit,
        RecordingIndexingService? indexing = null)
    {
        return new DocumentSegmentationService(
            segmenter,
            repository,
            indexing ?? new RecordingIndexingService(),
            new StubDocumentRepository(document),
            new StubUserRepository(),
            new StubDocumentAuthorizationService(canView, canEdit),
            NullLogger<DocumentSegmentationService>.Instance);
    }

    [Fact]
    public async Task SegmentDocumentAsync_reindexes_once_after_completed_persistence()
    {
        var repository = new RecordingDocumentSegmentationRepository(new List<string>());
        var indexing = new RecordingIndexingService();
        var document = CreateDocument();
        var service = CreateService(
            new RecordingSentenceSegmenter(new List<string>())
            {
                Result = CreateResult(document.Id, document.NormalizedOcrText!)
            },
            repository,
            document,
            canView: true,
            canEdit: true,
            indexing: indexing);

        await service.SegmentDocumentAsync(document.Id, "user-1");

        Assert.Equal(1, indexing.SyncCount);
        Assert.Equal(document.Id, indexing.LastDocumentId);
        Assert.Equal(SegmentationStatus.Completed, repository.Store[document.Id].Status);
    }

    [Fact]
    public async Task SegmentDocumentAsync_keeps_completed_segmentation_when_reindexing_fails()
    {
        var repository = new RecordingDocumentSegmentationRepository(new List<string>());
        var indexing = new RecordingIndexingService { Exception = new HttpRequestException("Elasticsearch unavailable") };
        var document = CreateDocument();
        var service = CreateService(
            new RecordingSentenceSegmenter(new List<string>())
            {
                Result = CreateResult(document.Id, document.NormalizedOcrText!)
            },
            repository,
            document,
            canView: true,
            canEdit: true,
            indexing: indexing);

        var result = await service.SegmentDocumentAsync(document.Id, "user-1");

        Assert.Equal(SegmentationStatus.Completed, result.Status);
        Assert.Equal(SegmentationStatus.Completed, repository.Store[document.Id].Status);
        Assert.NotEmpty(repository.Store[document.Id].Sentences!);
        Assert.Equal(1, indexing.SyncCount);
    }

    [Fact]
    public async Task ProcessStoredDocumentAsync_completed_same_source_does_not_reindex()
    {
        var document = CreateDocument(normalizedText: "exact source");
        var repository = new RecordingDocumentSegmentationRepository(new List<string>())
        {
            Initial = new DocumentSegmentation
            {
                DocumentId = document.Id,
                Status = SegmentationStatus.Completed,
                Track = "PA",
                NormalizedText = "exact source",
                Sentences = new List<DocumentSentence>()
            }
        };
        var indexing = new RecordingIndexingService();
        var segmenter = new RecordingSentenceSegmenter(new List<string>());
        var service = CreateService(
            segmenter,
            repository,
            document,
            canView: true,
            canEdit: true,
            indexing: indexing);

        await service.ProcessStoredDocumentAsync(document.Id);

        Assert.Equal(0, segmenter.CallCount);
        Assert.Equal(0, indexing.SyncCount);
    }

    private static Document CreateDocument(
        string? normalizedText = "  النص الأصلي\t\n",
        string? content = "cleaned text",
        string? rawOcrText = "raw text")
    {
        return new Document
        {
            Id = "doc-123",
            Title = "Document",
            FilePath = "uploads/doc.pdf",
            FileName = "doc.pdf",
            ContentType = "application/pdf",
            Size = 10,
            FileHash = "hash",
            UserId = "user-1",
            InstitutionId = "institution-1",
            DepartmentId = "department-1",
            Department = "department-1",
            Status = DocumentStatus.Draft,
            CreatedAt = new DateTime(2026, 8, 7, 12, 0, 0, DateTimeKind.Utc),
            UpdatedAt = new DateTime(2026, 8, 7, 12, 0, 0, DateTimeKind.Utc),
            NormalizedOcrText = normalizedText,
            Content = content,
            RawOcrText = rawOcrText
        };
    }

    private static SegmentationResult CreateResult(string documentId, string exactText)
    {
        return new SegmentationResult
        {
            DocumentId = documentId,
            Status = "completed",
            Provider = "AraSeg",
            Track = "PA",
            PipelineId = "pa-current-1",
            NormalizedText = exactText,
            Sentences =
            [
                new SegmentedSentence
                {
                    Index = 0,
                    Text = exactText,
                    StartToken = 0,
                    EndToken = 5
                }
            ]
        };
    }

    private sealed class RecordingSentenceSegmenter : ISentenceSegmenter
    {
        private readonly List<string> _events;

        public RecordingSentenceSegmenter(List<string> events)
        {
            _events = events;
        }

        public SegmentationResult Result { get; set; } = new();
        public Exception? Exception { get; set; }
        public Action? OnCall { get; set; }
        public int CallCount { get; private set; }
        public string? DocumentId { get; private set; }
        public string? Text { get; private set; }
        public SegmentationOptions? Options { get; private set; }

        public Task<SegmentationResult> SegmentAsync(string documentId, string text, SegmentationOptions options, CancellationToken cancellationToken = default)
        {
            CallCount++;
            DocumentId = documentId;
            Text = text;
            Options = options;
            _events.Add($"segmenter:call:{documentId}");
            OnCall?.Invoke();

            if (Exception != null)
            {
                return Task.FromException<SegmentationResult>(Exception);
            }

            return Task.FromResult(Result);
        }
    }

    private sealed class RecordingIndexingService : IIndexingService
    {
        public int SyncCount { get; private set; }
        public string? LastDocumentId { get; private set; }
        public Exception? Exception { get; set; }

        public Task SyncDocumentAsync(string documentId)
        {
            SyncCount++;
            LastDocumentId = documentId;
            return Exception == null ? Task.CompletedTask : Task.FromException(Exception);
        }

        public Task RemoveDocumentAsync(string documentId) => Task.CompletedTask;
        public Task EnsureIndexReadyAsync() => Task.CompletedTask;
        public Task ReindexAllAsync(bool recreateIndex = false) => Task.CompletedTask;
        public Task<(List<SearchDocumentIndex> Results, long Total)> SearchAsync(SearchDocumentsDto dto, SearchAccessScope scope) =>
            Task.FromResult((new List<SearchDocumentIndex>(), 0L));
    }

    private sealed class RecordingDocumentSegmentationRepository : IDocumentSegmentationRepository
    {
        private readonly List<string> _events;

        public RecordingDocumentSegmentationRepository(List<string> events)
        {
            _events = events;
        }

        public DocumentSegmentation? Initial { get; set; }
        public Dictionary<string, DocumentSegmentation> Store { get; } = new(StringComparer.Ordinal);

        public Task<DocumentSegmentation?> GetByDocumentIdAsync(string documentId, CancellationToken cancellationToken = default)
        {
            _events.Add($"repo:get:{documentId}");

            if (Store.TryGetValue(documentId, out var stored))
            {
                return Task.FromResult<DocumentSegmentation?>(Clone(stored));
            }

            return Task.FromResult<DocumentSegmentation?>(Initial != null && Initial.DocumentId == documentId
                ? Clone(Initial)
                : null);
        }

        public Task UpsertAsync(DocumentSegmentation segmentation, CancellationToken cancellationToken = default)
        {
            _events.Add($"repo:upsert:{segmentation.DocumentId}");
            Store[segmentation.DocumentId] = Clone(segmentation);
            return Task.CompletedTask;
        }

        public Task SetProcessingAsync(string documentId, string track, string normalizedText, CancellationToken cancellationToken = default)
        {
            _events.Add($"repo:processing:{documentId}");

            var existing = ResolveExisting(documentId);
            Store[documentId] = new DocumentSegmentation
            {
                DocumentId = documentId,
                Status = SegmentationStatus.Processing,
                Track = track,
                NormalizedText = normalizedText,
                CreatedAt = existing?.CreatedAt ?? new DateTime(2026, 8, 7, 12, 30, 0, DateTimeKind.Utc),
                UpdatedAt = new DateTime(2026, 8, 7, 12, 31, 0, DateTimeKind.Utc),
                CompletedAt = null
            };

            return Task.CompletedTask;
        }

        public Task SetCompletedAsync(DocumentSegmentation segmentation, CancellationToken cancellationToken = default)
        {
            _events.Add($"repo:completed:{segmentation.DocumentId}");

            var existing = ResolveExisting(segmentation.DocumentId);
            var completed = Clone(segmentation);
            completed.CreatedAt = existing?.CreatedAt ?? completed.CreatedAt;
            Store[segmentation.DocumentId] = completed;
            return Task.CompletedTask;
        }

        public Task SetFailedAsync(string documentId, string track, string normalizedText, string? errorCode, string errorMessage, CancellationToken cancellationToken = default)
        {
            _events.Add($"repo:failed:{documentId}");

            var existing = ResolveExisting(documentId);
            Store[documentId] = new DocumentSegmentation
            {
                DocumentId = documentId,
                Status = SegmentationStatus.Failed,
                Track = track,
                NormalizedText = normalizedText,
                ErrorCode = errorCode,
                ErrorMessage = errorMessage,
                CreatedAt = existing?.CreatedAt ?? new DateTime(2026, 8, 7, 12, 30, 0, DateTimeKind.Utc),
                UpdatedAt = new DateTime(2026, 8, 7, 12, 32, 0, DateTimeKind.Utc),
                CompletedAt = null
            };

            return Task.CompletedTask;
        }

        private DocumentSegmentation? ResolveExisting(string documentId)
        {
            if (Store.TryGetValue(documentId, out var stored))
            {
                return stored;
            }

            return Initial != null && Initial.DocumentId == documentId
                ? Clone(Initial)
                : null;
        }

        private static DocumentSegmentation Clone(DocumentSegmentation segmentation)
        {
            return new DocumentSegmentation
            {
                Id = segmentation.Id,
                DocumentId = segmentation.DocumentId,
                Status = segmentation.Status,
                Provider = segmentation.Provider,
                Track = segmentation.Track,
                PipelineId = segmentation.PipelineId,
                NormalizedText = segmentation.NormalizedText,
                Sentences = segmentation.Sentences?.Select(sentence => new DocumentSentence
                {
                    Index = sentence.Index,
                    Text = sentence.Text,
                    StartToken = sentence.StartToken,
                    EndToken = sentence.EndToken
                }).ToList(),
                ErrorCode = segmentation.ErrorCode,
                ErrorMessage = segmentation.ErrorMessage,
                CreatedAt = segmentation.CreatedAt,
                UpdatedAt = segmentation.UpdatedAt,
                CompletedAt = segmentation.CompletedAt
            };
        }
    }

    private sealed class StubDocumentRepository : IDocumentRepository
    {
        private readonly Document _document;

        public StubDocumentRepository(Document document)
        {
            _document = document;
        }

        public Task<Document?> GetByIdAsync(string id) =>
            Task.FromResult(id == _document.Id ? _document : null);

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
        public Task<User> GetByIdAsync(string id) => Task.FromResult(new User
        {
            Id = "user-1",
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

    private sealed class StubDocumentAuthorizationService : IDocumentAuthorizationService
    {
        private readonly bool _canView;
        private readonly bool _canEdit;

        public StubDocumentAuthorizationService(bool canView, bool canEdit)
        {
            _canView = canView;
            _canEdit = canEdit;
        }

        public bool CanAddForOwner(User actor, User owner) => true;
        public bool CanView(User actor, Document document) => _canView;
        public bool CanEdit(User actor, Document document) => _canEdit;
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
