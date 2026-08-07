namespace eArchiveSystem.Application.Interfaces.Services
{
    public interface IDashboardService
    {
        Task<int> GetTotalDocumentsAsync(string requesterId);
        Task<int> GetTotalUsersAsync(string requesterId);
        Task<int> GetTodayUploadsAsync(string requesterId);
        Task<int> GetMonthlyUpdatesAsync(string requesterId);

        Task<Dictionary<string, int>> GetDocumentsByDepartmentAsync(string requesterId);
        Task<Dictionary<string, int>> GetDocumentsByTypeAsync(string requesterId);


    }
}
