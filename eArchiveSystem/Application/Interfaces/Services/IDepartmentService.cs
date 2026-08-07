using eArchiveSystem.Application.DTOs;

namespace eArchiveSystem.Application.Interfaces.Services
{
    public interface IDepartmentService
    {
        Task<DepartmentDto> AddDepartmentAsync(AddDepartmentDto dto, string requesterId);
        Task<List<DepartmentDto>> GetDepartmentsAsync(string requesterId, string requesterRole, string? institutionId);
        Task<List<DepartmentTreeDto>> GetDepartmentTreeAsync(string requesterId, string requesterRole, string? institutionId);
        Task<DepartmentDto> UpdateDepartmentAsync(string departmentId, UpdateDepartmentDto dto, string requesterId);
        Task DeleteDepartmentAsync(string departmentId, string requesterId);
        Task<DepartmentDto> GetDepartmentByIdAsync(string departmentId, string requesterId);
    }
}
