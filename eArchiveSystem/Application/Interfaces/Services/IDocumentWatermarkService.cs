using eArchiveSystem.Domain.Models;

namespace eArchiveSystem.Application.Interfaces.Services
{
    public interface IDocumentWatermarkService
    {
        Task<(Stream FileStream, string FileName, string ContentType)> PrepareDownloadAsync(
            Document document,
            User actor,
            string sourcePath);
    }
}
