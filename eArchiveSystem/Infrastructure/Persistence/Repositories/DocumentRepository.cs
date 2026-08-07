using eArchiveSystem.Application.Interfaces.Persistence;
using eArchiveSystem.Domain.Models;
using MongoDB.Driver;

namespace eArchiveSystem.Infrastructure.Persistence.Repositories
{
    public class DocumentRepository : IDocumentRepository
    {
        private readonly IMongoCollection<Document> _documents;
        private readonly IMongoCollection<Metadata> _metadata;

        public DocumentRepository(IMongoDatabase database)
        {
            _documents = database.GetCollection<Document>("Documents");
            _metadata = database.GetCollection<Metadata>("Metadata");
        }

        public async Task CreateAsync(Document document)
        {
            await _documents.InsertOneAsync(document);
        }

        public async Task<Document?> GetByIdAsync(string id)
        {
            return await _documents
                .Find(d => d.Id == id)
                .FirstOrDefaultAsync();
        }

        public async Task<Document> GetByHashAsync(string fileHash)
        {
            return await _documents
                .Find(d => d.FileHash == fileHash)
                .FirstOrDefaultAsync();
        }

        public async Task<List<Document>> GetByUserAsync(string userId)
        {
            return await _documents
                .Find(d => d.UserId == userId)
                .ToListAsync();
        }

        public async Task<List<Document>> GetAllAsync()
        {
            return await _documents
                .Find(_ => true)
                .ToListAsync();
        }

        public async Task<List<Document>> GetByIdsAsync(IReadOnlyCollection<string> ids)
        {
            if (ids == null || ids.Count == 0)
                return new List<Document>();

            return await _documents
                .Find(Builders<Document>.Filter.In(document => document.Id, ids))
                .ToListAsync();
        }

        public async Task UpdateAsync(string id, Document document)
        {
            await _documents.ReplaceOneAsync(
                d => d.Id == id,
                document
            );
        }

        public async Task UpdateStatusAsync(string documentId, DocumentStatus status)
        {
            var update = Builders<Document>.Update
                .Set(d => d.Status, status)
                .Set(d => d.UpdatedAt, DateTime.UtcNow);

            await _documents.UpdateOneAsync(
                d => d.Id == documentId,
                update
            );
        }

        public async Task UpdateExtractedContentAsync(
            string documentId,
            string content,
            string rawOcrText,
            string normalizedOcrText)
        {
            var update = Builders<Document>.Update
                .Set(d => d.Content, content)
                .Set(d => d.RawOcrText, rawOcrText)
                .Set(d => d.NormalizedOcrText, normalizedOcrText)
                .Set(d => d.OcrUpdatedAt, DateTime.UtcNow)
                .Set(d => d.Status, DocumentStatus.Draft)
                .Set(d => d.UpdatedAt, DateTime.UtcNow);

            await _documents.UpdateOneAsync(d => d.Id == documentId, update);
        }

        public async Task UpdateContentAsync(
            string documentId,
            string content,
            string rawOcrText,
            string normalizedOcrText,
            string? ocrProvider,
            string? ocrLanguage,
            int? ocrPages,
            string? department,
            string? departmentId
        )
        {
            var update = Builders<Document>.Update
                .Set(d => d.Content, content)
                .Set(d => d.RawOcrText, rawOcrText)
                .Set(d => d.NormalizedOcrText, normalizedOcrText)
                .Set(d => d.OcrProvider, ocrProvider)
                .Set(d => d.OcrLanguage, ocrLanguage)
                .Set(d => d.OcrPages, ocrPages)
                .Set(d => d.OcrUpdatedAt, DateTime.UtcNow)
                .Set(d => d.Department, department)
                .Set(d => d.DepartmentId, departmentId)
                .Set(d => d.UpdatedAt, DateTime.UtcNow);

            await _documents.UpdateOneAsync(
                d => d.Id == documentId,
                update
            );
        }

        public async Task AttachMetadataAsync(string documentId)
        {
            var metadata = await _metadata
                .Find(m => m.Id == documentId)
                .FirstOrDefaultAsync();

            if (metadata == null)
                return;

            var update = Builders<Document>.Update
                .Set(d => d.Metadata, metadata)
                .Set(d => d.UpdatedAt, DateTime.UtcNow);

            await _documents.UpdateOneAsync(
                d => d.Id == documentId,
                update
            );
        }

        public async Task UpdateMetadataFieldsAsync(
            string documentId,
            Metadata metadata
        )
        {
            var update = Builders<Document>.Update
                .Set("Metadata.Description", metadata.Description)
                .Set("Metadata.BroadGenre", metadata.BroadGenre)
                .Set("Metadata.SpecificGenre", metadata.SpecificGenre)
                .Set("Metadata.DocumentType", metadata.DocumentType)
                .Set("Metadata.Tags", metadata.Tags)
                .Set("Metadata.IssuingEntity", metadata.IssuingEntity)
                .Set("Metadata.ReferenceNumber", metadata.ReferenceNumber)
                .Set("Metadata.DocumentDate", metadata.DocumentDate)
                .Set("Metadata.Insights", metadata.Insights)
                .Set("Metadata.HasSignature", metadata.HasSignature)
                .Set("Metadata.Signatures", metadata.Signatures)
                .Set("Metadata.Headers", metadata.Headers)
                .Set("Metadata.Footers", metadata.Footers)
                .Set("Metadata.Stamps", metadata.Stamps)
                .Set("Metadata.RawExtractionJson", metadata.RawExtractionJson)
                .Set("Metadata.StructuredDataProvided", metadata.StructuredDataProvided)
                .Set("Metadata.CoreFieldsComplete", metadata.CoreFieldsComplete)
                .Set("Metadata.AdvancedMetadataComplete", metadata.AdvancedMetadataComplete)
                .Set("Metadata.LayoutAnalysisAvailable", metadata.LayoutAnalysisAvailable)
                .Set("Metadata.RequiresReview", metadata.RequiresReview)
                .Set("Metadata.ExtractionStatus", metadata.ExtractionStatus)
                .Set("Metadata.MissingFields", metadata.MissingFields)
                .Set("Metadata.Department", metadata.Department)
                .Set("Metadata.DepartmentId", metadata.DepartmentId)
                .Set("Metadata.ExpirationDate", metadata.ExpirationDate)
                .Set("Metadata.CreatedAt", metadata.CreatedAt)
                .Set("Metadata.UpdatedAt", metadata.UpdatedAt)
                .Set(d => d.UpdatedAt, DateTime.UtcNow);

            await _documents.UpdateOneAsync(
                d => d.Id == documentId,
                update
            );
        }

        public async Task<bool> DeleteAsync(string id)
        {
            var result = await _documents.DeleteOneAsync(d => d.Id == id);
            return result.DeletedCount > 0;
        }
    }
}
