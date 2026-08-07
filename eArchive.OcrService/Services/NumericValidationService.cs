using System.Text;

namespace eArchive.OcrService.Services
{
    public class NumericValidationService : INumericValidationService
    {
        private static readonly Dictionary<char, char> ArabicIndicDigits = new()
        {
            ['٠'] = '0',
            ['١'] = '1',
            ['٢'] = '2',
            ['٣'] = '3',
            ['٤'] = '4',
            ['٥'] = '5',
            ['٦'] = '6',
            ['٧'] = '7',
            ['٨'] = '8',
            ['٩'] = '9',
            ['۰'] = '0',
            ['۱'] = '1',
            ['۲'] = '2',
            ['۳'] = '3',
            ['۴'] = '4',
            ['۵'] = '5',
            ['۶'] = '6',
            ['۷'] = '7',
            ['۸'] = '8',
            ['۹'] = '9'
        };

        public string ValidateAndNormalize(string rawText)
        {
            if (string.IsNullOrWhiteSpace(rawText))
                return string.Empty;

            var normalized = new StringBuilder(rawText.Length);

            foreach (var character in rawText)
            {
                normalized.Append(ArabicIndicDigits.TryGetValue(character, out var mappedDigit)
                    ? mappedDigit
                    : character);
            }

            return normalized.ToString();
        }
    }
}
