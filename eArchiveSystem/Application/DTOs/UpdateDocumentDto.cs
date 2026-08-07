using eArchiveSystem.Domain.Models;
using Microsoft.AspNetCore.Http;

namespace eArchiveSystem.Application.DTOs
{
    public class UpdateDocumentDto
    {
        public string? Title { get; set; }
        public IFormFile? File { get; set; }
        public DocumentPriority? Priority { get; set; }
        public bool? IsSensitive { get; set; }
    }
}
