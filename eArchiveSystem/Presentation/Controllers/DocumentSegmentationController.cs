using System.Security.Claims;
using eArchiveSystem.Application.Segmentation.Abstractions;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;

namespace eArchiveSystem.Presentation.Controllers
{
    [ApiController]
    [Route("api/documents/{id}/segmentation")]
    public class DocumentSegmentationController : ControllerBase
    {
        private readonly IDocumentSegmentationService _documentSegmentationService;

        public DocumentSegmentationController(IDocumentSegmentationService documentSegmentationService)
        {
            _documentSegmentationService = documentSegmentationService;
        }

        [Authorize(Roles = "SystemAdmin,InstitutionAdmin,Manager,Employee")]
        [HttpGet]
        public async Task<IActionResult> GetSegmentation(string id, CancellationToken cancellationToken)
        {
            var userId = GetCurrentUserId();
            if (string.IsNullOrWhiteSpace(userId))
            {
                return Unauthorized();
            }

            var result = await _documentSegmentationService.GetSegmentationAsync(
                id,
                userId,
                cancellationToken);

            return Ok(result);
        }

        [Authorize(Roles = "Manager,Employee")]
        [HttpPost]
        public async Task<IActionResult> StartSegmentation(string id, CancellationToken cancellationToken)
        {
            var userId = GetCurrentUserId();
            if (string.IsNullOrWhiteSpace(userId))
            {
                return Unauthorized();
            }

            var result = await _documentSegmentationService.SegmentDocumentAsync(
                id,
                userId,
                cancellationToken);

            return Ok(result);
        }

        [Authorize(Roles = "Manager,Employee")]
        [HttpPost("retry")]
        public async Task<IActionResult> RetrySegmentation(string id, CancellationToken cancellationToken)
        {
            var userId = GetCurrentUserId();
            if (string.IsNullOrWhiteSpace(userId))
            {
                return Unauthorized();
            }

            var result = await _documentSegmentationService.RetrySegmentationAsync(
                id,
                userId,
                cancellationToken);

            return Ok(result);
        }

        private string? GetCurrentUserId()
        {
            return User.FindFirst(ClaimTypes.NameIdentifier)?.Value
                ?? User.FindFirst("sub")?.Value;
        }
    }
}
