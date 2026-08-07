namespace eArchive.OcrService.Services
{
    public class SafeWorkingFilePreparationService : IWorkingFilePreparationService
    {
        private readonly ILogger<SafeWorkingFilePreparationService> _logger;

        public SafeWorkingFilePreparationService(ILogger<SafeWorkingFilePreparationService> logger)
        {
            _logger = logger;
        }

        public Task<string> PrepareAsync(string sourcePath)
        {
            var normalizedPath = NormalizePath(sourcePath);

            if (!File.Exists(normalizedPath))
                throw new FileNotFoundException($"OCR source file not found: {normalizedPath}", normalizedPath);

            var extension = Path.GetExtension(normalizedPath);
            var workingDirectory = Path.Combine(
                Path.GetTempPath(),
                "eArchive_OCR_Working",
                Guid.NewGuid().ToString("N"));

            Directory.CreateDirectory(workingDirectory);

            var workingPath = Path.Combine(workingDirectory, $"source{extension}");
            File.Copy(normalizedPath, workingPath, true);

            _logger.LogInformation(
                "Prepared OCR working file at {WorkingPath} from source {SourcePath}",
                workingPath,
                normalizedPath);

            return Task.FromResult(workingPath);
        }

        private static string NormalizePath(string sourcePath)
        {
            var trimmed = sourcePath.Trim().Trim('"');
            var unescaped = Uri.UnescapeDataString(trimmed);

            return Path.IsPathRooted(unescaped)
                ? Path.GetFullPath(unescaped)
                : Path.GetFullPath(Path.Combine(Directory.GetCurrentDirectory(), unescaped));
        }
    }
}
