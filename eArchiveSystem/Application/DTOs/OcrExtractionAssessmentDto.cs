namespace eArchiveSystem.Application.DTOs
{
    public class OcrExtractionAssessmentDto
    {
        public bool StructuredDataProvided { get; set; }
        public bool CoreFieldsComplete { get; set; }
        public bool AdvancedMetadataComplete { get; set; }
        public bool LayoutAnalysisAvailable { get; set; }
        public bool RequiresReview { get; set; }
        public string ExtractionStatus { get; set; } = "NeedsReview";
        public List<string> MissingFields { get; set; } = new();
    }
}
