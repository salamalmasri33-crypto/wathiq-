using eArchiveSystem.Domain.Models;

namespace eArchiveSystem.Application.DTOs
{
    public class DocumentAddResult
    {
        public string? DocumentId { get; set; } = string.Empty;
        public string Message { get; set; } = "Uploaded successfully";
        public bool IsDuplicate { get; set; }
        public string? DuplicateDocumentId { get; set; }
        public Document? Document { get; set; }

    }
}
