using eArchiveSystem.Application.DTOs;
using eArchiveSystem.Application.Interfaces.Persistence;
using eArchiveSystem.Application.Exceptions;
using eArchiveSystem.Application.Interfaces.Security;
using eArchiveSystem.Application.Interfaces.Services;
using eArchiveSystem.Application.Security;
using eArchiveSystem.Domain.Models;
using eArchiveSystem.Utils;

namespace eArchiveSystem.Application.Services
{
    // Handles authentication, user administration, and account security flows.
    public class UserService : IUserService
    {
        private readonly IUserRepository _repo;
        private readonly IDepartmentRepository _departments;
        private readonly IPasswordHasher _hasher;
        private readonly ITokenService _token;
        private readonly IEmailService _email;
        private readonly IConfiguration _config;
        private readonly IAuditService _audit;



        public UserService(
      IUserRepository repo,
      IDepartmentRepository departments,
      IPasswordHasher hasher,
      ITokenService token,
      IEmailService email,
      IConfiguration config,
      IAuditService audit
  )
        {
            _repo = repo;
            _departments = departments;
            _hasher = hasher;
            _token = token;
            _email = email;
            _config = config;
            _audit = audit;
        }


        // Creates a user with role and department validation.
        public async Task<User> AddUser(AddUserDto dto, string requesterId)
        {
            var requester = await _repo.GetByIdAsync(requesterId);
            if (requester == null)
                throw new NotFoundException("Requester not found");

            var exists = await _repo.GetByEmailAsync(dto.Email);
            if (exists != null)
                throw new ConflictException("Email already used");

            var validRoles = new[]
            {
                ApplicationRoles.SystemAdmin,
                ApplicationRoles.InstitutionAdmin,
                ApplicationRoles.Manager,
                ApplicationRoles.Employee
            };

            if (!validRoles.Contains(dto.Role))
                throw new ValidationException("Invalid role");

            if (ApplicationRoles.IsInstitutionAdmin(requester.Role))
            {
                if (dto.Role != ApplicationRoles.Manager &&
                    dto.Role != ApplicationRoles.Employee)
                {
                    throw new UnauthorizedActionException("Institution admin can only create managers and employees");
                }

                dto.InstitutionId = requester.InstitutionId;
            }
            else if (!ApplicationRoles.IsSystemAdmin(requester.Role))
            {
                throw new UnauthorizedActionException("You are not allowed to create users");
            }

            await ApplyDepartmentAssignmentAsync(dto.InstitutionId, dto.DepartmentId ?? dto.Department, user: null, dto);

            string hashedPassword = _hasher.Hash(dto.Password);

            var user = new User
            {
                Name = dto.Name,
                Email = dto.Email,
                Password = hashedPassword,
                Role = dto.Role,
                InstitutionId = dto.InstitutionId,
                DepartmentId = dto.DepartmentId ?? dto.Department,
                Department = dto.Department ?? dto.DepartmentId
            };
            await _repo.CreateAsync(user);
            return user;
        }

        // Authenticates credentials and starts 2FA when enabled.
      

