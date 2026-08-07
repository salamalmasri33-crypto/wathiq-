using System.Threading;
using System.Threading.Tasks;

namespace eArchiveSystem.Application.Segmentation.Abstractions
{
    /// <summary>
    /// Application-layer abstraction for communicating with the external AraSeg service.
    ///
    /// This interface belongs to the Application layer because it defines a use-case
    /// oriented contract (send text and receive a <see cref="SegmentationResult"/>)
    /// without any infrastructure details. Placing the abstraction in the Application
    /// layer keeps higher-level business logic decoupled from transport concerns and
    /// enables the Infrastructure layer to provide concrete implementations that
    /// depend on framework-specific details (HTTP, authentication, retries, etc.),
    /// following the Dependency Inversion Principle and Clean Architecture.
    /// </summary>
    public interface IAraSegClient
    {
        /// <summary>
        /// Sends the specified text to the AraSeg service and returns the segmentation result.
        /// </summary>
        /// <param name="documentId">A unique identifier for the document being segmented.</param>
        /// <param name="text">The document text to send for segmentation.</param>
        /// <param name="track">The segmentation track to request from AraSeg.</param>
        /// <param name="cancellationToken">A token to cancel the operation.</param>
        /// <returns>A <see cref="SegmentationResult"/> describing the segmentation outcome.</returns>
        Task<SegmentationResult> SegmentAsync(
            string documentId,
            string text,
            string track,
            CancellationToken cancellationToken = default);
    }
}
