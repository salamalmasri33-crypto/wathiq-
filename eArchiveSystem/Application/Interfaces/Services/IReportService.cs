using eArchiveSystem.Domain.Models;

namespace eArchiveSystem.Application.Interfaces.Services
{
    public interface IReportService
    {
        Task<Dictionary<string, int>> GetDocumentsCountByDepartmentAsync(string requesterId);
        Task<Dictionary<string, int>> GetDocumentsCountByTypeAsync(string requesterId);
        Task<List<Report>> GetUserActivityReportAsync(string requesterId);
        Task<object> GetTimeReportAsync(string requesterId);
       
        // Export - Department
        Task<byte[]> ExportDepartmentReportPdfAsync(string requesterId);
        Task<byte[]> ExportDepartmentReportExcelAsync(string requesterId);
        
        // Export - Type
        Task<byte[]> ExportTypeReportExcelAsync(string requesterId);
        Task<byte[]> ExportTypeReportPdfAsync(string requesterId);

        // Export - User Activity
        Task<byte[]> ExportUserActivityReportExcelAsync(string requesterId);
        Task<byte[]> ExportUserActivityReportPdfAsync(string requesterId);
        Task<byte[]> ExportAllDocumentsExcelAsync(string requesterId);


    }
}
