using PdfiumViewer;
using System.Drawing.Imaging;
using System.Runtime.Versioning;

namespace eArchive.OcrService.Services
{
    [SupportedOSPlatform("windows")]
    public class PdfToImageService : IPdfToImageService
    {
        private readonly ILogger<PdfToImageService> _logger;

        public PdfToImageService(ILogger<PdfToImageService> logger)
        {
            _logger = logger;
        }

        public async Task<List<string>> ConvertToImages(string pdfPath)
        {
            if (string.IsNullOrWhiteSpace(pdfPath))
                throw new ArgumentException("PDF path is empty");

            if (!File.Exists(pdfPath))
                throw new FileNotFoundException("PDF file not found", pdfPath);

            _logger.LogInformation("Converting PDF {PdfPath} to OCR image set", pdfPath);

            return await Task.Run(() =>
            {
                var images = new List<string>();

                using var pdf = PdfDocument.Load(pdfPath);

                var outputDir = Path.Combine(
                    Path.GetTempPath(),
                    "eArchive_OCR",
                    Guid.NewGuid().ToString());

                Directory.CreateDirectory(outputDir);

                for (int i = 0; i < pdf.PageCount; i++)
                {
                    using var image = pdf.Render(
                        i,
                        300,
                        300,
                        PdfRenderFlags.CorrectFromDpi);

                    var imagePath = Path.Combine(outputDir, $"page_{i + 1}.png");

                    image.Save(imagePath, ImageFormat.Png);
                    images.Add(imagePath);
                }

                _logger.LogInformation(
                    "Generated {ImageCount} page image(s) for OCR from {PdfPath}",
                    images.Count,
                    pdfPath);

                return images;
            });
        }
    }
}
