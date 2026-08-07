
        namespace eArchiveSystem.Application.Interfaces.Services
    {
        public interface IRuleBasedAnalyzer
        {
            string ExtractDescription(string text);
            List<string> ExtractKeywords(string text);
            List<string> ExtractInsights(string text);
            string DetectDocumentType(string text, string? fileName = null);
            string? DetectIssuingEntity(string text);
            string? ExtractReferenceNumber(string text);
            DateTime? ExtractDocumentDate(string text);
            List<string> ExtractHeaders(string text);
            List<string> ExtractFooters(string text);
            List<string> DetectStamps(string text);
            List<string> DetectSignatures(string text);
        }
    }

