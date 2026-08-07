using eArchiveSystem.Application.Interfaces.Persistence;
using eArchiveSystem.Application.Interfaces.Services;

namespace eArchiveSystem.Application.Services
{
    public class DashboardService : IDashboardService
    {
        private readonly IAnalyticsScopeService _scope;

        public DashboardService(IAnalyticsScopeService scope)
        {
            _scope = scope;
        }

        public async Task<int> GetTotalDocumentsAsync(string requesterId)
        {
            var docs = await _scope.GetScopedDocumentsAsync(requesterId);
            return docs.Count;
        }

        public async Task<int> GetTotalUsersAsync(string requesterId)
        {
            var users = await _scope.GetScopedUsersAsync(requesterId);
            return users.Count;
        }

        public async Task<int> GetTodayUploadsAsync(string requesterId)
        {
            var logs = await _scope.GetScopedAuditLogsAsync(requesterId);
            var today = DateTime.UtcNow.Date;

            return logs.Count(l =>
                l.Action == "AddDocument" &&
                l.Timestamp.Date == today);
        }

        public async Task<int> GetMonthlyUpdatesAsync(string requesterId)
        {
            var logs = await _scope.GetScopedAuditLogsAsync(requesterId);
            var now = DateTime.UtcNow;

            return logs.Count(l =>
                l.Action == "UpdateDocument" &&
                l.Timestamp.Month == now.Month &&
                l.Timestamp.Year == now.Year);
        }

        public async Task<Dictionary<string, int>> GetDocumentsByDepartmentAsync(string requesterId)
        {
            var docs = await _scope.GetScopedDocumentsAsync(requesterId);

            return docs
                .GroupBy(d => d.Department ?? "Unknown")
                .ToDictionary(g => g.Key, g => g.Count());
        }

        public async Task<Dictionary<string, int>> GetDocumentsByTypeAsync(string requesterId)
        {
            var docs = await _scope.GetScopedDocumentsAsync(requesterId);

            return docs
                .Where(d => d.Metadata != null)
                .GroupBy(d => d.Metadata.DocumentType ?? "Unknown")
                .ToDictionary(g => g.Key, g => g.Count());
        }
    }
}