        public async Task<AuthResult> Login(LoginDto dto)
        {
            var user = await _repo.GetByEmailAsync(dto.Email);
            if (user == null)
            {
                await _audit.LogAsync(
                    userId: "null",
                    role: "None",
                    action: "LoginFailed",
                    documentId: null,
                    description: $"Failed login attempt for email {dto.Email}"
                );

                throw new ValidationException("Invalid email or password");
            }


            // Reject locked accounts early.
            if (user.LockoutUntil != null && user.LockoutUntil > DateTime.UtcNow)
            {
                var remainingSeconds = (int)(user.LockoutUntil.Value - DateTime.UtcNow).TotalSeconds;
                throw new ValidationException($"Account locked. Try again after {remainingSeconds} seconds");
            }

            // Validate the submitted password.
            bool isMatch = _hasher.Verify(dto.Password, user.Password);

            if (!isMatch)
            {
                user.FailedLoginAttempts++;

                if (user.FailedLoginAttempts >= 3)
                {
                    user.LockoutUntil = DateTime.UtcNow.AddMinutes(1); // Lock for 1 minute.

                    await _audit.LogAsync(
                         user.Id,
                         user.Role,
                         "AccountLocked",
                         null,
                      $"User {user.Email} account locked for 1 minute"
                        );

                }

                await _repo.UpdateAsync(user.Id, user);
                await _audit.LogAsync(
                     user.Id,
                      user.Role,
                  "LoginFailed",
                   null,
                 $"Wrong password for {user.Email}"
                        );
                throw new ValidationException("Invalid email or password");
            }

            // Reset login counters after a successful password check.
            user.FailedLoginAttempts = 0;
            user.LockoutUntil = null;
            // Send a verification code when 2FA is enabled.
       
            if (user.TwoFactorEnabled)
            {
                string code = new Random().Next(100000, 999999).ToString();

                user.TwoFactorCode = code;
                user.TwoFactorExpiry = DateTime.UtcNow.AddMinutes(5);

                await _repo.UpdateAsync(user.Id, user);

                await _email.SendEmailAsync(
                    user.Email,
                    "Your Verification Code",
                    $"Your login verification code is: {code}"
                );
                await _audit.LogAsync(
                  user.Id,
                  user.Role,
                  "2FACodeSent",
                   null,
                  "Two-factor verification code sent"
                  );

                return new AuthResult
                {
                    Requires2FA = true,
                    Message = "Verification code sent to your email."
                };
            }


            // Issue a JWT when 2FA is not enabled.
            string token = _token.GenerateJwtToken(user);
            await _repo.UpdateAsync(user.Id, user);

            await _audit.LogAsync(
              user.Id,
              user.Role,
              "LoginSuccess",
               null,
              $"User {user.Email} logged in successfully"
            );

            return new AuthResult
            {
                Token = token,
                User = user,
                Requires2FA = false
            };

        } 

        // Returns the stateless logout response.
        public Task<string> Logout()
        {
       // JWT logout is handled on the client side.
            return Task.FromResult("Logged out successfully");
        }

        // Updates a user's role within the allowed admin scope.
        public async Task<string> AssignRole(string id, string newRole, string requesterId)
        {
            var requester = await _repo.GetByIdAsync(requesterId);
            if (requester == null)
                throw new NotFoundException("Requester not found");

            var user = await _repo.GetByIdAsync(id);
            if (user == null)
                throw new NotFoundException("User not found");

            // Accept only supported role values.
            var validRoles = new[] { ApplicationRoles.SystemAdmin, ApplicationRoles.InstitutionAdmin, ApplicationRoles.Manager, ApplicationRoles.Employee };
            if (!validRoles.Contains(newRole))
                throw new ValidationException("Invalid role");

            if (ApplicationRoles.IsInstitutionAdmin(requester.Role))
            {
                if (!string.Equals(requester.InstitutionId, user.InstitutionId, StringComparison.OrdinalIgnoreCase))
                    throw new UnauthorizedActionException("You can only manage users in your institution");

                if (newRole != ApplicationRoles.Manager &&
                    newRole != ApplicationRoles.Employee)
                {
                    throw new UnauthorizedActionException("Institution admin can only assign manager or employee roles");
                }
            }
            else if (!ApplicationRoles.IsSystemAdmin(requester.Role))
            {
                throw new UnauthorizedActionException("You are not allowed to assign roles");
            }

            user.Role = newRole;
            user.UpdatedAt = DateTime.Now;

            await _repo.UpdateAsync(id, user);

            return "Role updated successfully";
        }


