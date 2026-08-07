using eArchiveSystem.Application.DTOs;
using eArchiveSystem.Application.Interfaces.Services;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using System.Security.Claims;

namespace eArchiveSystem.Presentation.Controllers
{
    [ApiController]
    [Route("api/institution-settings")]
    [Authorize(Roles = "SystemAdmin,InstitutionAdmin")]
    public class InstitutionSettingsController : ControllerBase
    {
        private readonly IInstitutionSettingsService _settings;

        public InstitutionSettingsController(IInstitutionSettingsService settings)
        {
            _settings = settings;
        }

        [HttpGet]
        public async Task<IActionResult> Get([FromQuery] string? institutionId = null)
        {
            var requesterId = User.FindFirst(ClaimTypes.NameIdentifier)?.Value!;
            var result = await _settings.GetSettingsAsync(requesterId, institutionId);
            return Ok(result);
        }

        [HttpPut]
        public async Task<IActionResult> Update([FromBody] UpdateInstitutionSettingsDto dto)
        {
            var requesterId = User.FindFirst(ClaimTypes.NameIdentifier)?.Value!;
            var result = await _settings.UpdateSettingsAsync(requesterId, dto);
            return Ok(result);
        }
    }
}
