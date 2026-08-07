using eArchiveSystem.Domain.Models;

namespace eArchiveSystem.Application.Interfaces.Persistence
{
    public interface INotificationRepository
    {
        Task CreateManyAsync(IReadOnlyCollection<Notification> notifications);
        Task<(List<Notification> Notifications, long TotalCount)> GetByUserAsync(string userId, bool unreadOnly, int page, int pageSize);
        Task<Notification?> GetByIdAsync(string id);
        Task<long> CountUnreadAsync(string userId);
        Task MarkAsReadAsync(string id, DateTime readAt);
        Task MarkAllAsReadAsync(string userId, DateTime readAt);
    }
}
