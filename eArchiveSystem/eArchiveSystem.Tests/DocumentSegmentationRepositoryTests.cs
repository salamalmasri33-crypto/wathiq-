using eArchiveSystem.Application.Interfaces.Persistence;
using eArchiveSystem.Domain.Models;
using eArchiveSystem.Infrastructure.Persistence.Repositories;
using Microsoft.Extensions.DependencyInjection;
using MongoDB.Bson;
using MongoDB.Bson.Serialization;
using MongoDB.Driver;

namespace eArchiveSystem.Tests;

public sealed class DocumentSegmentationRepositoryTests
{
    [Fact]
    public async Task Get_by_document_id_returns_matching_record()
    {
        var repository = CreateRepository(
            new DateTime(2026, 8, 7, 11, 0, 0, DateTimeKind.Utc),
            out var collection);

        collection.Store["doc-1"] = new DocumentSegmentation
        {
            DocumentId = "doc-1",
            Status = SegmentationStatus.Completed,
            Provider = "AraSeg",
            Track = "PA",
            PipelineId = "pa-v1",
            NormalizedText = "نص",
            Sentences = new List<DocumentSentence>(),
            CreatedAt = new DateTime(2026, 8, 7, 10, 0, 0, DateTimeKind.Utc),
            UpdatedAt = new DateTime(2026, 8, 7, 10, 0, 0, DateTimeKind.Utc),
            CompletedAt = new DateTime(2026, 8, 7, 10, 0, 0, DateTimeKind.Utc)
        };

        var result = await repository.GetByDocumentIdAsync("doc-1");

        Assert.NotNull(result);
        Assert.Equal("doc-1", result!.DocumentId);
        Assert.Equal(SegmentationStatus.Completed, result.Status);
        Assert.Single(collection.SeenCancellationTokens);
    }

    [Fact]
    public async Task Upsert_creates_single_record_and_preserves_exact_text()
    {
        var now = new DateTime(2026, 8, 7, 11, 15, 0, DateTimeKind.Utc);
        var repository = CreateRepository(now, out var collection);
        var segmentation = new DocumentSegmentation
        {
            DocumentId = "doc-upsert",
            Status = SegmentationStatus.Completed,
            Provider = "AraSeg",
            Track = "PA",
            PipelineId = "pipeline-1",
            NormalizedText = "  قبل\nبعد\t\\n [PAR]؟ ",
            Sentences = new List<DocumentSentence>
            {
                new()
                {
                    Index = 0,
                    Text = "  قبل",
                    StartToken = 0,
                    EndToken = 1
                }
            },
            ErrorCode = null,
            ErrorMessage = null,
            CreatedAt = now,
            UpdatedAt = now,
            CompletedAt = now
        };

        await repository.UpsertAsync(segmentation);

        Assert.Equal(1, collection.Store.Count);
        var stored = collection.Store["doc-upsert"];
        Assert.Equal("  قبل\nبعد\t\\n [PAR]؟ ", stored.NormalizedText);
        Assert.Equal("pipeline-1", stored.PipelineId);
        Assert.Equal("  قبل", stored.Sentences![0].Text);
        Assert.Equal(now, stored.CompletedAt);
        Assert.Equal(DateTimeKind.Utc, stored.CreatedAt.Kind);
        Assert.Equal(DateTimeKind.Utc, stored.UpdatedAt.Kind);
        Assert.Equal(DateTimeKind.Utc, stored.CompletedAt!.Value.Kind);
    }

    [Fact]
    public async Task Repeated_upsert_for_same_document_id_updates_without_creating_duplicates()
    {
        var repository = CreateRepository(
            new DateTime(2026, 8, 7, 11, 30, 0, DateTimeKind.Utc),
            out var collection);

        await repository.UpsertAsync(new DocumentSegmentation
        {
            DocumentId = "doc-repeat",
            Status = SegmentationStatus.Processing,
            Track = "PA",
            NormalizedText = "النص الأول"
        });

        await repository.UpsertAsync(new DocumentSegmentation
        {
            DocumentId = "doc-repeat",
            Status = SegmentationStatus.Completed,
            Provider = "AraSeg",
            Track = "PA",
            PipelineId = "pipeline-2",
            NormalizedText = "النص الثاني",
            Sentences = new List<DocumentSentence>
            {
                new()
                {
                    Index = 0,
                    Text = "جملة",
                    StartToken = 0,
                    EndToken = 2
                }
            }
        });

        Assert.Equal(1, collection.Store.Count);
        var stored = collection.Store["doc-repeat"];
        Assert.Equal(SegmentationStatus.Completed, stored.Status);
        Assert.Equal("pipeline-2", stored.PipelineId);
        Assert.Equal("النص الثاني", stored.NormalizedText);
        Assert.Equal("جملة", stored.Sentences![0].Text);
    }

