using System.Text.RegularExpressions;
using eArchiveSystem.Application.Interfaces.Services;

namespace eArchiveSystem.Application.Services
{
    public class RuleBasedAnalyzer : IRuleBasedAnalyzer
    {
        private static readonly string[] StopWords =
        {
            "the","and","of","in","to","is","for","on","with","as","by"
        };

        public string ExtractDescription(string text)
        {
            if (string.IsNullOrWhiteSpace(text))
                return string.Empty;

            var sentences = Regex.Split(text, @"(?<=[\.])")
                .Select(s => s.Trim())
                .Where(s => s.Length > 30)
                .Take(2);

            return string.Join(" ", sentences);
        }

        public List<string> ExtractKeywords(string text)
        {
            if (string.IsNullOrWhiteSpace(text))
                return new List<string>();

            return text.ToLower()
                .Split(' ', StringSplitOptions.RemoveEmptyEntries)
                .Where(w => w.Length > 4 && !StopWords.Contains(w))
                .GroupBy(w => w)
                .OrderByDescending(g => g.Count())
                .Take(6)
                .Select(g => g.Key)
                .ToList();
        }

        public List<string> ExtractInsights(string text)
        {
            if (string.IsNullOrWhiteSpace(text))
                return new List<string>();

            var normalized = text.ToLowerInvariant();
            var insights = new List<string>();

            if (normalized.Contains("urgent") || normalized.Contains("important") || normalized.Contains("مهم"))
                insights.Add("Contains urgency or importance indicators");

            if (normalized.Contains("deadline") || normalized.Contains("due date") || normalized.Contains("آخر موعد"))
                insights.Add("Contains deadline-related information");

            if (normalized.Contains("approved") || normalized.Contains("approval") || normalized.Contains("موافقة"))
                insights.Add("Contains approval-related language");

            if (normalized.Contains("policy") || normalized.Contains("قرار") || normalized.Contains("regulation"))
                insights.Add("Contains policy or governance indicators");

            return insights;
        }

        public string DetectDocumentType(string text, string? fileName = null)
        {
            if (string.IsNullOrWhiteSpace(text))
                return "General";

            var content = text.ToLower();

            if (content.Contains("lecture") ||
                content.Contains("chapter") ||
                content.Contains("course") ||
                content.Contains("slides"))
                return "Lecture";

            if (content.Contains("assignment") ||
                content.Contains("task") ||
                content.Contains("required to") ||
                content.Contains("submit"))
                return "TaskAssignment";

            if (content.Contains("decision") ||
                content.Contains("issued by") ||
                content.Contains("effective date") ||
                content.Contains("قرار"))
                return "Decision";

            if (content.Contains("report") ||
                content.Contains("summary") ||
                content.Contains("analysis"))
                return "Report";

            if (content.Contains("contract") ||
                content.Contains("agreement") ||
                content.Contains("party") ||
                content.Contains("terms and conditions"))
                return "Contract";

            if (content.Contains("invoice") ||
                content.Contains("amount") ||
                content.Contains("total") ||
                content.Contains("vat"))
                return "Invoice";

            if (content.Contains("api") ||
                content.Contains("documentation") ||
                content.Contains("guide") ||
                content.Contains("installation"))
                return "TechnicalGuide";

            return "General";
        }

        public string? DetectIssuingEntity(string text)
        {
            if (string.IsNullOrWhiteSpace(text))
                return null;

            var patterns = new[]
            {
                @"issued by\s*[:\-]?\s*(.+)",
                @"issuing entity\s*[:\-]?\s*(.+)",
                @"الجهة المصدرة\s*[:\-]?\s*(.+)",
                @"صادر عن\s*[:\-]?\s*(.+)"
            };

            foreach (var pattern in patterns)
            {
                var match = Regex.Match(text, pattern, RegexOptions.IgnoreCase);
                if (match.Success)
                    return match.Groups[1].Value.Trim();
            }

            return null;
        }

        public string? ExtractReferenceNumber(string text)
        {
            if (string.IsNullOrWhiteSpace(text))
                return null;

            var patterns = new[]
            {
                @"reference\s*(number|no\.?)\s*[:\-]?\s*([A-Za-z0-9\-/]+)",
                @"ref\.?\s*[:\-]?\s*([A-Za-z0-9\-/]+)",
                @"الرقم المرجعي\s*[:\-]?\s*([A-Za-z0-9\-/]+)",
                @"رقم الكتاب\s*[:\-]?\s*([A-Za-z0-9\-/]+)"
            };

            foreach (var pattern in patterns)
            {
                var match = Regex.Match(text, pattern, RegexOptions.IgnoreCase);
                if (match.Success)
                    return match.Groups[match.Groups.Count - 1].Value.Trim();
            }

            return null;
        }

        public DateTime? ExtractDocumentDate(string text)
        {
            if (string.IsNullOrWhiteSpace(text))
                return null;

            var match = Regex.Match(text, @"\b(\d{4}[/-]\d{1,2}[/-]\d{1,2}|\d{1,2}[/-]\d{1,2}[/-]\d{4})\b");
            if (!match.Success)
                return null;

            return DateTime.TryParse(match.Value, out var date) ? date : null;
        }

        public List<string> ExtractHeaders(string text)
        {
            if (string.IsNullOrWhiteSpace(text))
                return new List<string>();

            return text.Split('\n', StringSplitOptions.RemoveEmptyEntries)
                .Select(line => line.Trim())
                .Where(line => !string.IsNullOrWhiteSpace(line))
                .Take(3)
                .ToList();
        }

        public List<string> ExtractFooters(string text)
        {
            if (string.IsNullOrWhiteSpace(text))
                return new List<string>();

            return text.Split('\n', StringSplitOptions.RemoveEmptyEntries)
                .Select(line => line.Trim())
                .Where(line => !string.IsNullOrWhiteSpace(line))
                .Reverse()
                .Take(3)
                .Reverse()
                .ToList();
        }

        public List<string> DetectStamps(string text)
        {
            if (string.IsNullOrWhiteSpace(text))
                return new List<string>();

            var indicators = new[] { "stamp", "sealed", "official seal", "ختم", "مختوم" };

            return indicators
                .Where(indicator => text.Contains(indicator, StringComparison.OrdinalIgnoreCase))
                .Distinct(StringComparer.OrdinalIgnoreCase)
                .ToList();
        }

        public List<string> DetectSignatures(string text)
        {
            if (string.IsNullOrWhiteSpace(text))
                return new List<string>();

            var indicators = new[] { "signature", "signed by", "التوقيع", "موقّع", "موقع" };

            return indicators
                .Where(indicator => text.Contains(indicator, StringComparison.OrdinalIgnoreCase))
                .Distinct(StringComparer.OrdinalIgnoreCase)
                .ToList();
        }
    }
}
