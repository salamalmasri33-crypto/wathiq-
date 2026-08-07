namespace eArchiveSystem.Application.DTOs
{
    public class OcrCallbackDto
    {
        public string Text { get; set; } = string.Empty;
        public string RawText { get; set; } = string.Empty;
        public string NormalizedText { get; set; } = string.Empty;
        public string Language { get; set; } = "ara+eng";
        public int Pages { get; set; }
        public string Provider { get; set; } = string.Empty;
        public OcrStructuredDataDto? StructuredData { get; set; }
        public string? RawJson { get; set; }
    }
}
