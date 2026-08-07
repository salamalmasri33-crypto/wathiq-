namespace eArchive.OcrService.Services
{
    public interface INumericValidationService
    {
        string ValidateAndNormalize(string rawText);
    }
}
