using eArchiveSystem.Application.Interfaces.Services;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;

namespace eArchiveSystem.Presentation.Controllers
{

        [ApiController]
        [Route("api/dashboard")]
        [Authorize(Roles = "SystemAdmin,InstitutionAdmin,Manager")]
        public class DashboardController : ControllerBase
        {
            private readonly IDashboardService _dashboard;

            public DashboardController(IDashboardService dashboard)
            {
                _dashboard = dashboard;
            }

            [HttpGet("totals")]
            public async Task<IActionResult> GetTotals()
            {
                var requesterId = User.FindFirst(System.Security.Claims.ClaimTypes.NameIdentifier)?.Value!;
                var result = new
                {
                    totalDocuments = await _dashboard.GetTotalDocumentsAsync(requesterId),
                    totalUsers = await _dashboard.GetTotalUsersAsync(requesterId),
                    todayUploads = await _dashboard.GetTodayUploadsAsync(requesterId),
                    monthlyUpdates = await _dashboard.GetMonthlyUpdatesAsync(requesterId)
                };

                return Ok(result); 
            }

            [HttpGet("documents-by-department")]
            public async Task<IActionResult> DocumentsByDepartment()
            {
                var requesterId = User.FindFirst(System.Security.Claims.ClaimTypes.NameIdentifier)?.Value!;
                return Ok(await _dashboard.GetDocumentsByDepartmentAsync(requesterId));
            }

            [HttpGet("documents-by-type")]
            public async Task<IActionResult> DocumentsByType() 
            {
                var requesterId = User.FindFirst(System.Security.Claims.ClaimTypes.NameIdentifier)?.Value!;
                return Ok(await _dashboard.GetDocumentsByTypeAsync(requesterId));
            }
        }
    }



