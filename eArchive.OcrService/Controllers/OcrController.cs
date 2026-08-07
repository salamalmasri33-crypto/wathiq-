using eArchive.OcrService.DTOs;
using eArchive.OcrService.Services;
using Microsoft.AspNetCore.Mvc;
using System.Net.Http.Json;

namespace eArchive.OcrService.Controllers
{
    [ApiController]
    [Route("api/ocr")]
    public class OcrController : ControllerBase
    {
        private readonly OcrProcessor _processor;
        private readonly IHttpClientFactory _httpClientFactory;
        private readonly ILogger<OcrController> _logger;

        public OcrController(
            OcrProcessor processor,
            IHttpClientFactory httpClientFactory,
            ILogger<OcrController> logger)
        {
            _processor = processor;
            _httpClientFactory = httpClientFactory;
            _logger = logger;
        }

        [HttpPost("process")]
        public async Task<IActionResult> Process([FromBody] OcrRequestDto dto)
        {
            if (string.IsNullOrWhiteSpace(dto.FilePath))
                return BadRequest("FilePath is missing");

            if (string.IsNullOrWhiteSpace(dto.CallbackUrl))
                return BadRequest("CallbackUrl is missing");

            OcrResultDto result;

            try
            {
                result = await _processor.ProcessAsync(dto);
            }
            catch (FileNotFoundException exception)
            {
                _logger.LogWarning(
                    exception,
                    "OCR source file was not found for document {DocumentId}",
                    dto.DocumentId);

                return BadRequest(exception.Message);
            }

            var client = _httpClientFactory.CreateClient("callback");
            var callbackResponse = await client.PostAsJsonAsync(dto.CallbackUrl, result);
            callbackResponse.EnsureSuccessStatusCode();

            _logger.LogInformation(
                "OCR callback sent successfully for document {DocumentId} using provider {Provider}",
                dto.DocumentId,
                result.Provider);

            return Ok();
        }
    }
}
