using eArchiveSystem.Domain.Models;

namespace eArchiveSystem.Application.DTOs
{
    public class SearchDocumentsDto
    {
        public string? Query { get; set; }       // Search text.
        public string? InstitutionId { get; set; }
        public string? BroadGenre { get; set; }
        public string? SpecificGenre { get; set; }
        public string? Department { get; set; }
        public string? DepartmentId { get; set; }
        public DocumentStatus? Status { get; set; } // Optional status filter.
        public DocumentPriority? Priority { get; set; }
        public DateTime? FromDate { get; set; }
        public DateTime? ToDate { get; set; } 
        public string? SortBy { get; set; }      // Sort field such as Title or CreatedAt.
        public bool Desc { get; set; } = false;  // Sort in descending order.
        public int Page { get; set; } = 1;
        public int PageSize { get; set; } = 10;
    }
}
