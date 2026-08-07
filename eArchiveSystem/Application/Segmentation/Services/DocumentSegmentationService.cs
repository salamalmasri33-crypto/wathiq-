using System;
using System.Threading;
using System.Threading.Tasks;
using eArchiveSystem.Application.DTOs;
using eArchiveSystem.Application.Exceptions;
using eArchiveSystem.Application.Interfaces.Persistence;
using eArchiveSystem.Application.Interfaces.Services;
using eArchiveSystem.Application.Segmentation.Abstractions;
using eArchiveSystem.Application.Segmentation.Mappers;
using eArchiveSystem.Application.Segmentation.Models;
using eArchiveSystem.Domain.Models;
using Microsoft.Extensions.Logging;

namespace eArchiveSystem.Application.Segmentation.Services
{
    public sealed class DocumentSegmentationService : IDocumentSegmentationService
    {
        private const string PaTrack = "PA";
        private static readonly SegmentationOptions PaSegmentationOptions = new()
        {
            Track = PaTrack
        };

        private readonly ISentenceSegmenter _segmenter;
        private readonly IDocumentSegmentationRepository _segmentations;
        private readonly IIndexingService _indexing;
        private readonly IDocumentRepository _documents;
        private readonly IUserRepository _users;
        private readonly IDocumentAuthorizationService _authorization;
        private readonly ILogger<DocumentSegmentationService> _logger;

        public DocumentSegmentationService(
            ISentenceSegmenter segmenter,
            IDocumentSegmentationRepository segmentations,
            IIndexingService indexing,
            IDocumentRepository documents,
            IUserRepository users,
            IDocumentAuthorizationService authorization,
            ILogger<DocumentSegmentationService> logger)
        {
            _segmenter = segmenter ?? throw new ArgumentNullException(nameof(segmenter));
            _segmentations = segmentations ?? throw new ArgumentNullException(nameof(segmentations));
            _indexing = indexing ?? throw new ArgumentNullException(nameof(indexing));
            _documents = documents ?? throw new ArgumentNullException(nameof(documents));
            _users = users ?? throw new ArgumentNullException(nameof(users));
            _authorization = authorization ?? throw new ArgumentNullException(nameof(authorization));
            _logger = logger ?? throw new ArgumentNullException(nameof(logger));
        }

        public async Task<DocumentSegmentationDto> GetSegmentationAsync(
            string documentId,
            string userId,
            CancellationToken cancellationToken = default)
        {
            var document = await LoadAuthorizedDocumentAsync(
                documentId,
                userId,
                requireEdit: false);

            var segmentation = await _segmentations.GetByDocumentIdAsync(
                document.Id,
                cancellationToken);

            if (segmentation == null)
            {
                throw new NotFoundException("Document segmentation not found");
            }

            return DocumentSegmentationMapper.ToDto(segmentation);
        }

        public async Task<DocumentSegmentationDto> SegmentDocumentAsync(
            string documentId,
            string userId,
            CancellationToken cancellationToken = default)
        {
            var document = await LoadAuthorizedDocumentAsync(
                documentId,
                userId,
                requireEdit: true);

            var current = await _segmentations.GetByDocumentIdAsync(
                document.Id,
                cancellationToken);

            if (current != null)
            {
                switch (current.Status)
                {
                    case SegmentationStatus.Processing:
                        throw new ConflictException("Document segmentation is already processing");
                    case SegmentationStatus.Completed:
                        throw new ConflictException("Document segmentation has already completed");
                    case SegmentationStatus.Failed:
                        throw new ConflictException("Document segmentation previously failed. Use the retry endpoint");
                }
            }

            var sourceText = GetExactNormalizedText(document);
            return await ExecuteSegmentationAsync(document, sourceText, cancellationToken);
        }

        public async Task<DocumentSegmentationDto> RetrySegmentationAsync(
            string documentId,
            string userId,
            CancellationToken cancellationToken = default)
        {
            var document = await LoadAuthorizedDocumentAsync(
                documentId,
                userId,
                requireEdit: true);

            var current = await _segmentations.GetByDocumentIdAsync(
                document.Id,
                cancellationToken);

            if (current == null)
            {
                throw new NotFoundException("Document segmentation not found");
            }

            if (current.Status == SegmentationStatus.Processing)
            {
                throw new ConflictException("Document segmentation is already processing");
            }

            if (current.Status == SegmentationStatus.Completed)
            {
                throw new ConflictException("Document segmentation has already completed");
            }

            if (current.Status != SegmentationStatus.Failed)
            {
                throw new ConflictException("Only failed document segmentation can be retried");
            }

            var sourceText = GetExactNormalizedText(document);
            return await ExecuteSegmentationAsync(document, sourceText, cancellationToken);
        }

