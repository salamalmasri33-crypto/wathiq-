namespace eArchive.OcrService.Services
{
    public interface IDocumentImageResolver
    {
        Task<IReadOnlyList<string>> ResolveAsync(string filePath);
    }
}
