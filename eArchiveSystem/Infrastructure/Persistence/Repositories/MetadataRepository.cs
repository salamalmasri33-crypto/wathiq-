using eArchiveSystem.Application.Interfaces.Persistence;
using eArchiveSystem.Domain.Models;
using MongoDB.Driver;

namespace eArchiveSystem.Infrastructure.Persistence.Repositories
{
    public class MetadataRepository : IMetadataRepository
    {
        private readonly IMongoCollection<Metadata> _metadata;

        public MetadataRepository(IMongoDatabase database)
        {
            _metadata = database.GetCollection<Metadata>("Metadata");
        }

        
        /// Insert or Update metadata (Id = DocumentId)
        public async Task UpsertAsync(Metadata metadata)
        {
            var filter = Builders<Metadata>.Filter.Eq(m => m.Id, metadata.Id);

            await _metadata.ReplaceOneAsync(
                filter,
                metadata,
                new ReplaceOptions { IsUpsert = true }
            );
        }

       
        /// Get metadata by DocumentId
        public async Task<Metadata?> GetByDocumentIdAsync(string documentId)
        {
            return await _metadata
                .Find(m => m.Id == documentId)
                .FirstOrDefaultAsync();
        }

        /// Delete metadata by DocumentId
        public async Task<bool> DeleteByDocumentIdAsync(string documentId)
        {
            var result = await _metadata.DeleteOneAsync(m => m.Id == documentId);
            return result.DeletedCount > 0;
        }
    }
}
