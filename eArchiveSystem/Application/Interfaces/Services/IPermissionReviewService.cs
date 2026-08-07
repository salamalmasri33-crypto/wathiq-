using eArchiveSystem.Application.DTOs;

namespace eArchiveSystem.Application.Interfaces.Services
{
    public interface IPermissionReviewService
    {
        Task<PermissionCoverageDto> GetCoverageAsync();
        Task<CurrentPermissionScopeDto> GetCurrentScopeAsync(string userId);
        Task<DocumentPermissionCheckDto> CheckDocumentAccessAsync(string userId, string documentId);
    }
}
