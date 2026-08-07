namespace eArchiveSystem.Application.DTOs
{
    public class OcrResultDto
    {
        public string? Description { get; set; }
        public string Text { get; set; } = string.Empty;
        public float Confidence { get; set; }
        public string Language { get; set; } = "ara+eng";
        public int Pages { get; set; }
        public string DocumentType { get; set; }
        public List<string> Tags { get; set; } = [];
        public string? Department { get; set; }
        public DateTime? ExpirationDate { get; set; }
    }
}
