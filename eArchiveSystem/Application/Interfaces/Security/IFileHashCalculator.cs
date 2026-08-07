using Microsoft.AspNetCore.Http;
using System.Threading.Tasks;

namespace eArchiveSystem.Application.Interfaces.Security
{
    public interface IFileHashCalculator
    {
        Task<string> ComputeHashAsync(IFormFile file);
    }
}
