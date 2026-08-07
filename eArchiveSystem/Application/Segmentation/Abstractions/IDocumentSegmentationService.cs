using System.Threading;
using System.Threading.Tasks;
using eArchiveSystem.Application.DTOs;

namespace eArchiveSystem.Application.Segmentation.Abstractions
{
    /// <summary>
    /// Application service contract for orchestrating document segmentation.
    ///
    /// This interface belongs to the Application layer because it represents a
    /// use-case oriented capability (segment a document) without exposing
    /// infrastructure details. Implementations reside in higher or lower layers
    /// depending on composition, while business logic and orchestration depend
    /// only on this abstraction.
    /// </summary>
    public interface IDocumentSegmentationService
    {
        Task<DocumentSegmentationDto> GetSegmentationAsync(
            string documentId,
            string userId,
            CancellationToken cancellationToken = default);

        Task<DocumentSegmentationDto> SegmentDocumentAsync(
            string documentId,
            string userId,
            CancellationToken cancellationToken = default);

        Task<DocumentSegmentationDto> RetrySegmentationAsync(
            string documentId,
            string userId,
            CancellationToken cancellationToken = default);

        Task ProcessStoredDocumentAsync(
            string documentId,
            CancellationToken cancellationToken = default);
    }
}
