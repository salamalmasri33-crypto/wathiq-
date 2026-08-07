namespace eArchive.OcrService.Services
{
    public interface IPdfTextExtractionService
    {
        Task<PdfTextExtractionResult?> TryExtractAsync(string filePath);
    }

    public sealed record PdfTextExtractionResult(string Text, int Pages);
}
