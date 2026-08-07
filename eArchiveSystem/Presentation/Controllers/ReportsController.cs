using eArchiveSystem.Application.Interfaces.Services;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;

namespace eArchiveSystem.Presentation.Controllers
{
    [ApiController]
    [Route("api/reports")]
    // Exposes reporting and export endpoints.
    public class ReportsController : ControllerBase
    {
        private readonly IReportService _reports;

        public ReportsController(IReportService reports)
        {
            _reports = reports;
        }

        // Returns document counts grouped by department.
        [Authorize(Roles = "SystemAdmin,InstitutionAdmin,Manager")]
        [HttpGet("documents-by-department")]
        public async Task<IActionResult> CountByDepartment()
        {
            var requesterId = User.FindFirst(System.Security.Claims.ClaimTypes.NameIdentifier)?.Value!;
            var result = await _reports.GetDocumentsCountByDepartmentAsync(requesterId);
            return Ok(result);
        }

        // Returns document counts grouped by type.
        [Authorize(Roles = "SystemAdmin,InstitutionAdmin,Manager")]
        [HttpGet("documents-by-type")]
        public async Task<IActionResult> CountByType()
        {
            var requesterId = User.FindFirst(System.Security.Claims.ClaimTypes.NameIdentifier)?.Value!;
            var result = await _reports.GetDocumentsCountByTypeAsync(requesterId);
            return Ok(result);
        }

        // Returns user activity metrics.
        [Authorize(Roles = "SystemAdmin,InstitutionAdmin,Manager")]
        [HttpGet("user-activity")]
        public async Task<IActionResult> UserActivity()
        {
            var requesterId = User.FindFirst(System.Security.Claims.ClaimTypes.NameIdentifier)?.Value!;
            var result = await _reports.GetUserActivityReportAsync(requesterId);
            return Ok(result);
        }

        // Returns time-based document metrics.
        [Authorize(Roles = "SystemAdmin,InstitutionAdmin,Manager")]
        [HttpGet("time-report")]
        public async Task<IActionResult> TimeReport()
        {
            var requesterId = User.FindFirst(System.Security.Claims.ClaimTypes.NameIdentifier)?.Value!;
            var result = await _reports.GetTimeReportAsync(requesterId);
            return Ok(result);
        }
        // Exports the department report as Excel.
        [Authorize(Roles = "SystemAdmin,InstitutionAdmin,Manager")]
        [HttpGet("export/department/excel")]
        public async Task<IActionResult> ExportDeptExcel()
        {
            var requesterId = User.FindFirst(System.Security.Claims.ClaimTypes.NameIdentifier)?.Value!;
            var file = await _reports.ExportDepartmentReportExcelAsync(requesterId);
            return File(file,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "DepartmentReport.xlsx");
        }
        // Exports the department report as PDF.
        [Authorize(Roles = "SystemAdmin,InstitutionAdmin,Manager")]
        [HttpGet("export/department/pdf")]
        public async Task<IActionResult> ExportDeptPdf()
        {
            var requesterId = User.FindFirst(System.Security.Claims.ClaimTypes.NameIdentifier)?.Value!;
            var file = await _reports.ExportDepartmentReportPdfAsync(requesterId);
            return File(file,
                "application/pdf",
                "DepartmentReport.pdf");
        }

        // Exports the type report as Excel.
        [Authorize(Roles = "SystemAdmin,InstitutionAdmin,Manager")]
        [HttpGet("export/type/excel")]
        public async Task<IActionResult> ExportTypeExcel()
        {
            var requesterId = User.FindFirst(System.Security.Claims.ClaimTypes.NameIdentifier)?.Value!;
            var file = await _reports.ExportTypeReportExcelAsync(requesterId);
            return File(file,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "DocumentTypeReport.xlsx");
        }
        // Exports the type report as PDF.
        [Authorize(Roles = "SystemAdmin,InstitutionAdmin,Manager")]
        [HttpGet("export/type/pdf")]
        public async Task<IActionResult> ExportTypePdf()
        {
            var requesterId = User.FindFirst(System.Security.Claims.ClaimTypes.NameIdentifier)?.Value!;
            var file = await _reports.ExportTypeReportPdfAsync(requesterId);
            return File(file,
                "application/pdf",
                "DocumentTypeReport.pdf");
        }

        // Exports the user activity report as Excel.
        [Authorize(Roles = "SystemAdmin,InstitutionAdmin,Manager")]
        [HttpGet("export/user-activity/excel")]
        public async Task<IActionResult> ExportUserExcel()
        {
            var requesterId = User.FindFirst(System.Security.Claims.ClaimTypes.NameIdentifier)?.Value!;
            var file = await _reports.ExportUserActivityReportExcelAsync(requesterId);
            return File(file,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "UserActivityReport.xlsx");
        }
        // Exports the user activity report as PDF.
        [Authorize(Roles = "SystemAdmin,InstitutionAdmin,Manager")]
        [HttpGet("export/user-activity/pdf")]
        public async Task<IActionResult> ExportUserPdf()
        {
            var requesterId = User.FindFirst(System.Security.Claims.ClaimTypes.NameIdentifier)?.Value!;
            var file = await _reports.ExportUserActivityReportPdfAsync(requesterId);
            return File(file,
                "application/pdf",
                "UserActivityReport.pdf");
        }
        // Exports all visible documents as Excel.
        [Authorize(Roles = "SystemAdmin,InstitutionAdmin,Manager")]
        [HttpGet("export/all-documents/excel")]
        public async Task<IActionResult> ExportAllDocumentsExcel()
        {
            var requesterId = User.FindFirst(System.Security.Claims.ClaimTypes.NameIdentifier)?.Value!;
            var file = await _reports.ExportAllDocumentsExcelAsync(requesterId);

            return File(
                file,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "AllDocuments.xlsx"
            );
        }
    }

}


