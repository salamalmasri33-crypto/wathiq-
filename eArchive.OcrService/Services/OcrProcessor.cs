using eArchive.OcrService.DTOs;
using eArchive.OcrService.OCR;

namespace eArchive.OcrService.Services
{
    public class OcrProcessor
    {
        private readonly IWorkingFilePreparationService _workingFilePreparationService;
        private readonly IPdfTextExtractionService _pdfTextExtractionService;
        private readonly IDocumentImageResolver _documentImageResolver;
        private readonly IImagePreprocessingService _imagePreprocessingService;
        private readonly IOcrStrategy _ocrStrategy;
        private readonly INumericValidationService _numericValidationService;

        public OcrProcessor(
            IWorkingFilePreparationService workingFilePreparationService,
            IPdfTextExtractionService pdfTextExtractionService,
            IDocumentImageResolver documentImageResolver,
            IImagePreprocessingService imagePreprocessingService,
            IOcrStrategy ocrStrategy,
            INumericValidationService numericValidationService)
        {
            _workingFilePreparationService = workingFilePreparationService;
            _pdfTextExtractionService = pdfTextExtractionService;
            _documentImageResolver = documentImageResolver;
            _imagePreprocessingService = imagePreprocessingService;
            _ocrStrategy = ocrStrategy;
            _numericValidationService = numericValidationService;
        }

        public async Task<OcrResultDto> ProcessAsync(OcrRequestDto dto)
        {
            var temporaryPaths = new List<string>();

            try
            {
                var workingSourcePath = await _workingFilePreparationService.PrepareAsync(dto.FilePath);
                temporaryPaths.Add(workingSourcePath);

                var pdfText = await _pdfTextExtractionService.TryExtractAsync(workingSourcePath);
                if (pdfText is not null)
                {
                    var normalizedPdfText = _numericValidationService.ValidateAndNormalize(pdfText.Text);

                    return new OcrResultDto
                    {
                        Text = normalizedPdfText,
                        RawText = pdfText.Text,
                        NormalizedText = normalizedPdfText,
                        Confidence = 1,
                        Language = "ara+eng",
                        Pages = pdfText.Pages,
                        Provider = "PdfTextLayer"
                    };
                }

                var images = await _documentImageResolver.ResolveAsync(workingSourcePath);
                temporaryPaths.AddRange(images);

                var preprocessedImages = await _imagePreprocessingService.PreprocessAsync(images);
                temporaryPaths.AddRange(preprocessedImages);

                var extraction = await _ocrStrategy.ProcessAsync(preprocessedImages);
                var normalizedText = _numericValidationService.ValidateAndNormalize(extraction.RawText);

                return new OcrResultDto
                {
                    Text = normalizedText,
                    RawText = extraction.RawText,
                    NormalizedText = normalizedText,
                    Confidence = extraction.Confidence,
                    Language = extraction.Language,
                    Pages = extraction.Pages,
                    Provider = extraction.Provider
                };
            }
            finally
            {
                CleanupTemporaryDirectories(temporaryPaths);
            }
        }

        private static void CleanupTemporaryDirectories(IEnumerable<string> paths)
        {
            var tempRoot = Path.GetFullPath(Path.GetTempPath());
            var directories = paths
                .Select(path => Path.GetDirectoryName(path))
                .Where(path => !string.IsNullOrWhiteSpace(path))
                .Select(path => Path.GetFullPath(path!))
                .Where(path => path.StartsWith(tempRoot, StringComparison.OrdinalIgnoreCase))
                .Distinct(StringComparer.OrdinalIgnoreCase)
                .OrderByDescending(path => path.Length)
                .ToList();

            foreach (var directory in directories)
            {
                if (!Directory.Exists(directory))
                    continue;

                try
                {
                    Directory.Delete(directory, recursive: true);
                }
                catch
                {
                    // Best effort cleanup; OCR result should not fail because temp cleanup missed.
                }
            }
        }
    }
}
