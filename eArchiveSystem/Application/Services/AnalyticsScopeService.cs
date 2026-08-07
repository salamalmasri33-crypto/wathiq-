using eArchiveSystem.Application.Exceptions;
using eArchiveSystem.Application.Interfaces.Persistence;
using eArchiveSystem.Application.Interfaces.Services;
using eArchiveSystem.Application.Security;
using eArchiveSystem.Domain.Models;

namespace eArchiveSystem.Application.Services
{
    public class AnalyticsScopeService : IAnalyticsScopeService
    {
        private readonly IUserRepository _users;
        private readonly IDocumentRepository _documents;
        private readonly IAuditRepository _audit;

        public AnalyticsScopeService(
            IUserRepository users,
            IDocumentRepository documents,
            IAuditRepository audit)
        {
            _users = users;
            _documents = documents;
            _audit = audit;
        }

        public async Task<User> GetActorAsync(string requesterId)
        {
            return await _users.GetByIdAsync(requesterId)
                ?? throw new NotFoundException("User not found");
        }

        public async Task<List<User>> GetScopedUsersAsync(string requesterId)
        {
            var actor = await GetActorAsync(requesterId);
            var users = await _users.GetAllAsync();

            if (ApplicationRoles.IsSystemAdmin(actor.Role))
                return users;

            if (ApplicationRoles.IsInstitutionAdmin(actor.Role))
            {
                return users
                    .Where(user => SameInstitution(actor.InstitutionId, user.InstitutionId))
                    .Where(user => !ApplicationRoles.IsSystemAdmin(user.Role))
                    .ToList();
            }

            if (ApplicationRoles.IsManager(actor.Role))
            {
                return users
                    .Where(user => SameInstitution(actor.InstitutionId, user.InstitutionId))
                    .Where(user => SameDepartment(actor.DepartmentId ?? actor.Department, user.DepartmentId ?? user.Department))
                    .Where(user => !ApplicationRoles.IsSystemAdmin(user.Role) && !ApplicationRoles.IsInstitutionAdmin(user.Role))
                    .ToList();
            }

            return users.Where(user => user.Id == actor.Id).ToList();
        }

        public async Task<List<Document>> GetScopedDocumentsAsync(string requesterId)
        {
            var actor = await GetActorAsync(requesterId);
            var documents = await _documents.GetAllAsync();

            if (ApplicationRoles.IsSystemAdmin(actor.Role))
                return documents;

            if (ApplicationRoles.IsInstitutionAdmin(actor.Role))
            {
                return documents
                    .Where(document => SameInstitution(actor.InstitutionId, document.InstitutionId))
                    .ToList();
            }

            if (ApplicationRoles.IsManager(actor.Role))
            {
                return documents
                    .Where(document => SameInstitution(actor.InstitutionId, document.InstitutionId))
                    .Where(document => SameDepartment(actor.DepartmentId ?? actor.Department, document.DepartmentId ?? document.Department))
                    .ToList();
            }

            return documents.Where(document => document.UserId == actor.Id).ToList();
        }

        public async Task<List<AuditLog>> GetScopedAuditLogsAsync(string requesterId)
        {
            var actor = await GetActorAsync(requesterId);
            var logs = await _audit.GetAllAsync();

            if (ApplicationRoles.IsSystemAdmin(actor.Role))
                return logs;

            var scopedUsers = await GetScopedUsersAsync(requesterId);
            var scopedDocuments = await GetScopedDocumentsAsync(requesterId);

            var allowedUserIds = scopedUsers
                .Select(user => user.Id)
                .Where(id => !string.IsNullOrWhiteSpace(id))
                .ToHashSet(StringComparer.OrdinalIgnoreCase);

            var allowedDocumentIds = scopedDocuments
                .Select(document => document.Id)
                .Where(id => !string.IsNullOrWhiteSpace(id))
                .ToHashSet(StringComparer.OrdinalIgnoreCase);

            return logs
                .Where(log =>
                    (!string.IsNullOrWhiteSpace(log.DocumentId) && allowedDocumentIds.Contains(log.DocumentId)) ||
                    (!string.IsNullOrWhiteSpace(log.UserId) && allowedUserIds.Contains(log.UserId)))
                .ToList();
        }

        private static bool SameInstitution(string? left, string? right)
        {
            if (string.IsNullOrWhiteSpace(left) || string.IsNullOrWhiteSpace(right))
                return false;

            return string.Equals(left.Trim(), right.Trim(), StringComparison.OrdinalIgnoreCase);
        }

        private static bool SameDepartment(string? left, string? right)
        {
            if (string.IsNullOrWhiteSpace(left) || string.IsNullOrWhiteSpace(right))
                return false;

            return string.Equals(left.Trim(), right.Trim(), StringComparison.OrdinalIgnoreCase);
        }
    }
}
