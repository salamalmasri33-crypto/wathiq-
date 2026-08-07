using System.Drawing;
using System.Drawing.Imaging;
using System.Runtime.Versioning;
using eArchive.OcrService.Configuration;
using Microsoft.Extensions.Options;

namespace eArchive.OcrService.Services
{
    [SupportedOSPlatform("windows")]
    public class DenoiseImagePreprocessingService : IImagePreprocessingService
    {
        private readonly ImagePreprocessingOptions _options;
        private readonly ILogger<DenoiseImagePreprocessingService> _logger;

        public DenoiseImagePreprocessingService(
            IOptions<ImagePreprocessingOptions> options,
            ILogger<DenoiseImagePreprocessingService> logger)
        {
            _options = options.Value;
            _logger = logger;
        }

        public Task<IReadOnlyList<string>> PreprocessAsync(IReadOnlyList<string> imagePaths)
        {
            var processedPaths = new List<string>(imagePaths.Count);
            var outputDirectory = Path.Combine(
                Path.GetTempPath(),
                "eArchive_OCR_Preprocessed",
                Guid.NewGuid().ToString("N"));

            Directory.CreateDirectory(outputDirectory);

            for (var index = 0; index < imagePaths.Count; index++)
            {
                var sourcePath = imagePaths[index];
                var outputPath = Path.Combine(outputDirectory, $"page_{index + 1}.png");

                using var originalBitmap = new Bitmap(sourcePath);
                using var resizedBitmap = ResizeIfNeeded(originalBitmap);
                using var grayscaleBitmap = _options.EnableGrayscale
                    ? ConvertToGrayscale(resizedBitmap)
                    : new Bitmap(resizedBitmap);
                using var contrastBitmap = _options.EnableContrastStretch
                    ? ApplyContrastStretch(grayscaleBitmap)
                    : new Bitmap(grayscaleBitmap);
                using var denoisedBitmap = _options.EnableMedianDenoise
                    ? ApplyMedianFilter(contrastBitmap)
                    : new Bitmap(contrastBitmap);

                denoisedBitmap.Save(outputPath, ImageFormat.Png);
                processedPaths.Add(outputPath);
            }

            _logger.LogInformation(
                "Preprocessed {ImageCount} image(s) for OCR",
                processedPaths.Count);

            return Task.FromResult<IReadOnlyList<string>>(processedPaths);
        }

        private Bitmap ResizeIfNeeded(Bitmap source)
        {
            if (source.Width <= _options.MaxWidth && source.Height <= _options.MaxHeight)
                return new Bitmap(source);

            var scale = Math.Min(
                (double)_options.MaxWidth / source.Width,
                (double)_options.MaxHeight / source.Height);

            var width = Math.Max(1, (int)Math.Round(source.Width * scale));
            var height = Math.Max(1, (int)Math.Round(source.Height * scale));
            var resized = new Bitmap(width, height);

            using var graphics = Graphics.FromImage(resized);
            graphics.InterpolationMode = System.Drawing.Drawing2D.InterpolationMode.HighQualityBicubic;
            graphics.DrawImage(source, 0, 0, width, height);

            return resized;
        }

        private static Bitmap ConvertToGrayscale(Bitmap source)
        {
            var grayscale = new Bitmap(source.Width, source.Height);

            for (var y = 0; y < source.Height; y++)
            {
                for (var x = 0; x < source.Width; x++)
                {
                    var pixel = source.GetPixel(x, y);
                    var luminance = (int)Math.Round((pixel.R * 0.299) + (pixel.G * 0.587) + (pixel.B * 0.114));
                    var gray = Color.FromArgb(luminance, luminance, luminance);
                    grayscale.SetPixel(x, y, gray);
                }
            }

            return grayscale;
        }

        private static Bitmap ApplyContrastStretch(Bitmap source)
        {
            byte min = 255;
            byte max = 0;

            for (var y = 0; y < source.Height; y++)
            {
                for (var x = 0; x < source.Width; x++)
                {
                    var value = source.GetPixel(x, y).R;
                    if (value < min) min = value;
                    if (value > max) max = value;
                }
            }

            if (max <= min)
                return new Bitmap(source);

            var stretched = new Bitmap(source.Width, source.Height);

            for (var y = 0; y < source.Height; y++)
            {
                for (var x = 0; x < source.Width; x++)
                {
                    var value = source.GetPixel(x, y).R;
                    var normalized = (int)Math.Round((value - min) * (255.0 / (max - min)));
                    normalized = Math.Clamp(normalized, 0, 255);
                    var color = Color.FromArgb(normalized, normalized, normalized);
                    stretched.SetPixel(x, y, color);
                }
            }

            return stretched;
        }

        private static Bitmap ApplyMedianFilter(Bitmap source)
        {
            var filtered = new Bitmap(source.Width, source.Height);

            for (var y = 0; y < source.Height; y++)
            {
                for (var x = 0; x < source.Width; x++)
                {
                    var neighbors = new List<byte>(9);

                    for (var offsetY = -1; offsetY <= 1; offsetY++)
                    {
                        for (var offsetX = -1; offsetX <= 1; offsetX++)
                        {
                            var sampleX = Math.Clamp(x + offsetX, 0, source.Width - 1);
                            var sampleY = Math.Clamp(y + offsetY, 0, source.Height - 1);
                            neighbors.Add(source.GetPixel(sampleX, sampleY).R);
                        }
                    }

                    neighbors.Sort();
                    var median = neighbors[neighbors.Count / 2];
                    filtered.SetPixel(x, y, Color.FromArgb(median, median, median));
                }
            }

            return filtered;
        }
    }
}
