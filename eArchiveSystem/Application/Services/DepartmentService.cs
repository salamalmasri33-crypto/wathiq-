using eArchiveSystem.Application.DTOs;
using eArchiveSystem.Application.Exceptions;
using eArchiveSystem.Application.Interfaces.Persistence;
using eArchiveSystem.Application.Interfaces.Services;
using eArchiveSystem.Application.Security;
using eArchiveSystem.Domain.Models;

namespace eArchiveSystem.Application.Services
{
    public class DepartmentService : IDepartmentService
    {
        private readonly IDepartmentRepository _departments;
        private readonly IUserRepository _users;

        public DepartmentService(
            IDepartmentRepository departments,
            IUserRepository users)
        {
            _departments = departments;
            _users = users;
        }

        public async Task<DepartmentDto> AddDepartmentAsync(AddDepartmentDto dto, string requesterId)
        {
            var requester = await _users.GetByIdAsync(requesterId)
                ?? throw new NotFoundException("Requester not found");

            var institutionId = ResolveInstitutionId(dto.InstitutionId, requester);

            if (string.IsNullOrWhiteSpace(dto.Name))
                throw new ValidationException("Department name is required");

            var exists = await _departments.GetByNameAsync(institutionId, dto.Name.Trim());
            if (exists != null)
                throw new ConflictException("Department already exists in this institution");

            var parentDepartmentId = await ResolveParentDepartmentIdAsync(
                institutionId,
                dto.ParentDepartmentId,
                currentDepartmentId: null);

            var department = new Department
            {
                Name = dto.Name.Trim(),
                InstitutionId = institutionId,
                ParentDepartmentId = parentDepartmentId,
                CreatedAt = DateTime.UtcNow,
                UpdatedAt = DateTime.UtcNow
            };

            await _departments.CreateAsync(department);

            return await MapAsync(department);
        }

        public async Task<List<DepartmentDto>> GetDepartmentsAsync(string requesterId, string requesterRole, string? institutionId)
        {
            var requester = await _users.GetByIdAsync(requesterId)
                ?? throw new NotFoundException("Requester not found");

            var scopedInstitutionId = ResolveInstitutionId(institutionId, requester, allowInstitutionAdminsWithoutInput: true);
            var departments = await _departments.GetByInstitutionIdAsync(scopedInstitutionId);

            return departments
                .OrderBy(d => d.Name)
                .Select(d => Map(d, departments))
                .ToList();
        }

        public async Task<List<DepartmentTreeDto>> GetDepartmentTreeAsync(string requesterId, string requesterRole, string? institutionId)
        {
            var requester = await _users.GetByIdAsync(requesterId)
                ?? throw new NotFoundException("Requester not found");

            var scopedInstitutionId = ResolveInstitutionId(institutionId, requester, allowInstitutionAdminsWithoutInput: true);
            var departments = await _departments.GetByInstitutionIdAsync(scopedInstitutionId);

            return BuildTree(departments);
        }

        public async Task<DepartmentDto> UpdateDepartmentAsync(string departmentId, UpdateDepartmentDto dto, string requesterId)
        {
            var requester = await _users.GetByIdAsync(requesterId)
                ?? throw new NotFoundException("Requester not found");

            var department = await _departments.GetByIdAsync(departmentId)
                ?? throw new NotFoundException("Department not found");

            EnsureCanManageDepartment(requester, department);

            if (string.IsNullOrWhiteSpace(dto.Name))
                throw new ValidationException("Department name is required");

            var existing = await _departments.GetByNameAsync(department.InstitutionId, dto.Name.Trim());
            if (existing != null && existing.Id != departmentId)
                throw new ConflictException("Department already exists in this institution");

            department.Name = dto.Name.Trim();
            department.ParentDepartmentId = await ResolveParentDepartmentIdAsync(
                department.InstitutionId,
                dto.ParentDepartmentId,
                departmentId);
            department.UpdatedAt = DateTime.UtcNow;

            await _departments.UpdateAsync(departmentId, department);

            return await MapAsync(department);
        }

        public async Task DeleteDepartmentAsync(string departmentId, string requesterId)
        {
            var requester = await _users.GetByIdAsync(requesterId)
                ?? throw new NotFoundException("Requester not found");

            var department = await _departments.GetByIdAsync(departmentId)
                ?? throw new NotFoundException("Department not found");

            EnsureCanManageDepartment(requester, department);

            var institutionDepartments = await _departments.GetByInstitutionIdAsync(department.InstitutionId);
            if (institutionDepartments.Any(d => d.ParentDepartmentId == departmentId))
                throw new ValidationException("Cannot delete a department that contains child departments");

            var deleted = await _departments.DeleteAsync(departmentId);
            if (!deleted)
                throw new NotFoundException("Department not found");
        }

        public async Task<DepartmentDto> GetDepartmentByIdAsync(string departmentId, string requesterId)
        {
            var requester = await _users.GetByIdAsync(requesterId)
                ?? throw new NotFoundException("Requester not found");

            var department = await _departments.GetByIdAsync(departmentId)
                ?? throw new NotFoundException("Department not found");

            EnsureCanReadDepartment(requester, department);

            var institutionDepartments = await _departments.GetByInstitutionIdAsync(department.InstitutionId);
            return Map(department, institutionDepartments);
        }

        private async Task<DepartmentDto> MapAsync(Department department)
        {
            var institutionDepartments = await _departments.GetByInstitutionIdAsync(department.InstitutionId);
            return Map(department, institutionDepartments);
        }

