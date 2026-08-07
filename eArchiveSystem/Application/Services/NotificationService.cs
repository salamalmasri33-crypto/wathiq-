using eArchiveSystem.Application.DTOs;
using eArchiveSystem.Application.Exceptions;
using eArchiveSystem.Application.Interfaces.Persistence;
using eArchiveSystem.Application.Interfaces.Services;
using eArchiveSystem.Application.Security;
using eArchiveSystem.Domain.Models;

namespace eArchiveSystem.Application.Services
{
    public class NotificationService : INotificationService
    {
        private readonly INotificationRepository _notifications;
        private readonly IUserRepository _users;

        public NotificationService(
            INotificationRepository notifications,
            IUserRepository users)
        {
            _notifications = notifications;
            _users = users;
        }

        public async Task<NotificationsPageDto> GetMyNotificationsAsync(string userId, bool unreadOnly, int page, int pageSize)
        {
            var normalizedPage = page <= 0 ? 1 : page;
            var normalizedPageSize = pageSize <= 0 ? 20 : Math.Min(pageSize, 100);

            var (items, total) = await _notifications.GetByUserAsync(
                userId,
                unreadOnly,
                normalizedPage,
                normalizedPageSize);

            var unreadCount = await _notifications.CountUnreadAsync(userId);

            return new NotificationsPageDto
            {
                Total = total,
                UnreadCount = unreadCount,
                Page = normalizedPage,
                PageSize = normalizedPageSize,
                Data = items.Select(Map).ToList()
            };
        }

        public async Task<long> GetUnreadCountAsync(string userId)
        {
            return await _notifications.CountUnreadAsync(userId);
        }

        public async Task MarkAsReadAsync(string userId, string notificationId)
        {
            var notification = await _notifications.GetByIdAsync(notificationId)
                ?? throw new NotFoundException("Notification not found");

            if (!string.Equals(notification.UserId, userId, StringComparison.Ordinal))
                throw new UnauthorizedActionException("You are not allowed to access this notification");

            if (notification.IsRead)
                return;

            await _notifications.MarkAsReadAsync(notificationId, DateTime.UtcNow);
        }

        public async Task MarkAllAsReadAsync(string userId)
        {
            await _notifications.MarkAllAsReadAsync(userId, DateTime.UtcNow);
        }

        public async Task NotifyDocumentUpdatedAsync(Document document, User actor)
        {
            var recipients = await GetDocumentStakeholdersAsync(document, document.DepartmentId, document.Department);

            await CreateNotificationsAsync(
                recipients,
                actor.Id,
                document,
                "DocumentUpdated",
                "Document updated",
                $"{actor.Name} updated document '{document.Title}'.");
        }

        public async Task NotifyDocumentApprovedAsync(Document document, User actor)
        {
            var recipients = await GetOwnerAndInstitutionAdminsAsync(document);

            await CreateNotificationsAsync(
                recipients,
                actor.Id,
                document,
                "DocumentApproved",
                "Document approved",
                $"{actor.Name} approved document '{document.Title}'.");
        }

        public async Task NotifyDocumentRejectedAsync(Document document, User actor, string? reason)
        {
            var recipients = await GetOwnerAndInstitutionAdminsAsync(document);
            var suffix = string.IsNullOrWhiteSpace(reason)
                ? string.Empty
                : $" Reason: {reason.Trim()}";

            await CreateNotificationsAsync(
                recipients,
                actor.Id,
                document,
                "DocumentRejected",
                "Document rejected",
                $"{actor.Name} rejected document '{document.Title}'.{suffix}");
        }

        public async Task NotifyDocumentTransferredAsync(Document document, User actor, string? previousDepartmentName, Department targetDepartment, string justification)
        {
            var recipients = await GetDocumentStakeholdersAsync(document, targetDepartment.Id, targetDepartment.Name);
            var sourceDepartment = string.IsNullOrWhiteSpace(previousDepartmentName) ? "Unknown department" : previousDepartmentName;

            await CreateNotificationsAsync(
                recipients,
                actor.Id,
                document,
                "DocumentTransferred",
                "Document transferred",
                $"{actor.Name} transferred document '{document.Title}' from '{sourceDepartment}' to '{targetDepartment.Name}'. Justification: {justification.Trim()}");
        }

        private async Task<List<User>> GetOwnerAndInstitutionAdminsAsync(Document document)
        {
            var allUsers = await _users.GetAllAsync();

            return allUsers
                .Where(user =>
                    string.Equals(user.Id, document.UserId, StringComparison.OrdinalIgnoreCase) ||
                    (string.Equals(user.InstitutionId, document.InstitutionId, StringComparison.OrdinalIgnoreCase) &&
                     ApplicationRoles.IsInstitutionAdmin(user.Role)))
                .GroupBy(user => user.Id)
                .Select(group => group.First())
                .ToList();
        }

        private async Task<List<User>> GetDocumentStakeholdersAsync(Document document, string? departmentId, string? departmentName)
        {
            var allUsers = await _users.GetAllAsync();

            return allUsers
                .Where(user =>
                    string.Equals(user.Id, document.UserId, StringComparison.OrdinalIgnoreCase) ||
                    (string.Equals(user.InstitutionId, document.InstitutionId, StringComparison.OrdinalIgnoreCase) &&
                     ApplicationRoles.IsInstitutionAdmin(user.Role)) ||
                    (string.Equals(user.InstitutionId, document.InstitutionId, StringComparison.OrdinalIgnoreCase) &&
                     ApplicationRoles.IsManager(user.Role) &&
                     MatchesDepartment(user, departmentId, departmentName)))
                .GroupBy(user => user.Id)
                .Select(group => group.First())
                .ToList();
        }

        private static bool MatchesDepartment(User user, string? departmentId, string? departmentName)
        {
            if (!string.IsNullOrWhiteSpace(departmentId) &&
                string.Equals(user.DepartmentId, departmentId, StringComparison.OrdinalIgnoreCase))
            {
                return true;
            }

            return !string.IsNullOrWhiteSpace(departmentName) &&
                   string.Equals(user.Department, departmentName, StringComparison.OrdinalIgnoreCase);
        }

        private async Task CreateNotificationsAsync(
            IEnumerable<User> recipients,
            string actorUserId,
            Document document,
            string type,
            string title,
            string message)
        {
            var notifications = recipients
                .Where(user => !string.IsNullOrWhiteSpace(user.Id))
                .Where(user => !string.Equals(user.Id, actorUserId, StringComparison.OrdinalIgnoreCase))
                .Select(user => new Notification
                {
                    UserId = user.Id,
                    DocumentId = document.Id,
                    InstitutionId = document.InstitutionId,
                    Type = type,
                    Title = title,
                    Message = message,
                    IsRead = false,
                    CreatedAt = DateTime.UtcNow
                })
                .ToList();

            await _notifications.CreateManyAsync(notifications);
        }

        private static NotificationDto Map(Notification notification)
        {
            return new NotificationDto
            {
                Id = notification.Id,
                DocumentId = notification.DocumentId,
                Type = notification.Type,
                Title = notification.Title,
                Message = notification.Message,
                IsRead = notification.IsRead,
                CreatedAt = notification.CreatedAt,
                ReadAt = notification.ReadAt
            };
        }
    }
}
