using eArchiveSystem.Application.DTOs;
using eArchiveSystem.Domain.Models;

namespace eArchiveSystem.Application.Interfaces.Persistence
{

    public interface IAuditRepository
    {
        Task CreateAsync(AuditLog log);
        Task<List<AuditLog>> GetByDocumentIdAsync(string documentId);

        Task<(List<AuditLog> Logs, long TotalCount)> GetFilteredAsync(
            string? userId,
            string? role,
            string? action,
            DateTime? from,
            DateTime? to,
            int page,
            int pageSize);

        Task<List<AuditLog>> GetAllAsync();
        
    }
}
