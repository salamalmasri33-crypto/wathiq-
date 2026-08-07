using System.Security.Claims;
using eArchiveSystem.Application.DTOs;
using eArchiveSystem.Application.Interfaces.Services;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;

namespace eArchiveSystem.Presentation.Controllers
{
    [ApiController]
    [Route("api/departments")]
    public class DepartmentsController : ControllerBase
    {
        private readonly IDepartmentService _departmentService;

        public DepartmentsController(IDepartmentService departmentService)
        {
            _departmentService = departmentService;
        }

        [Authorize(Roles = "SystemAdmin,InstitutionAdmin")]
        [HttpPost]
        public async Task<IActionResult> AddDepartment([FromBody] AddDepartmentDto dto)
        {
            var requesterId = User.FindFirst(ClaimTypes.NameIdentifier)?.Value!;
            var result = await _departmentService.AddDepartmentAsync(dto, requesterId);
            return Ok(result);
        }

        [Authorize]
        [HttpGet]
        public async Task<IActionResult> GetDepartments([FromQuery] string? institutionId)
        {
            var requesterId = User.FindFirst(ClaimTypes.NameIdentifier)?.Value!;
            var requesterRole = User.FindFirst(ClaimTypes.Role)?.Value!;
            var result = await _departmentService.GetDepartmentsAsync(requesterId, requesterRole, institutionId);
            return Ok(result);
        }

        [Authorize]
        [HttpGet("tree")]
        public async Task<IActionResult> GetDepartmentTree([FromQuery] string? institutionId)
        {
            var requesterId = User.FindFirst(ClaimTypes.NameIdentifier)?.Value!;
            var requesterRole = User.FindFirst(ClaimTypes.Role)?.Value!;
            var result = await _departmentService.GetDepartmentTreeAsync(requesterId, requesterRole, institutionId);
            return Ok(result);
        }

        [Authorize(Roles = "SystemAdmin,InstitutionAdmin")]
        [HttpPut("{departmentId}")]
        public async Task<IActionResult> UpdateDepartment(string departmentId, [FromBody] UpdateDepartmentDto dto)
        {
            var requesterId = User.FindFirst(ClaimTypes.NameIdentifier)?.Value!;
            var result = await _departmentService.UpdateDepartmentAsync(departmentId, dto, requesterId);
            return Ok(result);
        }

        [Authorize(Roles = "SystemAdmin,InstitutionAdmin")]
        [HttpDelete("{departmentId}")]
        public async Task<IActionResult> DeleteDepartment(string departmentId)
        {
            var requesterId = User.FindFirst(ClaimTypes.NameIdentifier)?.Value!;
            await _departmentService.DeleteDepartmentAsync(departmentId, requesterId);
            return Ok(new { message = "Department deleted successfully" });
        }

        [Authorize]
        [HttpGet("{departmentId}")]
        public async Task<IActionResult> GetDepartmentById(string departmentId)
        {
            var requesterId = User.FindFirst(ClaimTypes.NameIdentifier)?.Value!;
            var result = await _departmentService.GetDepartmentByIdAsync(departmentId, requesterId);
            return Ok(result);
        }
    }
}
