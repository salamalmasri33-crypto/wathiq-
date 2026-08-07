using eArchiveSystem.Application.DTOs;

namespace eArchiveSystem.Application.Interfaces.Services
{
    public interface IIndexingService
    {
        Task SyncDocumentAsync(string documentId);
        Task RemoveDocumentAsync(string documentId);
        Task EnsureIndexReadyAsync();
        Task ReindexAllAsync(bool recreateIndex = false);
        Task<(List<SearchDocumentIndex> Results, long Total)> SearchAsync(SearchDocumentsDto dto, SearchAccessScope scope);
    }
}
