namespace eArchive.OcrService.Configuration
{
    public class GroqOptions
    {
        public string BaseUrl { get; set; } = "https://api.groq.com/openai/v1/";
        public string ApiKey { get; set; } = string.Empty;
        public string Model { get; set; } = "meta-llama/llama-4-scout-17b-16e-instruct";
    }
}
