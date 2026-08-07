namespace eArchive.OcrService.OCR
{
    public class GroqOcrPromptBuilder : IGroqOcrPromptBuilder
    {
        public string BuildSystemPrompt()
        {
            return """
                You are a precise OCR engine.
                Extract the text exactly as it appears in the image.
                Preserve Arabic and English text, punctuation, line breaks, and mixed numerals.
                Do not summarize, translate, explain, or correct wording.
                Return valid JSON only in this shape: {"text":"..."}.
                If no text is visible, return {"text":""}.
                """;
        }

        public string BuildUserPrompt(int pageNumber)
        {
            return $"""
                Perform OCR for page {pageNumber}.
                Return only the extracted raw text in the required JSON format.
                """;
        }
    }
}
