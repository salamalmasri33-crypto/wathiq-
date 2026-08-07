using System.Drawing;
using System.Drawing.Imaging;
using eArchiveSystem.Application.Interfaces.Services;
using eArchiveSystem.Domain.Models;
using PdfiumViewer;
using QuestPDF.Fluent;
using ArchiveDocument = eArchiveSystem.Domain.Models.Document;

namespace eArchiveSystem.Application.Services
{
    public class DocumentWatermarkService : IDocumentWatermarkService
    {
        public Task<(Stream FileStream, string FileName, string ContentType)> PrepareDownloadAsync(
            ArchiveDocument document,
            User actor,
            string sourcePath)
        {
            if (!document.IsSensitive)
            {
                return Task.FromResult(OpenOriginal(document, sourcePath));
            }

            return Task.FromResult(PrepareSensitiveDownload(document, actor, sourcePath));
        }

        private (Stream FileStream, string FileName, string ContentType) PrepareSensitiveDownload(
            ArchiveDocument document,
            User actor,
            string sourcePath)
        {
            if (IsPdf(document))
                return CreateWatermarkedPdf(document, actor, sourcePath);

            if (IsImage(document))
                return CreateWatermarkedImage(document, actor, sourcePath);

            return OpenOriginal(document, sourcePath);
        }

        private static (Stream FileStream, string FileName, string ContentType) CreateWatermarkedPdf(
            ArchiveDocument document,
            User actor,
            string sourcePath)
        {
            var watermarkText = BuildWatermarkText(actor);
            var pageImages = RenderWatermarkedPdfPages(sourcePath, watermarkText);

            var pdfBytes = QuestPDF.Fluent.Document.Create(container =>
            {
                foreach (var pageImage in pageImages)
                {
                    container.Page(page =>
                    {
                        page.Margin(0);
                        page.Content().Image(pageImage).FitArea();
                    });
                }
            }).GeneratePdf();

            return (new MemoryStream(pdfBytes), document.FileName, "application/pdf");
        }

        private static (Stream FileStream, string FileName, string ContentType) CreateWatermarkedImage(
            ArchiveDocument document,
            User actor,
            string sourcePath)
        {
            using var sourceImage = Image.FromFile(sourcePath);
            using var bitmap = new Bitmap(sourceImage);

            ApplyWatermark(bitmap, BuildWatermarkText(actor));

            var output = new MemoryStream();
            var imageFormat = ResolveImageFormat(document.ContentType, document.FileName);
            bitmap.Save(output, imageFormat);
            output.Position = 0;

            return (output, document.FileName, NormalizeImageContentType(document.ContentType, document.FileName));
        }

        private static List<byte[]> RenderWatermarkedPdfPages(string sourcePath, string watermarkText)
        {
            var pageImages = new List<byte[]>();

            using var pdf = PdfDocument.Load(sourcePath);

            for (var pageIndex = 0; pageIndex < pdf.PageCount; pageIndex++)
            {
                using var renderedPage = pdf.Render(pageIndex, 220, 220, PdfRenderFlags.CorrectFromDpi);
                using var bitmap = new Bitmap(renderedPage);

                ApplyWatermark(bitmap, watermarkText);

                using var pageStream = new MemoryStream();
                bitmap.Save(pageStream, ImageFormat.Png);
                pageImages.Add(pageStream.ToArray());
            }

            return pageImages;
        }

        private static void ApplyWatermark(Bitmap bitmap, string watermarkText)
        {
            using var graphics = Graphics.FromImage(bitmap);
            graphics.SmoothingMode = System.Drawing.Drawing2D.SmoothingMode.AntiAlias;
            graphics.InterpolationMode = System.Drawing.Drawing2D.InterpolationMode.HighQualityBicubic;

            var fontSize = Math.Max(24f, bitmap.Width / 18f);
            using var font = new Font("Arial", fontSize, FontStyle.Bold, GraphicsUnit.Pixel);
            using var brush = new SolidBrush(Color.FromArgb(70, 180, 0, 0));
            using var format = new StringFormat
            {
                Alignment = StringAlignment.Center,
                LineAlignment = StringAlignment.Center
            };

            graphics.TranslateTransform(bitmap.Width / 2f, bitmap.Height / 2f);
            graphics.RotateTransform(-30f);

            var diagonal = (float)Math.Sqrt(bitmap.Width * bitmap.Width + bitmap.Height * bitmap.Height);
            var stepX = Math.Max(300f, bitmap.Width / 2f);
            var stepY = Math.Max(220f, bitmap.Height / 3f);

            for (var x = -diagonal; x <= diagonal; x += stepX)
            {
                for (var y = -diagonal; y <= diagonal; y += stepY)
                {
                    graphics.DrawString(watermarkText, font, brush, new PointF(x, y), format);
                }
            }

            graphics.ResetTransform();
        }

        private static string BuildWatermarkText(User actor)
        {
            return $"SENSITIVE COPY\n{actor.Name}\n{actor.Email}\n{DateTime.UtcNow:yyyy-MM-dd HH:mm} UTC";
        }

        private static bool IsPdf(ArchiveDocument document)
        {
            return string.Equals(document.ContentType, "application/pdf", StringComparison.OrdinalIgnoreCase) ||
                   Path.GetExtension(document.FileName).Equals(".pdf", StringComparison.OrdinalIgnoreCase);
        }

        private static bool IsImage(ArchiveDocument document)
        {
            var extension = Path.GetExtension(document.FileName);

            return string.Equals(document.ContentType, "image/png", StringComparison.OrdinalIgnoreCase) ||
                   string.Equals(document.ContentType, "image/jpeg", StringComparison.OrdinalIgnoreCase) ||
                   string.Equals(document.ContentType, "image/jpg", StringComparison.OrdinalIgnoreCase) ||
                   extension.Equals(".png", StringComparison.OrdinalIgnoreCase) ||
                   extension.Equals(".jpg", StringComparison.OrdinalIgnoreCase) ||
                   extension.Equals(".jpeg", StringComparison.OrdinalIgnoreCase);
        }

        private static ImageFormat ResolveImageFormat(string contentType, string fileName)
        {
            var extension = Path.GetExtension(fileName);

            if (string.Equals(contentType, "image/jpeg", StringComparison.OrdinalIgnoreCase) ||
                string.Equals(contentType, "image/jpg", StringComparison.OrdinalIgnoreCase) ||
                extension.Equals(".jpg", StringComparison.OrdinalIgnoreCase) ||
                extension.Equals(".jpeg", StringComparison.OrdinalIgnoreCase))
            {
                return ImageFormat.Jpeg;
            }

            return ImageFormat.Png;
        }

        private static string NormalizeImageContentType(string contentType, string fileName)
        {
            var extension = Path.GetExtension(fileName);

            if (string.Equals(contentType, "image/jpeg", StringComparison.OrdinalIgnoreCase) ||
                string.Equals(contentType, "image/jpg", StringComparison.OrdinalIgnoreCase) ||
                extension.Equals(".jpg", StringComparison.OrdinalIgnoreCase) ||
                extension.Equals(".jpeg", StringComparison.OrdinalIgnoreCase))
            {
                return "image/jpeg";
            }

            return "image/png";
        }

        private static (Stream FileStream, string FileName, string ContentType) OpenOriginal(ArchiveDocument document, string sourcePath)
        {
            return
            (
                new FileStream(sourcePath, FileMode.Open, FileAccess.Read, FileShare.Read),
                document.FileName,
                document.ContentType
            );
        }
    }
}
