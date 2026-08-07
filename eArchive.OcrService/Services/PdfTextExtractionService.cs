using System.Text;
using PdfiumViewer;

namespace eArchive.OcrService.Services
{
    public class PdfTextExtractionService : IPdfTextExtractionService
    {
        private const int MinimumTextCharacters = 20;

        public Task<PdfTextExtractionResult?> TryExtractAsync(string filePath)
        {
            if (!string.Equals(Path.GetExtension(filePath), ".pdf", StringComparison.OrdinalIgnoreCase))
                return Task.FromResult<PdfTextExtractionResult?>(null);

            using var document = PdfDocument.Load(filePath);
            var text = new StringBuilder();

            for (var page = 0; page < document.PageCount; page++)
            {
                if (page > 0)
                    text.AppendLine();

                text.Append(document.GetPdfText(page));
            }

            var extractedText = text.ToString().Trim();
            var meaningfulCharacterCount = extractedText.Count(character => !char.IsWhiteSpace(character));

            return Task.FromResult<PdfTextExtractionResult?>(
                meaningfulCharacterCount >= MinimumTextCharacters
                    ? new PdfTextExtractionResult(extractedText, document.PageCount)
                    : null);
        }
    }
}
