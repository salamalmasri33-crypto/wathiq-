namespace eArchive.OcrService.Services
{
    public interface IWorkingFilePreparationService
    {
        Task<string> PrepareAsync(string sourcePath);
    }
}
