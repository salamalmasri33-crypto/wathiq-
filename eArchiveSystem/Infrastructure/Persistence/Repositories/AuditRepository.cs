using eArchiveSystem.Application.Interfaces.Persistence;
using eArchiveSystem.Domain.Models;
using MongoDB.Driver;

namespace eArchiveSystem.Infrastructure.Persistence.Repositories
{
    public class AuditRepository : IAuditRepository
    {
        private readonly IMongoCollection<AuditLog> _collection;

        public AuditRepository(IMongoDatabase database)
        {
            _collection = database.GetCollection<AuditLog>("AuditLogs");
        }

        public async Task CreateAsync(AuditLog log)
        {
            await _collection.InsertOneAsync(log);
        }

        public async Task<List<AuditLog>> GetByDocumentIdAsync(string documentId)
        {
            return await _collection
                .Find(log => log.DocumentId == documentId)
                .SortBy(log => log.Timestamp)
                .ToListAsync();
        }

        // ----------------------------------------------
        // FILTERED + PAGINATED AUDIT LOGS
        // ----------------------------------------------
        public async Task<(List<AuditLog> Logs, long TotalCount)> GetFilteredAsync(
            string? userId,
            string? role,
            string? action,
            DateTime? from,
            DateTime? to,
            int page,
            int pageSize)
        {
            var builder = Builders<AuditLog>.Filter;
            var filters = new List<FilterDefinition<AuditLog>>();

            // Filter by UserId
            if (!string.IsNullOrEmpty(userId))
                filters.Add(builder.Eq(x => x.UserId, userId));

            // Filter by Role
            if (!string.IsNullOrEmpty(role))
                filters.Add(builder.Eq(x => x.UserRole, role));

            // Filter by Action
            if (!string.IsNullOrEmpty(action))
                filters.Add(builder.Eq(x => x.Action, action));

            // From Date
            if (from != null)
                filters.Add(builder.Gte(x => x.Timestamp, from));

            // To Date
            if (to != null)
                filters.Add(builder.Lte(x => x.Timestamp, to));

            var finalFilter = filters.Count > 0
                ? builder.And(filters)
                : builder.Empty;

            // Count for pagination
            var total = await _collection.CountDocumentsAsync(finalFilter);

            // Get logs with sorting + paging
            var logs = await _collection.Find(finalFilter)
                .SortByDescending(x => x.Timestamp)
                .Skip((page - 1) * pageSize)
                .Limit(pageSize)
                .ToListAsync();

            return (logs, total);
        }

        // (Optional fallback)
        public async Task<List<AuditLog>> GetAllAsync()
        {
            return await _collection
                .Find(_ => true)
                .SortByDescending(l => l.Timestamp)
                .ToListAsync();
        }
    }
}