        // Deletes a user within the allowed admin scope.
        public async Task<string> DeleteUser(string id, string requesterRole, string requesterId)
        {
            var requester = await _repo.GetByIdAsync(requesterId);
            if (requester == null)
                throw new NotFoundException("Requester not found");

            var target = await _repo.GetByIdAsync(id);
            if (target == null)
                throw new NotFoundException("User not found");

            if (ApplicationRoles.IsInstitutionAdmin(requester.Role))
            {
                if (!string.Equals(requester.InstitutionId, target.InstitutionId, StringComparison.OrdinalIgnoreCase))
                    throw new UnauthorizedActionException("You can only delete users in your institution");

                if (ApplicationRoles.IsSystemAdmin(target.Role) || ApplicationRoles.IsInstitutionAdmin(target.Role))
                    throw new UnauthorizedActionException("Institution admin cannot delete admin accounts");
            }
            else if (!ApplicationRoles.IsSystemAdmin(requesterRole))
            {
                throw new UnauthorizedActionException("Access denied");
            }

            await _repo.DeleteAsync(id);
            return "User deleted successfully";
        }
        // Updates the current user's profile fields.
        public async Task<string> UpdateProfile(string userId, UpdateProfileDto dto)
        {
            var user = await _repo.GetByIdAsync(userId);
            if (user == null)
                throw new NotFoundException("User not found");

            // Users can always update their own name and email.
            if (!string.IsNullOrEmpty(dto.Name))
                user.Name = dto.Name;

            if (!string.IsNullOrEmpty(dto.Email) && dto.Email != user.Email)
            {
                var exists = await _repo.GetByEmailAsync(dto.Email);
                if (exists != null)
                    throw new ConflictException("Email already in use");

                user.Email = dto.Email;
            }

            user.UpdatedAt = DateTime.Now;
            await _repo.UpdateAsync(userId, user);

            await _audit.LogAsync(
              user.Id,
              user.Role,
              "UpdateProfile",
              null,
              $"User updated profile. Name: {user.Name}, Email: {user.Email}"
              );
            return "Profile updated successfully";
        }
        // Changes the current user's password.
        public async Task<string> ChangePassword(string userId, ChangePasswordDto dto)
        {
            var user = await _repo.GetByIdAsync(userId);
            if (user == null)
                throw new NotFoundException("User not found");

            if (string.IsNullOrEmpty(dto.CurrentPassword))
                throw new ValidationException("Current password is required");       

            if (string.IsNullOrEmpty(dto.NewPassword))
                throw new ValidationException("New password is required");

            bool match = _hasher.Verify(dto.CurrentPassword, user.Password);
            if (!match)
                throw new ValidationException("Current password is incorrect");

            user.Password = _hasher.Hash(dto.NewPassword);
            user.UpdatedAt = DateTime.Now;

            await _repo.UpdateAsync(userId, user);

            await _audit.LogAsync(
                user.Id,
                user.Role,
                "ChangePassword",
                null,
                "User changed password"
            );

            return "Password updated successfully";
        }

        // Returns whether 2FA is enabled for the current user.
        public async Task<bool> GetTwoFactorEnabled(string userId)
        {
            var user = await _repo.GetByIdAsync(userId);
            if (user == null)
                throw new NotFoundException("User not found");

            return user.TwoFactorEnabled;
        }

        // Enables or disables 2FA for the current user.
        public async Task<string> SetTwoFactorEnabled(string userId, bool enabled)
        {
            var user = await _repo.GetByIdAsync(userId);
            if (user == null)
                throw new NotFoundException("User not found");

            user.TwoFactorEnabled = enabled;

            // Clear any pending code when 2FA is disabled.
            if (!enabled)
            {
                user.TwoFactorCode = null;
                user.TwoFactorExpiry = null;
            }

            user.UpdatedAt = DateTime.Now;
            await _repo.UpdateAsync(userId, user);

            await _audit.LogAsync(
                user.Id,
                user.Role,
                "Toggle2FA",
                null,
                $"User {(enabled ? "enabled" : "disabled")} two-factor authentication"
            );

            return enabled ? "Two-factor authentication enabled" : "Two-factor authentication disabled";
        }

