namespace eArchiveSystem.Application.DTOs
{
    public class AddMetadataDto
    {
        public string? Description { get; set; }
        public string? BroadGenre { get; set; }
        public string? SpecificGenre { get; set; }
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
    }
}