    [Fact]
    public async Task Set_processing_clears_previous_result_and_uses_utc_timestamp()
    {
        var processingAt = new DateTime(2026, 8, 7, 11, 45, 0, DateTimeKind.Utc);
        var repository = CreateRepository(processingAt, out var collection);

        collection.Store["doc-processing"] = new DocumentSegmentation
        {
            DocumentId = "doc-processing",
            Status = SegmentationStatus.Completed,
            Provider = "AraSeg",
            Track = "PA",
            PipelineId = "old-pipeline",
            NormalizedText = "قديم",
            Sentences = new List<DocumentSentence>
            {
                new() { Index = 0, Text = "قديم", StartToken = 0, EndToken = 1 }
            },
            ErrorCode = "OLD",
            ErrorMessage = "old",
            CreatedAt = new DateTime(2026, 8, 7, 9, 0, 0, DateTimeKind.Utc),
            UpdatedAt = new DateTime(2026, 8, 7, 9, 0, 0, DateTimeKind.Utc),
            CompletedAt = new DateTime(2026, 8, 7, 9, 0, 0, DateTimeKind.Utc)
        };

        await repository.SetProcessingAsync("doc-processing", "PA", "  نص جديد\n");

        var stored = collection.Store["doc-processing"];
        Assert.Equal(SegmentationStatus.Processing, stored.Status);
        Assert.Equal("PA", stored.Track);
        Assert.Equal("  نص جديد\n", stored.NormalizedText);
        Assert.Null(stored.Provider);
        Assert.Null(stored.PipelineId);
        Assert.Null(stored.Sentences);
        Assert.Null(stored.ErrorCode);
        Assert.Null(stored.ErrorMessage);
        Assert.Null(stored.CompletedAt);
        Assert.Equal(new DateTime(2026, 8, 7, 9, 0, 0, DateTimeKind.Utc), stored.CreatedAt);
        Assert.Equal(processingAt, stored.UpdatedAt);
        Assert.Equal(DateTimeKind.Utc, stored.UpdatedAt.Kind);
    }

    [Fact]
    public async Task Set_completed_preserves_created_at_and_clears_errors()
    {
        var completedAt = new DateTime(2026, 8, 7, 12, 0, 0, DateTimeKind.Utc);
        var repository = CreateRepository(completedAt, out var collection);

        collection.Store["doc-completed"] = new DocumentSegmentation
        {
            DocumentId = "doc-completed",
            Status = SegmentationStatus.Processing,
            Track = "PA",
            NormalizedText = "  نص المصدر\t",
            ErrorCode = "STALE",
            ErrorMessage = "stale",
            CreatedAt = new DateTime(2026, 8, 7, 8, 30, 0, DateTimeKind.Utc),
            UpdatedAt = new DateTime(2026, 8, 7, 8, 30, 0, DateTimeKind.Utc)
        };

        await repository.SetCompletedAsync(new DocumentSegmentation
        {
            DocumentId = "doc-completed",
            Status = SegmentationStatus.Completed,
            Provider = "AraSeg",
            Track = "PA",
            PipelineId = "pa-final",
            NormalizedText = "  نص المصدر\t",
            Sentences = new List<DocumentSentence>
            {
                new()
                {
                    Index = 0,
                    Text = "  نص المصدر\t",
                    StartToken = 0,
                    EndToken = 3
                }
            },
            CompletedAt = completedAt
        });

        var stored = collection.Store["doc-completed"];
        Assert.Equal(SegmentationStatus.Completed, stored.Status);
        Assert.Equal("AraSeg", stored.Provider);
        Assert.Equal("pa-final", stored.PipelineId);
        Assert.Equal("  نص المصدر\t", stored.NormalizedText);
        Assert.Equal("  نص المصدر\t", stored.Sentences![0].Text);
        Assert.Null(stored.ErrorCode);
        Assert.Null(stored.ErrorMessage);
        Assert.Equal(new DateTime(2026, 8, 7, 8, 30, 0, DateTimeKind.Utc), stored.CreatedAt);
        Assert.Equal(completedAt, stored.UpdatedAt);
        Assert.Equal(completedAt, stored.CompletedAt);
    }

