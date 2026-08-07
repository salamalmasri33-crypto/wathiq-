using eArchiveSystem.Application.DTOs;
using eArchiveSystem.Application.Exceptions;
using eArchiveSystem.Application.Interfaces.Persistence;
using eArchiveSystem.Application.Interfaces.Services;
using eArchiveSystem.Application.Segmentation.Abstractions;
using eArchiveSystem.Domain.Models;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;

namespace eArchiveSystem.Presentation.Controllers
{
    [ApiController]
    [Route("api/ocr")]
    public class OcrCallbackController : ControllerBase
    {
        private readonly IDocumentRepository _documents;
        private readonly ITextPreprocessorService _preprocessor;
        private readonly IIndexingService _indexingService;
        private readonly IDocumentSegmentationService _documentSegmentationService;
        private readonly ILogger<OcrCallbackController> _logger;

        public OcrCallbackController(
            IDocumentRepository documents,
            ITextPreprocessorService preprocessor,
            IIndexingService indexingService,
            IDocumentSegmentationService documentSegmentationService,
            ILogger<OcrCallbackController> logger)
        {
            _documents = documents;
            _preprocessor = preprocessor;
            _indexingService = indexingService;
            _documentSegmentationService = documentSegmentationService;
            _logger = logger;
        }

        [AllowAnonymous]
        [HttpPost("callback")]
        public async Task<IActionResult> ReceiveResult(
            [FromQuery] string documentId,
            [FromBody] OcrCallbackDto result)
        {
            var doc = await _documents.GetByIdAsync(documentId);
            if (doc == null)
                return NotFound();

            var normalizedText = string.IsNullOrWhiteSpace(result.NormalizedText)
                ? result.Text
                : result.NormalizedText;

            var rawText = string.IsNullOrWhiteSpace(result.RawText)
                ? normalizedText
                : result.RawText;

            var cleaned = _preprocessor.Clean(normalizedText);

            await _documents.UpdateContentAsync(
                documentId,
                cleaned,
                rawText,
                normalizedText,
                result.Provider,
                result.Language,
                result.Pages,
                doc.Department,
                doc.DepartmentId ?? doc.Department
            );

            // Move the document out of Processing as soon as OCR text is safely stored.
            await _documents.UpdateStatusAsync(documentId, DocumentStatus.Draft);

            // Search indexing can run after the status change without blocking manual metadata save.
            await _indexingService.SyncDocumentAsync(documentId);

            await TryProcessAutomaticSegmentationAsync(documentId);

            return Ok("OCR text stored successfully");
        }

        private async Task TryProcessAutomaticSegmentationAsync(string documentId)
        {
            try
            {
                await _documentSegmentationService.ProcessStoredDocumentAsync(documentId);
            }
            catch (AraSegClientException exception)
            {
                _logger.LogWarning(
                    "Automatic segmentation failed for document {DocumentId} with error code {ErrorCode}",
                    documentId,
                    exception.ErrorCode ?? "ARASEG_ERROR");
            }
            catch (ApiException exception)
            {
                _logger.LogWarning(
                    "Automatic segmentation failed for document {DocumentId}: {Message}",
                    documentId,
                    exception.Message);
            }
            catch (Exception)
            {
                _logger.LogError(
                    "Automatic segmentation failed unexpectedly for document {DocumentId}",
                    documentId);
            }
        }
    }
}
