using eArchiveSystem.Domain.Models;

namespace eArchiveSystem.Application.Interfaces.Services
{
    public interface IAnalyticsScopeService
    {
        Task<User> GetActorAsync(string requesterId);
        Task<List<User>> GetScopedUsersAsync(string requesterId);
        Task<List<Document>> GetScopedDocumentsAsync(string requesterId);
        Task<List<AuditLog>> GetScopedAuditLogsAsync(string requesterId);
    }
}
