namespace eArchive.OcrService.Configuration
{
    public class ImagePreprocessingOptions
    {
        public bool EnableGrayscale { get; set; } = true;
        public bool EnableContrastStretch { get; set; } = true;
        public bool EnableMedianDenoise { get; set; } = true;
        public int MaxWidth { get; set; } = 1800;
        public int MaxHeight { get; set; } = 2400;
    }
}
