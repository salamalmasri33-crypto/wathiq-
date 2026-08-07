using System.Text.RegularExpressions;
using eArchiveSystem.Application.Interfaces.Services;

namespace eArchiveSystem.Application.Services
{
    public class TextPreprocessorService : ITextPreprocessorService
    {
        private static readonly HashSet<string> ArabicStopWords = new()
    {
        "في","من","على","الى","إلى","عن","و","أو","ثم","أن","إن","كان","كانت",
        "هذا","هذه","ذلك","تلك","هو","هي","ما","لم","لن","قد","كل","بعض"
    };

        private static readonly HashSet<string> EnglishStopWords = new()
    {
        "a","an","the","and","or","in","on","at","to","from","of","for","by",
        "is","are","was","were","be","been","this","that","these","those"
    };

        public string Clean(string text)
        {
            if (string.IsNullOrWhiteSpace(text)) 
                return string.Empty;

            text = RemoveArabicDiacritics(text);
            text = NormalizeArabic(text);
            text = NormalizeEnglish(text);
            text = RemovePunctuation(text);
            text = RemoveExtraSpaces(text);

            var tokens = text.Split(' ', StringSplitOptions.RemoveEmptyEntries)
                .Where(t => !IsStopWord(t));

            return string.Join(' ', tokens);
        }

        private static string RemoveArabicDiacritics(string text)
        {
            return Regex.Replace(text, "[\\u064B-\\u065F\\u0670]", "");
        }

        private static string NormalizeArabic(string text)
        {
            return text
                .Replace("أ", "ا")
                .Replace("إ", "ا")
                .Replace("آ", "ا")
                .Replace("ى", "ي")
                .Replace("ؤ", "و")
                .Replace("ئ", "ي")
                .Replace("ة", "ه");
        }

        private static string NormalizeEnglish(string text)
        {
            return text.ToLowerInvariant();
        }

        private static string RemovePunctuation(string text)
        {
            return Regex.Replace(text, @"[^\p{L}\p{N}\s]", " ");
        }

        private static string RemoveExtraSpaces(string text)
        {
            return Regex.Replace(text, @"\s+", " ").Trim();
        }

        private static bool IsStopWord(string token)
        {
            return ArabicStopWords.Contains(token) || EnglishStopWords.Contains(token);
        }
    }
}