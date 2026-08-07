namespace eArchiveSystem.Application.Segmentation.Models
{
    public sealed record SegmentedSentence
    {
        public int Index { get; init; }
        public string Text { get; init; } = string.Empty;
        public int StartToken { get; init; }
        public int EndToken { get; init; }
    }
}
