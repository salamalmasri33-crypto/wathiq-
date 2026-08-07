namespace eArchive.OcrService.DTOs
{
    public class OcrResultDto
    {
        public string Text { get; set; } = string.Empty;
        public string RawText { get; set; } = string.Empty;
        public string NormalizedText { get; set; } = string.Empty;
        public float Confidence { get; set; }
        public string Language { get; set; } = "ara+eng";
        public int Pages { get; set; }
        public string Provider { get; set; } = string.Empty;
    }
}
