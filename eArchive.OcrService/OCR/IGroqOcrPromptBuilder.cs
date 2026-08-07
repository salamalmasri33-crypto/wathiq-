namespace eArchive.OcrService.OCR
{
    public interface IGroqOcrPromptBuilder
    {
        string BuildSystemPrompt();
        string BuildUserPrompt(int pageNumber);
    }
}
