using eArchiveSystem.Domain.Models;
using Microsoft.AspNetCore.Http;

namespace eArchiveSystem.Application.DTOs
{
    public class AddDocumentDto
    {
        public string? Title { get; set; }
        public IFormFile File { get; set; } = default!;
        public string? TargetUserId { get; set; }
        public bool EnableOcr { get; set; }
        public DocumentPriority? Priority { get; set; }
        public bool IsSensitive { get; set; }
    }
}
