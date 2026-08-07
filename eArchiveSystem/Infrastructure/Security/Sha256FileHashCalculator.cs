using eArchiveSystem.Application.Interfaces.Security;
using Microsoft.AspNetCore.Http;
using System.Security.Cryptography;
using System.Text;

namespace eArchiveSystem.Infrastructure.Security
{
    public class Sha256FileHashCalculator : IFileHashCalculator
    {
        public async Task<string> ComputeHashAsync(IFormFile file)
        {
            using var sha = SHA256.Create();
            using var stream = file.OpenReadStream();
            var hashBytes = await sha.ComputeHashAsync(stream);
            return BitConverter.ToString(hashBytes).Replace("-", "").ToLowerInvariant();
        }
    }
}
