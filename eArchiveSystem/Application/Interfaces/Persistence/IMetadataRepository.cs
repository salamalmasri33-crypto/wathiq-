using eArchiveSystem.Domain.Models;

namespace eArchiveSystem.Application.Interfaces.Persistence
{
    public interface IMetadataRepository
    {
        // Creates or updates metadata by document id.
        Task UpsertAsync(Metadata metadata);

        // Returns metadata by document id.
        Task<Metadata?> GetByDocumentIdAsync(string documentId);

        // Deletes metadata by document id.
        Task<bool> DeleteByDocumentIdAsync(string documentId);
    }
}
