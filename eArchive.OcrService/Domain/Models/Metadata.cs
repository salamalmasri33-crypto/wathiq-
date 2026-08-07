namespace eArchive.OcrService.Domain.Models
{
    public class Metadata
    {
        public string Id { get; set; } = string.Empty;

        public string? Description { get; set; }
        public string? Category { get; set; }
        public string? DocumentType { get; set; }

        public List<string>? Tags { get; set; }

        public string? OcrText { get; set; }
        public string? OcrLanguage { get; set; }
        public float OcrConfidence { get; set; }

        public DateTime CreatedAt { get; set; }
    }
}
