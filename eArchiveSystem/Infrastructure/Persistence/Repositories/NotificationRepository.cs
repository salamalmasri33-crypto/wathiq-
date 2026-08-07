using eArchiveSystem.Application.Interfaces.Persistence;
using eArchiveSystem.Domain.Models;
using MongoDB.Bson;
using MongoDB.Driver;

namespace eArchiveSystem.Infrastructure.Persistence.Repositories
{
    public class NotificationRepository : INotificationRepository
    {
        private readonly IMongoCollection<Notification> _notifications;

        public NotificationRepository(IMongoDatabase database)
        {
            _notifications = database.GetCollection<Notification>("Notifications");
        }

        public async Task CreateManyAsync(IReadOnlyCollection<Notification> notifications)
        {
            if (notifications == null || notifications.Count == 0)
                return;

            await _notifications.InsertManyAsync(notifications);
        }

        public async Task<(List<Notification> Notifications, long TotalCount)> GetByUserAsync(string userId, bool unreadOnly, int page, int pageSize)
        {
            var filter = Builders<Notification>.Filter.Eq(x => x.UserId, userId);

            if (unreadOnly)
            {
                filter &= Builders<Notification>.Filter.Eq(x => x.IsRead, false);
            }

            var total = await _notifications.CountDocumentsAsync(filter);
            var notifications = await _notifications
                .Find(filter)
                .SortByDescending(x => x.CreatedAt)
                .Skip((page - 1) * pageSize)
                .Limit(pageSize)
                .ToListAsync();

            return (notifications, total);
        }

        public async Task<Notification?> GetByIdAsync(string id)
        {
            if (!ObjectId.TryParse(id, out _))
                return null;

            return await _notifications
                .Find(x => x.Id == id)
                .FirstOrDefaultAsync();
        }

        public async Task<long> CountUnreadAsync(string userId)
        {
            var filter = Builders<Notification>.Filter.Eq(x => x.UserId, userId)
                & Builders<Notification>.Filter.Eq(x => x.IsRead, false);

            return await _notifications.CountDocumentsAsync(filter);
        }

        public async Task MarkAsReadAsync(string id, DateTime readAt)
        {
            var update = Builders<Notification>.Update
                .Set(x => x.IsRead, true)
                .Set(x => x.ReadAt, readAt);

            await _notifications.UpdateOneAsync(x => x.Id == id, update);
        }

        public async Task MarkAllAsReadAsync(string userId, DateTime readAt)
        {
            var filter = Builders<Notification>.Filter.Eq(x => x.UserId, userId)
                & Builders<Notification>.Filter.Eq(x => x.IsRead, false);

            var update = Builders<Notification>.Update
                .Set(x => x.IsRead, true)
                .Set(x => x.ReadAt, readAt);

            await _notifications.UpdateManyAsync(filter, update);
        }
    }
}
