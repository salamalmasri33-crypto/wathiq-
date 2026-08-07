using eArchiveSystem.Domain.Models;

namespace eArchiveSystem.Application.Interfaces.Persistence
{
    public interface IUserRepository
    {
        Task<User> GetByEmailAsync(string email);
        Task CreateAsync(User user);
        Task UpdateAsync(string id, User user);
        Task DeleteAsync(string id);
        Task<List<User>> GetAllAsync();
        Task<User> GetByIdAsync(string id);
        Task<User> GetByResetToken(string token);
        Task<List<User>> GetByRoleAsync(string role);
        Task<List<User>> GetByIdsAsync(List<string> ids);


    }
}

