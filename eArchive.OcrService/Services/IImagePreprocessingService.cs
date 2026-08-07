namespace eArchive.OcrService.Services
{
    public interface IImagePreprocessingService
    {
        Task<IReadOnlyList<string>> PreprocessAsync(IReadOnlyList<string> imagePaths);
    }
}
