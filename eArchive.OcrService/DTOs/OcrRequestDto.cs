namespace eArchive.OcrService.DTOs
{
    public class OcrRequestDto
    {
        public string DocumentId { get; set; } = string.Empty;
        public string FilePath { get; set; } = string.Empty;
        public string? CallbackUrl { get; set; }
        public string? Department { get; set; }
    }
}
