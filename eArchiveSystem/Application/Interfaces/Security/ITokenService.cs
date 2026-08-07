using eArchiveSystem.Domain.Models;

namespace eArchiveSystem.Application.Interfaces.Security
{
    public interface ITokenService
    {
        string GenerateJwtToken(User user);
    }
}
