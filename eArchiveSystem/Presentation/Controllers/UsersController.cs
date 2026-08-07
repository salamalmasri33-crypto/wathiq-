using eArchiveSystem.Application.DTOs;
using eArchiveSystem.Application.Interfaces.Services;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using System.Security.Claims;

namespace eArchiveSystem.Presentation.Controllers
{
    [ApiController]
    [Route("api/users")]
    // Manages user administration and self-service account actions.
    public class UsersController : ControllerBase
    {
        private readonly IUserService _service;

        public UsersController(IUserService service)
        {
            _service = service;
        }

        // Creates a user within the allowed admin scope.
        [Authorize(Roles = "SystemAdmin,InstitutionAdmin")]
        [HttpPost("add")]
        public async Task<IActionResult> AddUser(AddUserDto dto)
        {
            var requesterId = User.FindFirst(ClaimTypes.NameIdentifier)?.Value!;
            var user = await _service.AddUser(dto, requesterId);
            return Ok(user);
        }

        // Creates the first system admin account.
        [Authorize(Roles = "SystemAdmin")]
        [HttpPost("create-admin")]
        public async Task<IActionResult> CreateAdmin(CreateAdminDto dto)
        {
            var admin = await _service.CreateAdmin(dto);
            return Ok(new
            {
                message = "System admin created successfully",
                admin = new
                {
                    id = admin.Id,
                    name = admin.Name,
                    email = admin.Email,
                    role = admin.Role
                }
            });
        }

        // Allows signed-in users to update their own profile.
        [Authorize]
        [HttpPut("profile")]
        public async Task<IActionResult> UpdateProfile([FromBody] UpdateProfileDto dto)
        {
            var userId = User.FindFirst(System.Security.Claims.ClaimTypes.NameIdentifier)?.Value;

            var result = await _service.UpdateProfile(userId, dto);

            return Ok(new { message = result });
        }

        // Updates a user's role.
        [Authorize(Roles = "SystemAdmin,InstitutionAdmin")]
        [HttpPut("{id}/assign-role")]
        public async Task<IActionResult> AssignRole(string id, AssignRoleDto dto)
        {
            var requesterId = User.FindFirst(ClaimTypes.NameIdentifier)?.Value!;
            var result = await _service.AssignRole(id, dto.Role, requesterId);
            return Ok(new { message = result });
        }


        // Deletes a user within the allowed admin scope.
        [Authorize(Roles = "SystemAdmin,InstitutionAdmin")]
        [HttpDelete("{id}")]
        public async Task<IActionResult> DeleteUser(string id)
        {
            var requesterId = User.FindFirst(ClaimTypes.NameIdentifier)?.Value!;
            var role = User.FindFirst(System.Security.Claims.ClaimTypes.Role)?.Value;
            var result = await _service.DeleteUser(id, role, requesterId);

            return Ok(new { message = result });
        }

        // Updates a user as an administrator.
        [Authorize(Roles = "SystemAdmin,InstitutionAdmin")]
        [HttpPut("edit/{id}")]
        public async Task<IActionResult> EditUser(string id, UpdateUserDto dto)
        {
            var requesterId = User.FindFirst(ClaimTypes.NameIdentifier)?.Value!;
            var result = await _service.EditUser(id, dto, requesterId);
            return Ok(new { message = result });
        }
        // Returns the visible users for the current admin.
        [Authorize(Roles = "SystemAdmin,InstitutionAdmin")]
        [HttpGet]
        public async Task<IActionResult> GetUsers([FromQuery] string? role, [FromQuery] string? search)
        {
            var currentUserId = User.FindFirst(System.Security.Claims.ClaimTypes.NameIdentifier)?.Value;

            var users = await _service.GetUsers(role, search, currentUserId);
            return Ok(users);
        }

        // Changes the current user's password.
        [Authorize]
        [HttpPut("change-password")]
        public async Task<IActionResult> ChangePassword([FromBody] ChangePasswordDto dto)
        {
            var userId = User.FindFirst(ClaimTypes.NameIdentifier)?.Value;

            var result = await _service.ChangePassword(userId, dto);

            return Ok(new { message = result });
        }

        // Returns the current user's 2FA status.

        /// <summary>
        /// Get current user's 2FA status.
        /// </summary>
        [Authorize]
        [HttpGet("2fa")]
        public async Task<IActionResult> Get2FAStatus()
        {
            var userId = User.FindFirst(ClaimTypes.NameIdentifier)?.Value;
            var enabled = await _service.GetTwoFactorEnabled(userId);
            return Ok(new { enabled });
        }

        /// <summary>
        /// Enable or disable the current user's 2FA.
        /// </summary>
        // Updates the current user's 2FA setting.
        [Authorize]
        [HttpPut("2fa")]
        public async Task<IActionResult> Set2FAStatus([FromBody] TwoFactorToggleDto dto)
        {
            var userId = User.FindFirst(ClaimTypes.NameIdentifier)?.Value;
            var message = await _service.SetTwoFactorEnabled(userId, dto.Enabled);
            return Ok(new { message, enabled = dto.Enabled });
        }

    }
} 
