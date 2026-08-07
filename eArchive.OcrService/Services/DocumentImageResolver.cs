namespace eArchive.OcrService.Services
{
    public class DocumentImageResolver : IDocumentImageResolver
    {
        private static readonly string[] SupportedImageExtensions = [".jpg", ".jpeg", ".png"];

        private readonly IPdfToImageService _pdfToImageService;

        public DocumentImageResolver(IPdfToImageService pdfToImageService)
        {
            _pdfToImageService = pdfToImageService;
        }

        public async Task<IReadOnlyList<string>> ResolveAsync(string filePath)
        {
            var extension = Path.GetExtension(filePath).ToLowerInvariant();

            if (extension == ".pdf")
            {
                var images = await _pdfToImageService.ConvertToImages(filePath);

                if (images.Count == 0)
                    throw new InvalidOperationException("No images generated from PDF");

                return images;
            }

            if (SupportedImageExtensions.Contains(extension))
                return [filePath];

            throw new InvalidOperationException("Unsupported file type for OCR");
        }
    }
}
