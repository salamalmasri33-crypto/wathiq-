namespace eArchiveSystem.Application.DTOs
{
    public class DocumentSentenceDto
    {
        public int Index { get; set; }
        public string Text { get; set; } = string.Empty;
        public int StartToken { get; set; }
        public int EndToken { get; set; }
    }
}
