using eArchiveSystem.Domain.Models;

namespace eArchiveSystem.Application.Interfaces.Persistence
{
    public interface IDepartmentRepository
    {
        Task CreateAsync(Department department);
        Task UpdateAsync(string id, Department department);
        Task<bool> DeleteAsync(string id);
        Task<Department?> GetByIdAsync(string id);
        Task<Department?> GetByNameAsync(string institutionId, string name);
        Task<List<Department>> GetByInstitutionIdAsync(string institutionId);
    } 
}
