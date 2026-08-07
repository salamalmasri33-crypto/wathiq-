namespace eArchive.OcrService.Services
{
    public interface IPdfToImageService
    {
        Task <List<string>> ConvertToImages(string pdfPath);
    }
}