    [Fact]
    public async Task Set_failed_stores_safe_error_and_clears_completed_fields()
    {
        var failedAt = new DateTime(2026, 8, 7, 12, 15, 0, DateTimeKind.Utc);
        var repository = CreateRepository(failedAt, out var collection);

        collection.Store["doc-failed"] = new DocumentSegmentation
        {
            DocumentId = "doc-failed",
            Status = SegmentationStatus.Completed,
            Provider = "AraSeg",
            Track = "PA",
            PipelineId = "old-pipeline",
            NormalizedText = "قديم",
            Sentences = new List<DocumentSentence>
            {
                new() { Index = 0, Text = "قديم", StartToken = 0, EndToken = 1 }
            },
            CreatedAt = new DateTime(2026, 8, 7, 8, 0, 0, DateTimeKind.Utc),
            UpdatedAt = new DateTime(2026, 8, 7, 8, 0, 0, DateTimeKind.Utc),
            CompletedAt = new DateTime(2026, 8, 7, 8, 0, 0, DateTimeKind.Utc)
        };

        await repository.SetFailedAsync(
            "doc-failed",
            "PA",
            "  النص الآمن\n",
            "MODEL_NOT_READY",
            "Segmentation service is not ready.");

        var stored = collection.Store["doc-failed"];
        Assert.Equal(SegmentationStatus.Failed, stored.Status);
        Assert.Equal("PA", stored.Track);
        Assert.Equal("  النص الآمن\n", stored.NormalizedText);
        Assert.Equal("MODEL_NOT_READY", stored.ErrorCode);
        Assert.Equal("Segmentation service is not ready.", stored.ErrorMessage);
        Assert.Null(stored.Provider);
        Assert.Null(stored.PipelineId);
        Assert.Null(stored.Sentences);
        Assert.Null(stored.CompletedAt);
        Assert.Equal(new DateTime(2026, 8, 7, 8, 0, 0, DateTimeKind.Utc), stored.CreatedAt);
        Assert.Equal(failedAt, stored.UpdatedAt);
        Assert.DoesNotContain("C:\\", stored.ErrorMessage, StringComparison.OrdinalIgnoreCase);
    }

    [Fact]
    public async Task Repository_forwards_cancellation_tokens_to_collection_operations()
    {
        var repository = CreateRepository(
            new DateTime(2026, 8, 7, 12, 30, 0, DateTimeKind.Utc),
            out var collection);

        using var getCts = new CancellationTokenSource();
        using var upsertCts = new CancellationTokenSource();
        using var processingCts = new CancellationTokenSource();
        using var completedCts = new CancellationTokenSource();
        using var failedCts = new CancellationTokenSource();

        await repository.GetByDocumentIdAsync("doc-token-get", getCts.Token);
        await repository.UpsertAsync(new DocumentSegmentation
        {
            DocumentId = "doc-token-upsert",
            Status = SegmentationStatus.Pending,
            Track = "PA"
        }, upsertCts.Token);
        await repository.SetProcessingAsync("doc-token-processing", "PA", "text", processingCts.Token);
        await repository.SetCompletedAsync(new DocumentSegmentation
        {
            DocumentId = "doc-token-completed",
            Status = SegmentationStatus.Completed,
            Provider = "AraSeg",
            Track = "PA",
            PipelineId = "pipeline-token",
            NormalizedText = "text",
            Sentences = new List<DocumentSentence>()
        }, completedCts.Token);
        await repository.SetFailedAsync(
            "doc-token-failed",
            "PA",
            "text",
            "INVALID_INPUT",
            "Safe error.",
            failedCts.Token);

        Assert.Contains(collection.SeenCancellationTokens, token => token.Equals(getCts.Token));
        Assert.Contains(collection.SeenCancellationTokens, token => token.Equals(upsertCts.Token));
        Assert.Contains(collection.SeenCancellationTokens, token => token.Equals(processingCts.Token));
        Assert.Contains(collection.SeenCancellationTokens, token => token.Equals(completedCts.Token));
        Assert.Contains(collection.SeenCancellationTokens, token => token.Equals(failedCts.Token));
    }

