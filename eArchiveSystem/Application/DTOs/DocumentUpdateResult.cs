using eArchiveSystem.Domain.Models;
namespace eArchiveSystem.Application.DTOs
{
    public class DocumentUpdateResult
    {
        public bool Success { get; set; }
        public bool IsDuplicate { get; set; }
        public string? Message { get; set; }
        public Document? Document { get; set; }
        public string? ExistingDocumentId { get; set; }

    }
}
