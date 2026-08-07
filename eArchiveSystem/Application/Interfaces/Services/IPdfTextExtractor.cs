namespace eArchiveSystem.Application.Interfaces.Services
{
    public interface IPdfTextExtractor
    {
        Task<string> ExtractTextAsync(string filePath, CancellationToken cancellationToken = default);
    }
}
