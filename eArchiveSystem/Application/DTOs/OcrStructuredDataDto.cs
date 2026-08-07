namespace eArchiveSystem.Application.DTOs
{
    public class OcrStructuredDataDto
    {
        public string? Summary { get; set; }
        public string? IssuingEntity { get; set; }
        public string? ReferenceNumber { get; set; }
        public DateTime? DocumentDate { get; set; }
        public List<string>? Keywords { get; set; }
        public List<string>? Insights { get; set; }
        public List<string>? Headers { get; set; }
        public List<string>? Footers { get; set; }
        public List<string>? Stamps { get; set; }
        public List<string>? Signatures { get; set; }
        public bool? HasSignature { get; set; }
    }
}
