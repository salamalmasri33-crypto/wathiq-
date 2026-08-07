using System.Text;
using eArchiveSystem.Application.Interfaces.Services;
using PdfiumViewer;

namespace eArchiveSystem.Infrastructure.Documents
{
    public class PdfTextExtractor : IPdfTextExtractor
    {
        public Task<string> ExtractTextAsync(string filePath, CancellationToken cancellationToken = default)
        {
            return Task.Run(() =>
            {
                using var pdf = PdfDocument.Load(filePath);
                var text = new StringBuilder();

                for (var page = 0; page < pdf.PageCount; page++)
                {
                    cancellationToken.ThrowIfCancellationRequested();
                    if (text.Length > 0)
                        text.AppendLine();
                    text.Append(pdf.GetPdfText(page));
                }

                return text.ToString();
            }, cancellationToken);
        }
    }
}
