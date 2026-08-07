using eArchiveSystem.Domain.Models;

namespace eArchiveSystem.Application.DTOs
{
    public class MetadataPreviewDto
    {
        public string DocumentId { get; set; } = string.Empty;
        public string Title { get; set; } = string.Empty;
        public DocumentStatus Status { get; set; }
        public bool HasExtractedText { get; set; }
        public bool HasSavedMetadata { get; set; }

        public string? Description { get; set; }
        public string? BroadGenre { get; set; }
        public string? SpecificGenre { get; set; }
        public string GenreClassificationStatus { get; set; } = "NotRequested";
        public string? GenreClassificationMessage { get; set; }
        public List<string>? Tags { get; set; }
        public string? Department { get; set; }
        public string? DepartmentId { get; set; }
        public string? DocumentType { get; set; }
        public DateTime? ExpirationDate { get; set; }
        public string? IssuingEntity { get; set; }
        public string? ReferenceNumber { get; set; }
        public DateTime? DocumentDate { get; set; }
        public List<string>? Insights { get; set; }
        public bool HasSignature { get; set; }
        public List<string>? Signatures { get; set; }
        public List<string>? Headers { get; set; }
        public List<string>? Footers { get; set; }
        public List<string>? Stamps { get; set; }
        public string? RawExtractionJson { get; set; }

        public bool StructuredDataProvided { get; set; }
        public bool CoreFieldsComplete { get; set; }
        public bool AdvancedMetadataComplete { get; set; }
        public bool LayoutAnalysisAvailable { get; set; }
        public bool RequiresReview { get; set; }
        public string ExtractionStatus { get; set; } = "NeedsReview";
        public List<string> MissingFields { get; set; } = new();
    }
}
