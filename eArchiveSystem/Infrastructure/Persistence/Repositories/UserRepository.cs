using eArchiveSystem.Application.Interfaces.Persistence;
using eArchiveSystem.Domain.Models;
using MongoDB.Driver;
using MongoDB.Bson;

namespace eArchiveSystem.Infrastructure.Persistence.Repositories
{
    // Stores and retrieves user records from MongoDB.
    public class UserRepository : IUserRepository
    {
        private readonly IMongoCollection<User> _users;

        public UserRepository(IMongoDatabase database)
        {
            _users = database.GetCollection<User>("Users"); 
        }

        public async Task<List<User>> GetAllAsync() =>
            await _users.Find(_ => true).ToListAsync();

        public async Task<User> GetByEmailAsync(string email) =>
            await _users.Find(u => u.Email == email).FirstOrDefaultAsync();

        public async Task CreateAsync(User user) =>
            await _users.InsertOneAsync(user);

        public async Task UpdateAsync(string id, User user) =>
            await _users.ReplaceOneAsync(u => u.Id == id, user);

        public async Task<User> GetByIdAsync(string id)
        {
            if (!ObjectId.TryParse(id, out _))
                return null;
            return await _users.Find(u => u.Id == id).FirstOrDefaultAsync();
        }


        public async Task DeleteAsync(string id) =>
    await _users.DeleteOneAsync(u => u.Id == id);
        public async Task<User> GetByResetToken(string token) =>
    await _users.Find(u => u.ResetCode == token).FirstOrDefaultAsync();

        public async Task<List<User>> GetByRoleAsync(string role)
        {
            return await _users
                .Find(x => x.Role == role)
                .ToListAsync();
        }
        public async Task<List<User>> GetByIdsAsync(List<string> ids)
        {
            if (ids == null || !ids.Any())
                return new List<User>();

            // Skip invalid ObjectId values before querying MongoDB.
            var validIds = ids
                .Where(id => ObjectId.TryParse(id, out _))
                .ToList();

            if (!validIds.Any())
                return new List<User>();

            var filter = Builders<User>.Filter.In(u => u.Id, validIds);
            return await _users.Find(filter).ToListAsync();
        } 
    }
}
