using eArchiveSystem.Application.DTOs;
using eArchiveSystem.Utils;

namespace eArchiveSystem.Application.Interfaces.Services
{
    public interface IDocumentWorkflowService
    {
        Task<ServiceResult<WorkflowActionResultDto>> SubmitDocumentAsync(string userId, string documentId);
        Task<ServiceResult<WorkflowActionResultDto>> StartReviewAsync(string userId, string documentId);
        Task<ServiceResult<WorkflowActionResultDto>> ApproveDocumentAsync(string userId, string documentId, ReviewDecisionDto? decision = null);
        Task<ServiceResult<WorkflowActionResultDto>> RejectDocumentAsync(string userId, string documentId, ReviewDecisionDto decision);
        Task<ServiceResult<WorkflowActionResultDto>> PublishDocumentAsync(string userId, string documentId);
        Task<ServiceResult<WorkflowActionResultDto>> ArchiveDocumentAsync(string userId, string documentId);
        Task<ServiceResult<DocumentTransferResultDto>> TransferDocumentAsync(string userId, string documentId, TransferDocumentDto dto);
    }
}
