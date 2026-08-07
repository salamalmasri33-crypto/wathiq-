using eArchiveSystem.Application.Interfaces.Services;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Http;

namespace eArchiveSystem.Application.Services
{
    // Saves uploaded files inside the local application folder.
    public class LocalStorageService : IStorageService
    {
        private readonly IWebHostEnvironment _env;

        public LocalStorageService(IWebHostEnvironment env)
        {
            _env = env;
        }

        // Stores the file and returns its relative path.
        public async Task<string> SaveFileAsync(IFormFile file, string folderName)
        {
            // Resolve the current application root.
            var root = Directory.GetCurrentDirectory();

            // Build the target folder path.
            var uploadsPath = Path.Combine(root, folderName);

            // Create the folder when it does not exist.
            if (!Directory.Exists(uploadsPath))
                Directory.CreateDirectory(uploadsPath);

            // Generate a unique file name.
            string uniqueFileName = Guid.NewGuid() + Path.GetExtension(file.FileName);

            // Build the absolute file path.
            string filePath = Path.Combine(uploadsPath, uniqueFileName);

            // Copy the uploaded content to disk.
            using (var fs = new FileStream(filePath, FileMode.Create))
            {
                await file.CopyToAsync(fs);
            }

            // Return the relative path used by the app.
            return Path.Combine(folderName, uniqueFileName);
        }

    }
}
