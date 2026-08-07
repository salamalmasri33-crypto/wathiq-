using eArchiveSystem.Application.DTOs;

namespace eArchiveSystem.Application.Interfaces.Services
{
    public interface IMetadataPreviewService
    {
        Task<MetadataPreviewDto> GeneratePreviewAsync(string documentId, string userId, string role, CancellationToken cancellationToken = default);
    }
}
