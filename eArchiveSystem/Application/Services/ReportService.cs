using eArchiveSystem.Application.Interfaces.Persistence;
using eArchiveSystem.Application.Interfaces.Services;
using ClosedXML.Excel;
using QuestPDF.Fluent;
using eArchiveSystem.Domain.Models;

using QuestPDF.Infrastructure;

namespace eArchiveSystem.Application.Services
{
    public class ReportService : IReportService
    {
        private readonly IAnalyticsScopeService _scope;

        public ReportService(IAnalyticsScopeService scope)
        {
            _scope = scope;
        }

        // ================================
        // A) COUNT REPORTS
        // ================================

        public async Task<Dictionary<string, int>> GetDocumentsCountByDepartmentAsync(string requesterId)
        {
            var docs = await _scope.GetScopedDocumentsAsync(requesterId);

            return docs
                .GroupBy(d => d.Department)
                .ToDictionary(g => g.Key ?? "Unknown", g => g.Count());
        }

        public async Task<Dictionary<string, int>> GetDocumentsCountByTypeAsync(string requesterId)
        {
            var docs = await _scope.GetScopedDocumentsAsync(requesterId);

            return docs
                .Where(d => d.Metadata?.DocumentType != null)
                .GroupBy(d => d.Metadata.DocumentType)
                .ToDictionary(g => g.Key ?? "Unknown", g => g.Count());
        }

        // ================================
        // B) USER ACTIVITY REPORT
        // ================================

        public async Task<List<Report>> GetUserActivityReportAsync(string requesterId)
        {
            var logs = await _scope.GetScopedAuditLogsAsync(requesterId);

            var report = logs
                .GroupBy(l => l.UserId)
                .Select(g => new Report
                {
                    UserId = g.Key,
                    Uploads = g.Count(x => x.Action == "AddDocument"),
                    Updates = g.Count(x => x.Action == "UpdateDocument"),
                    Deletes = g.Count(x => x.Action == "DeleteDocument"),
                    Searches = g.Count(x => x.Action == "SearchDocuments"),
                    Downloads = g.Count(x => x.Action == "DownloadDocument")
                })
                .ToList();

            return report;
        }

        // ================================
        // C) TIME REPORT
        // ================================

        public async Task<object> GetTimeReportAsync(string requesterId)
        {
            var logs = await _scope.GetScopedAuditLogsAsync(requesterId);

            return logs
                .GroupBy(l => l.Timestamp.Date)
                .Select(g => new
                {
                    Date = g.Key,
                    Added = g.Count(x => x.Action == "AddDocument"),
                    Updated = g.Count(x => x.Action == "UpdateDocument"),
                    Searches = g.Count(x => x.Action == "SearchDocuments")
                })
                .ToList();
        }

        // ================================
        // D) EXPORT - DEPARTMENT
        // ================================

        public async Task<byte[]> ExportDepartmentReportExcelAsync(string requesterId)
        {
            var data = await GetDocumentsCountByDepartmentAsync(requesterId);

            using var workbook = new XLWorkbook();
            var sheet = workbook.Worksheets.Add("Departments");

            sheet.Cell(1, 1).Value = "Department";
            sheet.Cell(1, 2).Value = "Documents Count";

            int row = 2;

            foreach (var item in data)
            {
                sheet.Cell(row, 1).Value = item.Key;
                sheet.Cell(row, 2).Value = item.Value;
                row++;
            }

            using var stream = new MemoryStream();
            workbook.SaveAs(stream);
            return stream.ToArray();
        }

        public async Task<byte[]> ExportDepartmentReportPdfAsync(string requesterId)
        {
            var data = await GetDocumentsCountByDepartmentAsync(requesterId);

            var pdf = QuestPDF.Fluent.Document.Create(container =>

            {
                container.Page(page =>
                {
                    page.Margin(40);

                    page.Header().Text("Documents by Department").FontSize(20).Bold();

                    page.Content().Table(table =>
                    {
                        table.ColumnsDefinition(cols =>
                        {
                            cols.RelativeColumn();
                            cols.RelativeColumn();
                        });

                        table.Header(h =>
                        {
                            h.Cell().Text("Department").Bold();
                            h.Cell().Text("Count").Bold();
                        });

                        foreach (var item in data)
                        {
                            table.Cell().Text(item.Key);
                            table.Cell().Text(item.Value.ToString());
                        }
                    });

                    page.Footer().AlignRight().Text($"Generated: {DateTime.Now}");
                });
            });

            return pdf.GeneratePdf();
        }

        // ================================
        // E) EXPORT - TYPE
        // ================================

        public async Task<byte[]> ExportTypeReportExcelAsync(string requesterId)
        {
            var data = await GetDocumentsCountByTypeAsync(requesterId);

            using var workbook = new XLWorkbook();
            var sheet = workbook.Worksheets.Add("Document Types");

            sheet.Cell(1, 1).Value = "Document Type";
            sheet.Cell(1, 2).Value = "Count";

            int row = 2;

            foreach (var item in data)
            {
                sheet.Cell(row, 1).Value = item.Key;
                sheet.Cell(row, 2).Value = item.Value;
                row++;
            }

            using var stream = new MemoryStream();
            workbook.SaveAs(stream);
            return stream.ToArray();
        }