        // Creates a system admin account.
        public async Task<User> CreateAdmin(CreateAdminDto dto)
        {
            var exists = await _repo.GetByEmailAsync(dto.Email);
            if (exists != null)
                throw new ConflictException("System admin email already exists");

            string hashedPassword = _hasher.Hash(dto.Password);

            var admin = new User
            {
                Name = dto.Name,
                Email = dto.Email,
                Password = hashedPassword,
                Role = ApplicationRoles.SystemAdmin
            };

            await _repo.CreateAsync(admin);

            return admin;
        }
        // Updates a user as an administrator.
        public async Task<string> EditUser(string id, UpdateUserDto dto, string requesterId)
        {
            var requester = await _repo.GetByIdAsync(requesterId);
            if (requester == null)
                throw new NotFoundException("Requester not found");

            var user = await _repo.GetByIdAsync(id);
            if (user == null)
                throw new NotFoundException("User not found");

            if (ApplicationRoles.IsInstitutionAdmin(requester.Role))
            {
                if (!string.Equals(requester.InstitutionId, user.InstitutionId, StringComparison.OrdinalIgnoreCase))
                    throw new UnauthorizedActionException("You can only edit users in your institution");

                if (ApplicationRoles.IsSystemAdmin(user.Role) || ApplicationRoles.IsInstitutionAdmin(user.Role))
                    throw new UnauthorizedActionException("Institution admin cannot edit admin accounts");
            }
            else if (!ApplicationRoles.IsSystemAdmin(requester.Role))
            {
                throw new UnauthorizedActionException("You are not allowed to edit users");
            }

            // Update the name when it is provided.
            if (!string.IsNullOrEmpty(dto.Name))
                user.Name = dto.Name;

            // Update the email when it is provided.
            if (!string.IsNullOrEmpty(dto.Email))
                user.Email = dto.Email;

            // Allow admins to replace the password.
            if (!string.IsNullOrEmpty(dto.NewPassword))
                user.Password = _hasher.Hash(dto.NewPassword);

            if (!string.IsNullOrWhiteSpace(dto.InstitutionId) && ApplicationRoles.IsSystemAdmin(requester.Role))
                user.InstitutionId = dto.InstitutionId;

            if (!string.IsNullOrWhiteSpace(dto.DepartmentId) || !string.IsNullOrWhiteSpace(dto.Department))
            {
                await ApplyDepartmentAssignmentAsync(user.InstitutionId, dto.DepartmentId ?? dto.Department, user, dto);
            }

            user.UpdatedAt = DateTime.Now;

            await _repo.UpdateAsync(id, user);

            return "User updated successfully";
        }
        // Generates a 6-digit reset code.
        private string GenerateResetCode()
        {
            return new Random().Next(100000, 999999).ToString();
        }
        // Sends a password reset code to the user.
        public async Task<string> ForgotPassword(ForgotPasswordDto dto)
        {
            var user = await _repo.GetByEmailAsync(dto.Email);
            if (user == null)
                throw new NotFoundException("Email not found");

            string code = GenerateResetCode();

            user.ResetCode = code;
            user.ResetCodeExpiry = DateTime.UtcNow.AddMinutes(5);

            await _repo.UpdateAsync(user.Id, user);

            await _email.SendEmailAsync(
                user.Email,
                "Password Reset Code",
                $"Your password reset code is: {code}"
            );

            return "Reset code sent to your email";
        }

        // Resets the password after code validation.
        public async Task<string> ResetPassword(ResetPasswordDto dto)
        {
            var user = await _repo.GetByEmailAsync(dto.Email);
            if (user == null)
                throw new ValidationException("Invalid email");

            if (user.ResetCode != dto.Code)
                throw new ValidationException("Invalid reset code");

            if (user.ResetCodeExpiry < DateTime.UtcNow)
                throw new ValidationException("Reset code expired");

            user.Password = _hasher.Hash(dto.NewPassword);
            user.ResetCode = null;
            user.ResetCodeExpiry = null;

            await _repo.UpdateAsync(user.Id, user);

            return "Password has been reset successfully";
        }

