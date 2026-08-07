using Microsoft.AspNetCore.Http;

namespace eArchiveSystem.Application.Interfaces.Services
{
    public interface IStorageService
    {
        Task<string> SaveFileAsync(IFormFile file, string folderName);
    }
}
