using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.Authorization;
using eArchiveSystem.Application.Interfaces.Services;

namespace eArchiveSystem.Presentation.Controllers
{
    [ApiController]
    [Route("api/audit")]
    // Returns audit logs for authorized roles.
    public class AuditController : ControllerBase
    {
        private readonly IAuditService _audit;

        public AuditController(IAuditService audit)
        {
            _audit = audit;
        }

        // Keeps audit access limited to the roles that already use this screen.
        [Authorize(Roles = "SystemAdmin,InstitutionAdmin,Manager")]
        [HttpGet]
        public async Task<IActionResult> GetAuditLogs()
        {
            var requesterId = User.FindFirst(System.Security.Claims.ClaimTypes.NameIdentifier)?.Value!;
            var logs = await _audit.GetAllWithUsersAsync(requesterId);
            return Ok(logs);
        }
    }
}
