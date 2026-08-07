using eArchiveSystem.Application.DTOs;
using eArchiveSystem.Application.Interfaces.Services;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;

namespace eArchiveSystem.Presentation.Controllers
{
    [ApiController]
    [Route("api/documents/{documentId}/workflow")]
    [Authorize]
    public class DocumentWorkflowController : ControllerBase 
    {
        private readonly IDocumentWorkflowService _workflowService; 

        public DocumentWorkflowController(IDocumentWorkflowService workflowService)
        {
            _workflowService = workflowService;
        }

        [HttpPost("submit")] 
        public async Task<IActionResult> Submit(string documentId)
        {
            var userId = User.FindFirst("sub")?.Value ?? User.FindFirst(System.Security.Claims.ClaimTypes.NameIdentifier)?.Value;
            if (string.IsNullOrEmpty(userId))
                return Unauthorized();

            var result = await _workflowService.SubmitDocumentAsync(userId, documentId);
            if (!result.Success)
                return BadRequest(result.Message);

            return Ok(result.Data);
        }

        [HttpPost("start-review")]
        [Authorize(Roles = "Manager")]
        public async Task<IActionResult> StartReview(string documentId)
        {
            var userId = User.FindFirst("sub")?.Value ?? User.FindFirst(System.Security.Claims.ClaimTypes.NameIdentifier)?.Value;
            if (string.IsNullOrEmpty(userId))
                return Unauthorized();

            var result = await _workflowService.StartReviewAsync(userId, documentId);
            if (!result.Success)
                return BadRequest(result.Message);

            return Ok(result.Data);
        }

        [HttpPost("approve")]
        [Authorize(Roles = "Manager")]
        public async Task<IActionResult> Approve(string documentId, [FromBody] ReviewDecisionDto? decision = null)
        {
            var userId = User.FindFirst("sub")?.Value ?? User.FindFirst(System.Security.Claims.ClaimTypes.NameIdentifier)?.Value;
            if (string.IsNullOrEmpty(userId))
                return Unauthorized();

            var result = await _workflowService.ApproveDocumentAsync(userId, documentId, decision);
            if (!result.Success)
                return BadRequest(result.Message);

            return Ok(result.Data);
        }

        [HttpPost("reject")]
        [Authorize(Roles = "Manager")]
        public async Task<IActionResult> Reject(string documentId, [FromBody] ReviewDecisionDto decision)
        {
            var userId = User.FindFirst("sub")?.Value ?? User.FindFirst(System.Security.Claims.ClaimTypes.NameIdentifier)?.Value;
            if (string.IsNullOrEmpty(userId))
                return Unauthorized();

            var result = await _workflowService.RejectDocumentAsync(userId, documentId, decision);
            if (!result.Success)
                return BadRequest(result.Message);

            return Ok(result.Data);
        }

        [HttpPost("publish")]
        [Authorize(Roles = "InstitutionAdmin")]
        public async Task<IActionResult> Publish(string documentId)
        {
            var userId = User.FindFirst("sub")?.Value ?? User.FindFirst(System.Security.Claims.ClaimTypes.NameIdentifier)?.Value;
            if (string.IsNullOrEmpty(userId))
                return Unauthorized();

            var result = await _workflowService.PublishDocumentAsync(userId, documentId);
            if (!result.Success)
                return BadRequest(result.Message);

            return Ok(result.Data);
        }

        [HttpPost("archive")]
        [Authorize(Roles = "InstitutionAdmin")]
        public async Task<IActionResult> Archive(string documentId)
        {
            var userId = User.FindFirst("sub")?.Value ?? User.FindFirst(System.Security.Claims.ClaimTypes.NameIdentifier)?.Value;
            if (string.IsNullOrEmpty(userId))
                return Unauthorized();

            var result = await _workflowService.ArchiveDocumentAsync(userId, documentId);
            if (!result.Success)
                return BadRequest(result.Message);

            return Ok(result.Data);
        }

        [HttpPost("transfer")]
        [Authorize(Roles = "SystemAdmin,InstitutionAdmin,Manager")]
        public async Task<IActionResult> Transfer(string documentId, [FromBody] TransferDocumentDto dto)
        {
            var userId = User.FindFirst("sub")?.Value ?? User.FindFirst(System.Security.Claims.ClaimTypes.NameIdentifier)?.Value;
            if (string.IsNullOrEmpty(userId))
                return Unauthorized();

            var result = await _workflowService.TransferDocumentAsync(userId, documentId, dto);
            if (!result.Success)
                return BadRequest(result.Message);

            return Ok(result.Data);
        }
    }
}