        public async Task<byte[]> ExportTypeReportPdfAsync(string requesterId)
        {
            var data = await GetDocumentsCountByTypeAsync(requesterId);

            var pdf = QuestPDF.Fluent.Document.Create(container =>

            {
                container.Page(page =>
                {
                    page.Margin(40);

                    page.Header().Text("Documents by Type").FontSize(20).Bold();

                    page.Content().Table(table =>
                    {
                        table.ColumnsDefinition(cols =>
                        {
                            cols.RelativeColumn();
                            cols.RelativeColumn();
                        });

                        table.Header(h =>
                        {
                            h.Cell().Text("Type").Bold();
                            h.Cell().Text("Count").Bold();
                        });

                        foreach (var item in data)
                        {
                            table.Cell().Text(item.Key);
                            table.Cell().Text(item.Value.ToString());
                        }
                    });

                    page.Footer().AlignRight().Text($"Generated: {DateTime.Now}");
                });
            });

            return pdf.GeneratePdf();
        }

        // ================================
        // F) EXPORT - USER ACTIVITY
        // ================================

        public async Task<byte[]> ExportUserActivityReportExcelAsync(string requesterId)
        {
            var list = await GetUserActivityReportAsync(requesterId);

            using var workbook = new XLWorkbook();
            var sheet = workbook.Worksheets.Add("User Activity");

            sheet.Cell(1, 1).Value = "User ID";
            sheet.Cell(1, 2).Value = "Uploads";
            sheet.Cell(1, 3).Value = "Updates";
            sheet.Cell(1, 4).Value = "Deletes";
            sheet.Cell(1, 5).Value = "Searches";
            sheet.Cell(1, 6).Value = "Downloads";

            int row = 2;

            foreach (var item in list)
            {
                sheet.Cell(row, 1).Value = item.UserId;
                sheet.Cell(row, 2).Value = item.Uploads;
                sheet.Cell(row, 3).Value = item.Updates;
                sheet.Cell(row, 4).Value = item.Deletes;
                sheet.Cell(row, 5).Value = item.Searches;
                sheet.Cell(row, 6).Value = item.Downloads;
                row++;
            }

            using var stream = new MemoryStream();
            workbook.SaveAs(stream);
            return stream.ToArray();
        }

        public async Task<byte[]> ExportUserActivityReportPdfAsync(string requesterId)
        {
            var list = await GetUserActivityReportAsync(requesterId);

            var pdf = QuestPDF.Fluent.Document.Create(container =>

            {
                container.Page(page =>
                {
                    page.Margin(40);
                    page.Header().Text("User Activity Report").FontSize(20).Bold();

                    page.Content().Table(table =>
                    {
                        table.ColumnsDefinition(cols =>
                        {
                            cols.RelativeColumn(); // User ID
                            cols.RelativeColumn(); // Uploads
                            cols.RelativeColumn(); // Updates
                            cols.RelativeColumn(); // Deletes
                            cols.RelativeColumn(); // Searches
                            cols.RelativeColumn(); // Downloads
                        });

                        table.Header(h =>
                        {
                            h.Cell().Text("User ID").Bold();
                            h.Cell().Text("Uploads").Bold();
                            h.Cell().Text("Updates").Bold();
                            h.Cell().Text("Deletes").Bold();
                            h.Cell().Text("Searches").Bold();
                            h.Cell().Text("Downloads").Bold();
                        });

                        foreach (var item in list)
                        {
                            table.Cell().Text(item.UserId);
                            table.Cell().Text(item.Uploads.ToString());
                            table.Cell().Text(item.Updates.ToString());
                            table.Cell().Text(item.Deletes.ToString());
                            table.Cell().Text(item.Searches.ToString());
                            table.Cell().Text(item.Downloads.ToString());
                        }
                    });

                    page.Footer().AlignRight().Text($"Generated: {DateTime.Now}");
                });
            });

            return pdf.GeneratePdf();
        }

        public async Task<byte[]> ExportAllDocumentsExcelAsync(string requesterId)
        {
            var docs = await _scope.GetScopedDocumentsAsync(requesterId);

            using var workbook = new XLWorkbook();
            var sheet = workbook.Worksheets.Add("All Documents");

            // Header Row
            sheet.Cell(1, 1).Value = "Document ID";
            sheet.Cell(1, 2).Value = "Title";
            sheet.Cell(1, 3).Value = "Department";
            sheet.Cell(1, 4).Value = "Type";
            sheet.Cell(1, 5).Value = "Created At";
            sheet.Cell(1, 6).Value = "Owner";

            int row = 2;

            foreach (var d in docs)
            {
                sheet.Cell(row, 1).Value = d.Id;
                sheet.Cell(row, 2).Value = d.Title ?? "";
                sheet.Cell(row, 3).Value = d.Department ?? "Unknown";
                sheet.Cell(row, 4).Value = d.Metadata?.DocumentType ?? "Unknown";
                sheet.Cell(row, 5).Value = d.CreatedAt.ToString("yyyy-MM-dd HH:mm");
                sheet.Cell(row, 6).Value = d.UserId;
                row++;
            }

            using var stream = new MemoryStream();
            workbook.SaveAs(stream);
            return stream.ToArray();
        }

    }
}
