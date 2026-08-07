using eArchiveSystem.Application.DTOs;
using eArchiveSystem.Domain.Models;
using eArchiveSystem.Utils;

namespace eArchiveSystem.Application.Interfaces.Services
{
    public interface IUserService
    {
        Task<AuthResult> Login(LoginDto dto);
        Task<string> Logout();
        Task<string> UpdateProfile(string userId, UpdateProfileDto dto);

        // Two-Factor Authentication (2FA)
        Task<bool> GetTwoFactorEnabled(string userId);
        Task<string> SetTwoFactorEnabled(string userId, bool enabled);

        Task<User> AddUser(AddUserDto dto, string requesterId);
        Task<string> DeleteUser(string id, string requesterRole, string requesterId);
        Task<string> AssignRole(string userId, string role, string requesterId);
        Task<User> CreateAdmin(CreateAdminDto dto);
        Task<string> EditUser(string id, UpdateUserDto dto, string requesterId);
        Task<string> ForgotPassword(ForgotPasswordDto dto);
        Task<string> ResetPassword(ResetPasswordDto dto);
        Task<List<UserDto>> GetUsers(string? role, string? search, string currentUserId);
        Task CreateBootstrapAdminIfNotExists();
        Task<AuthResult> VerifyTwoFactorAsync(Verify2FADto dto);
        Task<string> ChangePassword(string userId, ChangePasswordDto dto);

    }

}