        // Returns the visible users for the current admin.
        public async Task<List<UserDto>> GetUsers(string? role, string? search, string currentUserId)
        {
            var users = await _repo.GetAllAsync();
            var currentUser = await _repo.GetByIdAsync(currentUserId);

            // Exclude the current user from the result.
            users = users.Where(u => u.Id != currentUserId).ToList();

            // Filter by role when requested.
            if (!string.IsNullOrEmpty(role))
            {
                users = users
                        .Where(u => u.Role.Equals(role, StringComparison.OrdinalIgnoreCase))
                        .ToList();
            }

            if (currentUser != null && ApplicationRoles.IsInstitutionAdmin(currentUser.Role))
            {
                users = users
                    .Where(u => string.Equals(u.InstitutionId, currentUser.InstitutionId, StringComparison.OrdinalIgnoreCase))
                    .Where(u => !ApplicationRoles.IsSystemAdmin(u.Role) && !ApplicationRoles.IsInstitutionAdmin(u.Role))
                    .ToList();
            }

            // Filter by name or email.
            if (!string.IsNullOrEmpty(search))
            {
                search = search.ToLower();
                users = users.Where(u =>
                    u.Name.ToLower().Contains(search) ||
                    u.Email.ToLower().Contains(search)
                ).ToList();
            }

            return users.Select(u => new UserDto
            {
                Id = u.Id,
                Name = u.Name,
                Email = u.Email,
                Role = u.Role,
                InstitutionId = u.InstitutionId,
                DepartmentId = u.DepartmentId,
                Department = u.Department
            }).ToList();
        }
        // Creates the configured bootstrap admin when no system admin exists.
        public async Task CreateBootstrapAdminIfNotExists()
        {
            var systemAdminExists = await _repo.GetByRoleAsync(ApplicationRoles.SystemAdmin);
            if (systemAdminExists.Any()) return;

            var name = _config["BootstrapAdmin:Name"];
            var email = _config["BootstrapAdmin:Email"];
            var password = _config["BootstrapAdmin:Password"];

            if (string.IsNullOrWhiteSpace(name) ||
                string.IsNullOrWhiteSpace(email) ||
                string.IsNullOrWhiteSpace(password))
            {
                return;
            }

            var hashed = _hasher.Hash(password);

            await _repo.CreateAsync(new User
            {
                Name = name,
                Email = email,
                Password = hashed,
                Role = ApplicationRoles.SystemAdmin
            });
        }

        // Verifies the submitted 2FA code and issues a token.
        public async Task<AuthResult> VerifyTwoFactorAsync(Verify2FADto dto)
        {
            var user = await _repo.GetByEmailAsync(dto.Email);
            if (user == null)
                throw new NotFoundException("User not found");

            if (user.TwoFactorCode == null || user.TwoFactorExpiry < DateTime.UtcNow)
                throw new ValidationException("Verification code expired");

            if (user.TwoFactorCode != dto.Code)
                throw new ValidationException("Invalid verification code");

            // Clear the one-time code after a successful verification.
            user.TwoFactorCode = null;
            user.TwoFactorExpiry = null;
            string token = _token.GenerateJwtToken(user);

            await _repo.UpdateAsync(user.Id, user);

            await _audit.LogAsync(
                user.Id,
                user.Role,
                "Login2FASuccess",
                null,
                $"User {user.Email} passed 2FA"
            );

            return new AuthResult
            {
                Token = token,
                User = user,
                Requires2FA = false
            };
        }

        private async Task ApplyDepartmentAssignmentAsync(string? institutionId, string? requestedDepartmentId, User? user, AddUserDto dto)
        {
            if (string.IsNullOrWhiteSpace(requestedDepartmentId))
            {
                dto.DepartmentId = null;
                dto.Department = null;
                return;
            }

            if (string.IsNullOrWhiteSpace(institutionId))
                throw new ValidationException("InstitutionId is required when assigning a department");

            var department = await _departments.GetByIdAsync(requestedDepartmentId.Trim());
            if (department == null)
                throw new NotFoundException("Department not found");

            if (!string.Equals(department.InstitutionId, institutionId, StringComparison.OrdinalIgnoreCase))
                throw new ValidationException("Department does not belong to the selected institution");

            dto.DepartmentId = department.Id;
            dto.Department = department.Name;

            if (user != null)
            {
                user.DepartmentId = department.Id;
                user.Department = department.Name;
            }
        }

        private async Task ApplyDepartmentAssignmentAsync(string? institutionId, string? requestedDepartmentId, User user, UpdateUserDto dto)
        {
            if (string.IsNullOrWhiteSpace(requestedDepartmentId))
            {
                user.DepartmentId = null;
                user.Department = null;
                return;
            }

            if (string.IsNullOrWhiteSpace(institutionId))
                throw new ValidationException("InstitutionId is required when assigning a department");

            var department = await _departments.GetByIdAsync(requestedDepartmentId.Trim());
            if (department == null)
                throw new NotFoundException("Department not found");

            if (!string.Equals(department.InstitutionId, institutionId, StringComparison.OrdinalIgnoreCase))
                throw new ValidationException("Department does not belong to the selected institution");

            dto.DepartmentId = department.Id;
            dto.Department = department.Name;
            user.DepartmentId = department.Id;
            user.Department = department.Name;
        }



    }

}