        private static DepartmentDto Map(Department department, IReadOnlyCollection<Department> institutionDepartments)
        {
            var parent = string.IsNullOrWhiteSpace(department.ParentDepartmentId)
                ? null
                : institutionDepartments.FirstOrDefault(d => d.Id == department.ParentDepartmentId);

            return new DepartmentDto
            {
                Id = department.Id,
                Name = department.Name,
                InstitutionId = department.InstitutionId,
                ParentDepartmentId = department.ParentDepartmentId,
                ParentDepartmentName = parent?.Name
            };
        }

        private async Task<string?> ResolveParentDepartmentIdAsync(string institutionId, string? requestedParentDepartmentId, string? currentDepartmentId)
        {
            if (string.IsNullOrWhiteSpace(requestedParentDepartmentId))
                return null;

            var parentDepartmentId = requestedParentDepartmentId.Trim();

            if (currentDepartmentId != null &&
                string.Equals(parentDepartmentId, currentDepartmentId, StringComparison.OrdinalIgnoreCase))
            {
                throw new ValidationException("Department cannot be its own parent");
            }

            var parentDepartment = await _departments.GetByIdAsync(parentDepartmentId)
                ?? throw new NotFoundException("Parent department not found");

            if (!string.Equals(parentDepartment.InstitutionId, institutionId, StringComparison.OrdinalIgnoreCase))
                throw new ValidationException("Parent department must belong to the same institution");

            if (!string.IsNullOrWhiteSpace(currentDepartmentId))
            {
                var institutionDepartments = await _departments.GetByInstitutionIdAsync(institutionId);
                EnsureNoCycle(currentDepartmentId, parentDepartmentId, institutionDepartments);
            }

            return parentDepartmentId;
        }

        private static void EnsureNoCycle(string currentDepartmentId, string newParentDepartmentId, IReadOnlyCollection<Department> institutionDepartments)
        {
            var visited = new HashSet<string>(StringComparer.OrdinalIgnoreCase) { currentDepartmentId };
            var currentParentId = newParentDepartmentId;

            while (!string.IsNullOrWhiteSpace(currentParentId))
            {
                if (!visited.Add(currentParentId))
                    throw new ValidationException("Department hierarchy cannot contain cycles");

                currentParentId = institutionDepartments
                    .FirstOrDefault(d => d.Id == currentParentId)?
                    .ParentDepartmentId;
            }
        }

        private static List<DepartmentTreeDto> BuildTree(IReadOnlyCollection<Department> departments)
        {
            var nodes = departments.ToDictionary(
                d => d.Id,
                d => new DepartmentTreeDto
                {
                    Id = d.Id,
                    Name = d.Name,
                    InstitutionId = d.InstitutionId,
                    ParentDepartmentId = d.ParentDepartmentId
                },
                StringComparer.OrdinalIgnoreCase);

            var roots = new List<DepartmentTreeDto>();

            foreach (var department in departments.OrderBy(d => d.Name))
            {
                var node = nodes[department.Id];

                if (string.IsNullOrWhiteSpace(department.ParentDepartmentId) ||
                    !nodes.TryGetValue(department.ParentDepartmentId, out var parentNode))
                {
                    roots.Add(node);
                    continue;
                }

                parentNode.Children.Add(node);
            }

            SortTree(roots);
            return roots;
        }

        private static void SortTree(List<DepartmentTreeDto> nodes)
        {
            nodes.Sort((left, right) => string.Compare(left.Name, right.Name, StringComparison.OrdinalIgnoreCase));
            foreach (var node in nodes)
            {
                SortTree(node.Children);
            }
        }

        private static void EnsureCanManageDepartment(User requester, Department department)
        {
            if (ApplicationRoles.IsSystemAdmin(requester.Role))
                return;

            if (ApplicationRoles.IsInstitutionAdmin(requester.Role) &&
                string.Equals(requester.InstitutionId, department.InstitutionId, StringComparison.OrdinalIgnoreCase))
            {
                return;
            }

            throw new UnauthorizedActionException("You are not allowed to manage this department");
        }

        private static void EnsureCanReadDepartment(User requester, Department department)
        {
            if (ApplicationRoles.IsSystemAdmin(requester.Role))
                return;

            if (string.Equals(requester.InstitutionId, department.InstitutionId, StringComparison.OrdinalIgnoreCase))
                return;

            throw new UnauthorizedActionException("You are not allowed to view this department");
        }

        private static string ResolveInstitutionId(string? requestedInstitutionId, User requester, bool allowInstitutionAdminsWithoutInput = false)
        {
            if (ApplicationRoles.IsSystemAdmin(requester.Role))
            {
                if (string.IsNullOrWhiteSpace(requestedInstitutionId))
                    throw new ValidationException("InstitutionId is required");

                return requestedInstitutionId.Trim();
            }

            if (ApplicationRoles.IsInstitutionAdmin(requester.Role))
            {
                if (string.IsNullOrWhiteSpace(requester.InstitutionId))
                    throw new ValidationException("Institution admin must belong to an institution");

                if (!string.IsNullOrWhiteSpace(requestedInstitutionId) &&
                    !string.Equals(requestedInstitutionId, requester.InstitutionId, StringComparison.OrdinalIgnoreCase))
                {
                    throw new UnauthorizedActionException("You can only manage departments in your institution");
                }

                return requester.InstitutionId;
            }

            if (allowInstitutionAdminsWithoutInput && !string.IsNullOrWhiteSpace(requester.InstitutionId))
                return requester.InstitutionId;

            throw new UnauthorizedActionException("You are not allowed to manage departments");
        }
    }
}
