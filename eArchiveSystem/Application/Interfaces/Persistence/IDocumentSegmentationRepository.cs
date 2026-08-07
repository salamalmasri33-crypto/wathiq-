using eArchiveSystem.Domain.Models;

namespace eArchiveSystem.Application.Interfaces.Persistence
{
    public interface IDocumentSegmentationRepository
    {
        Task<DocumentSegmentation?> GetByDocumentIdAsync(
            string documentId,
            CancellationToken cancellationToken = default);

        Task UpsertAsync(
            DocumentSegmentation segmentation,
            CancellationToken cancellationToken = default);

        Task SetProcessingAsync(
            string documentId,
            string track,
            string normalizedText,
            CancellationToken cancellationToken = default);

        Task SetCompletedAsync(
            DocumentSegmentation segmentation,
            CancellationToken cancellationToken = default);

        Task SetFailedAsync(
            string documentId,
            string track,
            string normalizedText,
            string? errorCode,
            string errorMessage,
            CancellationToken cancellationToken = default);
    }
}
