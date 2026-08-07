using System.Net.Http.Headers;
using System.Text;
using System.Text.Json;
using eArchive.OcrService.Configuration;
using eArchive.OcrService.Domain.Models;
using Microsoft.Extensions.Options;

namespace eArchive.OcrService.OCR
{
    public class GroqVisionOcrStrategy : IOcrStrategy
    {
        private static readonly JsonSerializerOptions JsonOptions = new(JsonSerializerDefaults.Web);

        private readonly IHttpClientFactory _httpClientFactory;
        private readonly IGroqOcrPromptBuilder _promptBuilder;
        private readonly GroqOptions _options;
        private readonly ILogger<GroqVisionOcrStrategy> _logger;

        public GroqVisionOcrStrategy(
            IHttpClientFactory httpClientFactory,
            IGroqOcrPromptBuilder promptBuilder,
            IOptions<GroqOptions> options,
            ILogger<GroqVisionOcrStrategy> logger)
        {
            _httpClientFactory = httpClientFactory;
            _promptBuilder = promptBuilder;
            _options = options.Value;
            _logger = logger;
        }

        public async Task<OcrExtractionResult> ProcessAsync(IReadOnlyList<string> imagePaths)
        {
            if (string.IsNullOrWhiteSpace(_options.ApiKey))
                throw new InvalidOperationException("Groq API key is not configured.");

            using var client = CreateClient();
            var pageTexts = new List<string>(imagePaths.Count);

            for (var index = 0; index < imagePaths.Count; index++)
            {
                var pageNumber = index + 1;
                var pageText = await ExtractPageTextAsync(client, imagePaths[index], pageNumber);
                pageTexts.Add(pageText);
            }

            return new OcrExtractionResult
            {
                RawText = string.Join(Environment.NewLine + Environment.NewLine, pageTexts),
                Confidence = 0,
                Language = "ara+eng",
                Pages = imagePaths.Count,
                Provider = $"Groq/{_options.Model}"
            };
        }

        private HttpClient CreateClient()
        {
            var client = _httpClientFactory.CreateClient("groq");
            client.BaseAddress = new Uri(AppendTrailingSlash(_options.BaseUrl));
            client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", _options.ApiKey);
            return client;
        }

        private async Task<string> ExtractPageTextAsync(HttpClient client, string imagePath, int pageNumber)
        {
            var requestBody = new
            {
                model = _options.Model,
                temperature = 0,
                reasoning_effort = "none",
                response_format = new { type = "json_object" },
                messages = new object[]
                {
                    new
                    {
                        role = "system",
                        content = _promptBuilder.BuildSystemPrompt()
                    },
                    new
                    {
                        role = "user",
                        content = new object[]
                        {
                            new
                            {
                                type = "text",
                                text = _promptBuilder.BuildUserPrompt(pageNumber)
                            },
                            new
                            {
                                type = "image_url",
                                image_url = new
                                {
                                    url = BuildImageDataUrl(imagePath)
                                }
                            }
                        }
                    }
                }
            };

            using var request = new HttpRequestMessage(HttpMethod.Post, "chat/completions")
            {
                Content = new StringContent(
                    JsonSerializer.Serialize(requestBody, JsonOptions),
                    Encoding.UTF8,
                    "application/json")
            };

            using var response = await client.SendAsync(request);
            var responseBody = await response.Content.ReadAsStringAsync();

            if (!response.IsSuccessStatusCode)
            {
                _logger.LogError(
                    "Groq OCR request failed for page {PageNumber}. Status: {StatusCode}. Response: {ResponseBody}",
                    pageNumber,
                    response.StatusCode,
                    responseBody);

                response.EnsureSuccessStatusCode();
            }

            using var responseJson = JsonDocument.Parse(responseBody);
            var content = responseJson.RootElement
                .GetProperty("choices")[0]
                .GetProperty("message")
                .GetProperty("content")
                .GetString();

            if (string.IsNullOrWhiteSpace(content))
                return string.Empty;

            try
            {
                using var contentJson = JsonDocument.Parse(content);
                return contentJson.RootElement.TryGetProperty("text", out var textNode)
                    ? textNode.GetString() ?? string.Empty
                    : content;
            }
            catch (JsonException)
            {
                return content;
            }
        }

        private static string BuildImageDataUrl(string imagePath)
        {
            var bytes = File.ReadAllBytes(imagePath);
            var mimeType = GetMimeType(imagePath);
            var base64 = Convert.ToBase64String(bytes);
            return $"data:{mimeType};base64,{base64}";
        }

        private static string GetMimeType(string imagePath)
        {
            var extension = Path.GetExtension(imagePath).ToLowerInvariant();

            return extension switch
            {
                ".png" => "image/png",
                ".jpg" => "image/jpeg",
                ".jpeg" => "image/jpeg",
                _ => "application/octet-stream"
            };
        }

        private static string AppendTrailingSlash(string url)
        {
            return url.EndsWith("/", StringComparison.Ordinal) ? url : $"{url}/";
        }
    }
}
