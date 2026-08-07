using eArchiveSystem.Application.DTOs;
using eArchiveSystem.Domain.Models;

namespace eArchiveSystem.Application.Interfaces.Services
{
    public interface INotificationService
    {
        Task<NotificationsPageDto> GetMyNotificationsAsync(string userId, bool unreadOnly, int page, int pageSize);
        Task<long> GetUnreadCountAsync(string userId);
        Task MarkAsReadAsync(string userId, string notificationId);
        Task MarkAllAsReadAsync(string userId);
        Task NotifyDocumentUpdatedAsync(Document document, User actor);
        Task NotifyDocumentApprovedAsync(Document document, User actor);
        Task NotifyDocumentRejectedAsync(Document document, User actor, string? reason);
        Task NotifyDocumentTransferredAsync(Document document, User actor, string? previousDepartmentName, Department targetDepartment, string justification);
    }
}
