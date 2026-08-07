using eArchive.OcrService.Domain.Models;

namespace eArchive.OcrService.OCR
{
    public interface IOcrStrategy
    {
        Task<OcrExtractionResult> ProcessAsync(IReadOnlyList<string> imagePaths);
    }

    public class OcrPageResult
    {
        public string Text { get; set; } = string.Empty;
        public float Confidence { get; set; }
    }
}
