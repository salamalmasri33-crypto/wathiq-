using eArchiveSystem.Application.Interfaces.Security;
using eArchiveSystem.Domain.Models;
using Microsoft.Extensions.Configuration;
using Microsoft.IdentityModel.Tokens;
using System.IdentityModel.Tokens.Jwt;
using System.Security.Claims;
using System.Text;

namespace eArchiveSystem.Infrastructure.Security
{
    public class JwtTokenService : ITokenService
    {
        private readonly IConfiguration _config;

        public JwtTokenService(IConfiguration config)
        {
            _config = config;
        }

        public string GenerateJwtToken(User user)
        {
            var configuredKey = _config["Jwt:Key"];
            if (string.IsNullOrWhiteSpace(configuredKey))
            {
                configuredKey = Environment.GetEnvironmentVariable("JWT__KEY");
            }

            if (string.IsNullOrWhiteSpace(configuredKey))
            {
                configuredKey = "Wathiq_Local_Development_Key_Change_Me_2026";
            }

            var key = Encoding.UTF8.GetBytes(configuredKey);

            var claims = new[]
            {
                new Claim(ClaimTypes.NameIdentifier, user.Id),
                new Claim("email", user.Email),
                new Claim(ClaimTypes.Role, user.Role),
                new Claim("institutionId", user.InstitutionId ?? string.Empty),
                new Claim("departmentId", user.DepartmentId ?? user.Department ?? string.Empty),
                new Claim("department", user.Department ?? string.Empty)
            };


            var creds = new SigningCredentials(
                new SymmetricSecurityKey(key),
                SecurityAlgorithms.HmacSha256
            );

            var token = new JwtSecurityToken(
                issuer: _config["Jwt:Issuer"],
                audience: _config["Jwt:Audience"],
                claims: claims,
                expires: DateTime.UtcNow.AddHours(3),
                signingCredentials: creds
            );

            return new JwtSecurityTokenHandler().WriteToken(token);
        }
    }
}
