using System.Security.Claims;
using eArchiveSystem.Application.Interfaces.Services;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;

namespace eArchiveSystem.Presentation.Controllers
{
    [ApiController]
    [Route("api/permissions")]
    [Authorize]
    public class PermissionsController : ControllerBase
    {
        private readonly IPermissionReviewService _permissionReviewService;

        public PermissionsController(IPermissionReviewService permissionReviewService)
        {
            _permissionReviewService = permissionReviewService;
        }

        [HttpGet("coverage")]
        public async Task<IActionResult> Coverage()
        {
            var result = await _permissionReviewService.GetCoverageAsync();
            return Ok(result);
        }

        [HttpGet("me")]
        public async Task<IActionResult> Me()
        {
            var userId = User.FindFirst(ClaimTypes.NameIdentifier)?.Value!;
            var result = await _permissionReviewService.GetCurrentScopeAsync(userId);
            return Ok(result);
        }

        [HttpGet("documents/{documentId}")]
        public async Task<IActionResult> CheckDocumentAccess(string documentId)
        {
            var userId = User.FindFirst(ClaimTypes.NameIdentifier)?.Value!;
            var result = await _permissionReviewService.CheckDocumentAccessAsync(userId, documentId);
            return Ok(result);
        }
    }
}
