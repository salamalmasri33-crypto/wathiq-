using eArchiveSystem.Application.Interfaces.Persistence;
using eArchiveSystem.Domain.Models;
using MongoDB.Driver;

namespace eArchiveSystem.Infrastructure.Persistence.Repositories
{
    public sealed class DocumentSegmentationRepository : IDocumentSegmentationRepository
    {
        internal const string CollectionName = "DocumentSegmentations";

        private readonly IDocumentSegmentationCollection _collection;
        private readonly Func<DateTime> _utcNow;

        public DocumentSegmentationRepository(IMongoDatabase database)
            : this(
                new MongoDocumentSegmentationCollection(
                    database?.GetCollection<DocumentSegmentation>(CollectionName)
                    ?? throw new ArgumentNullException(nameof(database))),
                null)
        {
        }

        internal DocumentSegmentationRepository(
            IDocumentSegmentationCollection collection,
            Func<DateTime>? utcNow)
        {
            _collection = collection ?? throw new ArgumentNullException(nameof(collection));
            _utcNow = utcNow ?? (() => DateTime.UtcNow);
        }

        public Task<DocumentSegmentation?> GetByDocumentIdAsync(
            string documentId,
            CancellationToken cancellationToken = default)
        {
            ArgumentException.ThrowIfNullOrWhiteSpace(documentId);
            return _collection.FindByDocumentIdAsync(documentId, cancellationToken);
        }

        public Task UpsertAsync(
            DocumentSegmentation segmentation,
            CancellationToken cancellationToken = default)
        {
            ArgumentNullException.ThrowIfNull(segmentation);
            ArgumentException.ThrowIfNullOrWhiteSpace(segmentation.DocumentId);
            ArgumentException.ThrowIfNullOrWhiteSpace(segmentation.Track);

            var now = EnsureUtc(_utcNow());
            var createdAt = segmentation.CreatedAt == default
                ? now
                : EnsureUtc(segmentation.CreatedAt);
            var updatedAt = segmentation.UpdatedAt == default
                ? now
                : EnsureUtc(segmentation.UpdatedAt);
            var completedAt = segmentation.Status == SegmentationStatus.Completed
                ? EnsureUtc(segmentation.CompletedAt ?? updatedAt)
                : (DateTime?)null;

            var update = Builders<DocumentSegmentation>.Update
                .Set(item => item.DocumentId, segmentation.DocumentId)
                .Set(item => item.Status, segmentation.Status)
                .Set(item => item.Provider, segmentation.Provider)
                .Set(item => item.Track, segmentation.Track)
                .Set(item => item.PipelineId, segmentation.PipelineId)
                .Set(item => item.NormalizedText, segmentation.NormalizedText)
                .Set(item => item.Sentences, segmentation.Sentences)
                .Set(item => item.ErrorCode, segmentation.ErrorCode)
                .Set(item => item.ErrorMessage, segmentation.ErrorMessage)
                .Set(item => item.UpdatedAt, updatedAt)
                .Set(item => item.CompletedAt, completedAt)
                .SetOnInsert(item => item.CreatedAt, createdAt);

            return _collection.UpdateByDocumentIdAsync(
                segmentation.DocumentId,
                update,
                isUpsert: true,
                cancellationToken);
        }

        public Task SetProcessingAsync(
            string documentId,
            string track,
            string normalizedText,
            CancellationToken cancellationToken = default)
        {
            ArgumentException.ThrowIfNullOrWhiteSpace(documentId);
            ArgumentException.ThrowIfNullOrWhiteSpace(track);
            ArgumentNullException.ThrowIfNull(normalizedText);

            var now = EnsureUtc(_utcNow());

            var update = Builders<DocumentSegmentation>.Update
                .Set(item => item.DocumentId, documentId)
                .Set(item => item.Status, SegmentationStatus.Processing)
                .Set(item => item.Provider, null)
                .Set(item => item.Track, track)
                .Set(item => item.PipelineId, null)
                .Set(item => item.NormalizedText, normalizedText)
                .Set(item => item.Sentences, null)
                .Set(item => item.ErrorCode, null)
                .Set(item => item.ErrorMessage, null)
                .Set(item => item.UpdatedAt, now)
                .Set(item => item.CompletedAt, null)
                .SetOnInsert(item => item.CreatedAt, now);

            return _collection.UpdateByDocumentIdAsync(
                documentId,
                update,
                isUpsert: true,
                cancellationToken);
        }

