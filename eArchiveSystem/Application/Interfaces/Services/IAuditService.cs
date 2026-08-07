using eArchiveSystem.Application.DTOs;
using eArchiveSystem.Domain.Models;

namespace eArchiveSystem.Application.Interfaces.Services
{
    public interface IAuditService
    {
        Task LogAsync(
            string userId,
            string role,
            string action,
            string? documentId,
            string description);

        Task<List<AuditLog>> GetAllAsync();

        Task<(List<AuditLog> Logs, long TotalCount)> GetFilteredAsync(
            string? userId,
            string? role,
            string? action,
            DateTime? from,
            DateTime? to,
            int page,
            int pageSize);


        Task<List<AuditLogDto>> GetAllWithUsersAsync(string requesterId);
    }
}
    





