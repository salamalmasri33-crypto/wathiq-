
using eArchiveSystem.Application.Interfaces.Persistence;
using eArchiveSystem.Application.Interfaces.Services;
using eArchiveSystem.Domain.Models;
using MongoDB.Driver;
using eArchiveSystem.Application.DTOs;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;

namespace eArchiveSystem.Application.Services
{
    public class AuditService : IAuditService
    {
        private readonly IAuditRepository _repo;
        private readonly IUserRepository _users;
        private readonly IAnalyticsScopeService _scope;

        public AuditService(IAuditRepository repo,
            IUserRepository users,
            IAnalyticsScopeService scope)
        {
            _repo = repo;
            _users = users;
            _scope = scope;
        }

        public async Task LogAsync(
            string userId,
            string role,
            string action,
            string? documentId,
            string description)
        {
            var log = new AuditLog
            {
                Id = Guid.NewGuid().ToString(),
                Timestamp = DateTime.UtcNow,
                UserId = userId,
                UserRole = role,
                Action = action,
                DocumentId = documentId,
                Description = description
            };

            await _repo.CreateAsync(log);
        }

        public async Task<List<AuditLog>> GetAllAsync()
        {
            return await _repo.GetAllAsync();
        }

        public async Task<(List<AuditLog> Logs, long TotalCount)> GetFilteredAsync(
            string? userId,
            string? role,
            string? action,
            DateTime? from,
            DateTime? to,
            int page,
            int pageSize)
        {
            return await _repo.GetFilteredAsync(userId, role, action, from, to, page, pageSize);
        }

        public async Task<List<AuditLogDto>> GetAllWithUsersAsync(string requesterId)
        {
            var logs = await _scope.GetScopedAuditLogsAsync(requesterId);

            var userIds = logs
                .Select(l => l.UserId)
                .Where(id => !string.IsNullOrEmpty(id) && id != "SYSTEM" && MongoDB.Bson.ObjectId.TryParse(id, out _))
                .Distinct()
                .ToList();

            var users = await _users.GetByIdsAsync(userIds);
            var usersDict = users.ToDictionary(u => u.Id, u => u.Name);

            return logs.Select(l => new AuditLogDto
            {
                Id = l.Id,
                Timestamp = l.Timestamp,
                UserId = l.UserId,
                UserName = l.UserId == "SYSTEM"
                    ? "System"
                    : usersDict.ContainsKey(l.UserId)
                        ? usersDict[l.UserId]
                        : "Unknown",
                UserRole = l.UserRole,
                Action = l.Action,
                DocumentId = l.DocumentId,
                Description = l.Description
            }).ToList();
        }
    }
}





