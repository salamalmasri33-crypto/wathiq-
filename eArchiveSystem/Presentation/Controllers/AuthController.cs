using eArchiveSystem.Application.DTOs;
using eArchiveSystem.Application.Interfaces.Services;

using Microsoft.AspNetCore.Mvc;

namespace eArchiveSystem.Controllers
{
    [ApiController]
    [Route("api/auth")]
    // Handles authentication and password recovery endpoints.
    public class AuthController : ControllerBase
    {
        private readonly IUserService _userService; 

        public AuthController(IUserService userService)
        { 
            _userService = userService; 
        }

        // Signs in a user and returns a token or a 2FA challenge.
        [HttpPost("login")]
        public async Task<IActionResult> Login(LoginDto dto) 
        {
            var result = await _userService.Login(dto);

            // Return the 2FA challenge when a second step is required.
            if (result.Requires2FA)
            {
                return Ok(new
                {
                    requires2FA = true,
                    message = result.Message
                });
            }

            // Return the signed-in user payload when authentication is complete.
            return Ok(new
            {
                token = result.Token,
                user = new
                {
                    id = result.User.Id,
                    name = result.User.Name,
                    email = result.User.Email,
                    role = result.User.Role,
                    institutionId = result.User.InstitutionId,
                    departmentId = result.User.DepartmentId,
                    department = result.User.Department
                },
                requires2FA = false
            });
        }
        

        // Ends the current session on the client side.
        [HttpPost("logout")]
        public async Task<IActionResult> Logout()
        {
            var message = await _userService.Logout();
            return Ok(new { message });
        }

        // Starts the password reset flow.
        [HttpPost("password/forgot")]
        public async Task<IActionResult> Forgot(ForgotPasswordDto dto)
        {
            var result = await _userService.ForgotPassword(dto);
            return Ok(result);
        }


        // Completes the password reset flow.
        [HttpPost("password/reset")]
        public async Task<IActionResult> Reset(ResetPasswordDto dto)
        {
            var result = await _userService.ResetPassword(dto);
            return Ok(result);
        }

        // Verifies the submitted 2FA code.
        [HttpPost("verify-2fa")]
        public async Task<IActionResult> Verify2FA([FromBody] Verify2FADto dto)
        {
            var result = await _userService.VerifyTwoFactorAsync(dto);

            return Ok(new
            {
                token = result.Token,
                user = new
                {
                    id = result.User.Id,
                    name = result.User.Name,
                    email = result.User.Email,
                    role = result.User.Role,
                    institutionId = result.User.InstitutionId,
                    departmentId = result.User.DepartmentId,
                    department = result.User.Department
                },
                requires2FA = false,
                message = result.Message
            });
        }


    }
}
