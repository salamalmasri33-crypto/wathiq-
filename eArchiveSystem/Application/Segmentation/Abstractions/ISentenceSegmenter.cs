using System.Threading;
using System.Threading.Tasks;

namespace eArchiveSystem.Application.Segmentation.Abstractions
{
    public interface ISentenceSegmenter
    {
        Task<SegmentationResult> SegmentAsync(
            string documentId,
            string text,
            SegmentationOptions options,
            CancellationToken cancellationToken = default);
    }
}
