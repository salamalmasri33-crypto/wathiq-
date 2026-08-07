using eArchiveSystem.Domain.Models;

namespace eArchiveSystem.Application.DTOs
{
    public class AuthResult
    {
        public string Token { get; set; }
        public User User { get; set; }
        public bool Requires2FA { get; set; }
        public string? Message { get; set; }
    }
}