    [Fact]
    public void Repository_can_be_resolved_from_dependency_injection()
    {
        var services = new ServiceCollection();
        services.AddSingleton<IMongoDatabase>(
            new MongoClient("mongodb://127.0.0.1:27017").GetDatabase("wathiq-segmentation-tests"));
        services.AddScoped<IDocumentSegmentationRepository, DocumentSegmentationRepository>();

        using var provider = services.BuildServiceProvider();
        using var scope = provider.CreateScope();

        var repository = scope.ServiceProvider.GetRequiredService<IDocumentSegmentationRepository>();

        Assert.IsType<DocumentSegmentationRepository>(repository);
        Assert.Equal("DocumentSegmentations", DocumentSegmentationRepository.CollectionName);
    }

    private static DocumentSegmentationRepository CreateRepository(
        DateTime utcNow,
        out FakeDocumentSegmentationCollection collection)
    {
        collection = new FakeDocumentSegmentationCollection();
        return new DocumentSegmentationRepository(collection, () => utcNow);
    }

    private sealed class FakeDocumentSegmentationCollection : IDocumentSegmentationCollection
    {
        private static readonly IBsonSerializer<DocumentSegmentation> Serializer =
            BsonSerializer.SerializerRegistry.GetSerializer<DocumentSegmentation>();

        public Dictionary<string, DocumentSegmentation> Store { get; } =
            new(StringComparer.Ordinal);

        public List<CancellationToken> SeenCancellationTokens { get; } = new();

        public Task<DocumentSegmentation?> FindByDocumentIdAsync(
            string documentId,
            CancellationToken cancellationToken)
        {
            SeenCancellationTokens.Add(cancellationToken);

            return Task.FromResult(
                Store.TryGetValue(documentId, out var segmentation)
                    ? Clone(segmentation)
                    : null);
        }

        public Task UpdateByDocumentIdAsync(
            string documentId,
            UpdateDefinition<DocumentSegmentation> update,
            bool isUpsert,
            CancellationToken cancellationToken)
        {
            SeenCancellationTokens.Add(cancellationToken);

            var exists = Store.TryGetValue(documentId, out var current);
            if (!exists && !isUpsert)
            {
                return Task.CompletedTask;
            }

            var working = exists
                ? Clone(current!)
                : new DocumentSegmentation { DocumentId = documentId };

            var rendered = update.Render(Serializer, BsonSerializer.SerializerRegistry);
            var bson = working.ToBsonDocument();

            ApplyOperator(rendered, bson, "$set", alwaysApply: true);
            ApplyOperator(rendered, bson, "$setOnInsert", alwaysApply: !exists);

            Store[documentId] = BsonSerializer.Deserialize<DocumentSegmentation>(bson);
            return Task.CompletedTask;
        }

        private static DocumentSegmentation Clone(DocumentSegmentation segmentation)
        {
            return BsonSerializer.Deserialize<DocumentSegmentation>(
                segmentation.ToBsonDocument());
        }

        private static void ApplyOperator(
            BsonDocument rendered,
            BsonDocument target,
            string operatorName,
            bool alwaysApply)
        {
            if (!alwaysApply || !rendered.TryGetValue(operatorName, out var operatorValue))
            {
                return;
            }

            foreach (var element in operatorValue.AsBsonDocument.Elements)
            {
                SetValue(target, element.Name, element.Value.DeepClone());
            }
        }

        private static void SetValue(BsonDocument target, string path, BsonValue value)
        {
            var segments = path.Split('.');
            var current = target;

            for (var i = 0; i < segments.Length - 1; i++)
            {
                if (!current.TryGetValue(segments[i], out var nextValue)
                    || nextValue.BsonType != BsonType.Document)
                {
                    var nextDocument = new BsonDocument();
                    current[segments[i]] = nextDocument;
                    current = nextDocument;
                }
                else
                {
                    current = nextValue.AsBsonDocument;
                }
            }

            current[segments[^1]] = value;
        }
    }
}