        public async Task ProcessStoredDocumentAsync(
            string documentId,
            CancellationToken cancellationToken = default)
        {
            if (string.IsNullOrWhiteSpace(documentId))
            {
                throw new ValidationException("Document id is required");
            }

            var document = await _documents.GetByIdAsync(documentId);
            if (document == null)
            {
                throw new NotFoundException("Document not found");
            }

            var sourceText = GetExactNormalizedText(document);
            var current = await _segmentations.GetByDocumentIdAsync(
                document.Id,
                cancellationToken);

            if (ShouldSkipAutomaticProcessing(current, sourceText))
            {
                return;
            }

            await ExecuteSegmentationAsync(document, sourceText, cancellationToken);
        }

        private async Task<DocumentSegmentationDto> ExecuteSegmentationAsync(
            Document document,
            string sourceText,
            CancellationToken cancellationToken)
        {
            await _segmentations.SetProcessingAsync(
                document.Id,
                PaTrack,
                sourceText,
                cancellationToken);

            try
            {
                var result = await _segmenter.SegmentAsync(
                    document.Id,
                    sourceText,
                    PaSegmentationOptions,
                    cancellationToken);

                var completed = DocumentSegmentationMapper.ToCompleted(
                    result,
                    DateTime.UtcNow);

                await _segmentations.SetCompletedAsync(
                    completed,
                    cancellationToken);

                await TryReindexCompletedSegmentationAsync(document.Id);

                return DocumentSegmentationMapper.ToDto(completed);
            }
            catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
            {
                await TryResetPendingAsync(document.Id, sourceText);
                throw;
            }
            catch (Exception exception)
            {
                var (errorCode, errorMessage) = ToSafeFailure(exception);

                try
                {
                    await _segmentations.SetFailedAsync(
                        document.Id,
                        PaTrack,
                        sourceText,
                        errorCode,
                        errorMessage,
                        CancellationToken.None);
                }
                catch (Exception persistenceException)
                {
                    _logger.LogWarning(
                        persistenceException,
                        "Failed to persist segmentation failure state for document {DocumentId}",
                        document.Id);
                }

                throw;
            }
        }

        private async Task TryResetPendingAsync(string documentId, string sourceText)
        {
            try
            {
                await _segmentations.UpsertAsync(
                    new DocumentSegmentation
                    {
                        DocumentId = documentId,
                        Status = SegmentationStatus.Pending,
                        Track = PaTrack,
                        NormalizedText = sourceText,
                        Provider = null,
                        PipelineId = null,
                        Sentences = null,
                        ErrorCode = null,
                        ErrorMessage = null,
                        UpdatedAt = DateTime.UtcNow,
                        CompletedAt = null
                    },
                    CancellationToken.None);
            }
            catch (Exception persistenceException)
            {
                _logger.LogWarning(
                    persistenceException,
                    "Failed to reset segmentation to pending after cancellation for document {DocumentId}",
                    documentId);
            }
        }

        private async Task TryReindexCompletedSegmentationAsync(string documentId)
        {
            try
            {
                await _indexing.SyncDocumentAsync(documentId);
            }
            catch (Exception)
            {
                _logger.LogWarning(
                    "Document segmentation completed for {DocumentId}, but Elasticsearch reindexing failed.",
                    documentId);
            }
        }

        private async Task<Document> LoadAuthorizedDocumentAsync(
            string documentId,
            string userId,
            bool requireEdit)
        {
            if (string.IsNullOrWhiteSpace(documentId))
            {
                throw new ValidationException("Document id is required");
            }

            if (string.IsNullOrWhiteSpace(userId))
            {
                throw new ValidationException("User id is required");
            }

            var document = await _documents.GetByIdAsync(documentId);
            if (document == null)
            {
                throw new NotFoundException("Document not found");
            }

            var actor = await _users.GetByIdAsync(userId)
                ?? throw new NotFoundException("User not found");

            var allowed = requireEdit
                ? _authorization.CanEdit(actor, document)
                : _authorization.CanView(actor, document);

            if (!allowed)
            {
                throw new UnauthorizedActionException(requireEdit
                    ? "You are not allowed to start document segmentation for this document"
                    : "You are not allowed to view document segmentation for this document");
            }

            return document;
        }

        private static string GetExactNormalizedText(Document document)
        {
            var normalizedText = document.NormalizedOcrText;
            if (string.IsNullOrWhiteSpace(normalizedText))
            {
                throw new ValidationException("Normalized OCR text is not available for this document");
            }

            return normalizedText;
        }

        private static (string? ErrorCode, string ErrorMessage) ToSafeFailure(Exception exception)
        {
            return exception switch
            {
                AraSegClientException araSegException => (araSegException.ErrorCode, araSegException.Message),
                ApiException apiException => (null, apiException.Message),
                _ => ("SEGMENTATION_FAILED", "Document segmentation failed.")
            };
        }

        private static bool ShouldSkipAutomaticProcessing(
            DocumentSegmentation? current,
            string sourceText)
        {
            if (current == null)
            {
                return false;
            }

            if (current.Status == SegmentationStatus.Processing)
            {
                return true;
            }

            var hasSameSource = string.Equals(
                current.NormalizedText,
                sourceText,
                StringComparison.Ordinal);

            return hasSameSource && (current.Status == SegmentationStatus.Completed ||
                current.Status == SegmentationStatus.Failed);
        }
    }
}
