using eArchiveSystem.Application.Interfaces.Persistence;
using eArchiveSystem.Domain.Models;
using MongoDB.Driver;

namespace eArchiveSystem.Infrastructure.Persistence.Repositories
{
    public class DepartmentRepository : IDepartmentRepository
    {
        private readonly IMongoCollection<Department> _departments;

        public DepartmentRepository(IMongoDatabase database)
        {
            _departments = database.GetCollection<Department>("Departments");
        }

        public Task CreateAsync(Department department) =>
            _departments.InsertOneAsync(department);

        public Task UpdateAsync(string id, Department department) =>
            _departments.ReplaceOneAsync(d => d.Id == id, department);

        public async Task<bool> DeleteAsync(string id)
        {
            var result = await _departments.DeleteOneAsync(d => d.Id == id);
            return result.DeletedCount > 0;
        }

        public Task<Department?> GetByIdAsync(string id) =>
            _departments.Find(d => d.Id == id).FirstOrDefaultAsync();

        public Task<Department?> GetByNameAsync(string institutionId, string name) =>
            _departments.Find(d => d.InstitutionId == institutionId && d.Name.ToLower() == name.ToLower()).FirstOrDefaultAsync();

        public Task<List<Department>> GetByInstitutionIdAsync(string institutionId) =>
            _departments.Find(d => d.InstitutionId == institutionId).ToListAsync();
    }
}