        public Task SetCompletedAsync(
            DocumentSegmentation segmentation,
            CancellationToken cancellationToken = default)
        {
            ArgumentNullException.ThrowIfNull(segmentation);
            ArgumentException.ThrowIfNullOrWhiteSpace(segmentation.DocumentId);
            ArgumentException.ThrowIfNullOrWhiteSpace(segmentation.Provider);
            ArgumentException.ThrowIfNullOrWhiteSpace(segmentation.Track);
            ArgumentException.ThrowIfNullOrWhiteSpace(segmentation.PipelineId);
            ArgumentNullException.ThrowIfNull(segmentation.NormalizedText);

            if (segmentation.Status != SegmentationStatus.Completed)
            {
                throw new ArgumentException(
                    "Completed persistence requires a completed segmentation record.",
                    nameof(segmentation));
            }

            var completedSource = segmentation.CompletedAt
                ?? (segmentation.UpdatedAt == default ? _utcNow() : segmentation.UpdatedAt);
            var completedAt = EnsureUtc(completedSource);

            var update = Builders<DocumentSegmentation>.Update
                .Set(item => item.DocumentId, segmentation.DocumentId)
                .Set(item => item.Status, SegmentationStatus.Completed)
                .Set(item => item.Provider, segmentation.Provider)
                .Set(item => item.Track, segmentation.Track)
                .Set(item => item.PipelineId, segmentation.PipelineId)
                .Set(item => item.NormalizedText, segmentation.NormalizedText)
                .Set(item => item.Sentences, segmentation.Sentences)
                .Set(item => item.ErrorCode, null)
                .Set(item => item.ErrorMessage, null)
                .Set(item => item.UpdatedAt, completedAt)
                .Set(item => item.CompletedAt, completedAt)
                .SetOnInsert(item => item.CreatedAt, completedAt);

            return _collection.UpdateByDocumentIdAsync(
                segmentation.DocumentId,
                update,
                isUpsert: true,
                cancellationToken);
        }

        public Task SetFailedAsync(
            string documentId,
            string track,
            string normalizedText,
            string? errorCode,
            string errorMessage,
            CancellationToken cancellationToken = default)
        {
            ArgumentException.ThrowIfNullOrWhiteSpace(documentId);
            ArgumentException.ThrowIfNullOrWhiteSpace(track);
            ArgumentNullException.ThrowIfNull(normalizedText);
            ArgumentException.ThrowIfNullOrWhiteSpace(errorMessage);

            var now = EnsureUtc(_utcNow());

            var update = Builders<DocumentSegmentation>.Update
                .Set(item => item.DocumentId, documentId)
                .Set(item => item.Status, SegmentationStatus.Failed)
                .Set(item => item.Provider, null)
                .Set(item => item.Track, track)
                .Set(item => item.PipelineId, null)
                .Set(item => item.NormalizedText, normalizedText)
                .Set(item => item.Sentences, null)
                .Set(item => item.ErrorCode, errorCode)
                .Set(item => item.ErrorMessage, errorMessage)
                .Set(item => item.UpdatedAt, now)
                .Set(item => item.CompletedAt, null)
                .SetOnInsert(item => item.CreatedAt, now);

            return _collection.UpdateByDocumentIdAsync(
                documentId,
                update,
                isUpsert: true,
                cancellationToken);
        }

        private static DateTime EnsureUtc(DateTime value)
        {
            return value.Kind switch
            {
                DateTimeKind.Utc => value,
                DateTimeKind.Local => value.ToUniversalTime(),
                _ => DateTime.SpecifyKind(value, DateTimeKind.Utc)
            };
        }
    }

    internal interface IDocumentSegmentationCollection
    {
        Task<DocumentSegmentation?> FindByDocumentIdAsync(
            string documentId,
            CancellationToken cancellationToken);

        Task UpdateByDocumentIdAsync(
            string documentId,
            UpdateDefinition<DocumentSegmentation> update,
            bool isUpsert,
            CancellationToken cancellationToken);
    }

    internal sealed class MongoDocumentSegmentationCollection : IDocumentSegmentationCollection
    {
        private readonly IMongoCollection<DocumentSegmentation> _collection;

        public MongoDocumentSegmentationCollection(IMongoCollection<DocumentSegmentation> collection)
        {
            _collection = collection ?? throw new ArgumentNullException(nameof(collection));
        }

        public async Task<DocumentSegmentation?> FindByDocumentIdAsync(
            string documentId,
            CancellationToken cancellationToken)
        {
            return await _collection
                .Find(item => item.DocumentId == documentId)
                .FirstOrDefaultAsync(cancellationToken);
        }

        public async Task UpdateByDocumentIdAsync(
            string documentId,
            UpdateDefinition<DocumentSegmentation> update,
            bool isUpsert,
            CancellationToken cancellationToken)
        {
            await _collection.UpdateOneAsync(
                item => item.DocumentId == documentId,
                update,
                new UpdateOptions { IsUpsert = isUpsert },
                cancellationToken);
        }
    }
}
