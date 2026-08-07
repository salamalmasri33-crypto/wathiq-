using eArchiveSystem.Application.DTOs;

namespace eArchiveSystem.Application.Interfaces.Persistence
{
    public interface IDocumentSearchRepository
    {
        Task IndexAsync(SearchDocumentIndex document);
        Task DeleteAsync(string documentId);
        Task EnsureIndexExistsAsync();
        Task RecreateIndexAsync();
        Task<(IReadOnlyList<SearchDocumentHit> Hits, long Total)> SearchAsync(SearchDocumentsDto dto, SearchAccessScope scope);
    }
}
