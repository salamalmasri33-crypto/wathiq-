using eArchiveSystem.Application.Segmentation.Mappers;
using eArchiveSystem.Application.Segmentation.Models;
using eArchiveSystem.Domain.Models;

namespace eArchiveSystem.Tests;

public sealed class DocumentSegmentationMapperTests
{
    [Fact]
    public void Completed_mapper_preserves_exact_text_sentences_and_pipeline_fields()
    {
        var completedAt = new DateTime(2026, 8, 7, 10, 15, 0, DateTimeKind.Utc);
        var result = new SegmentationResult
        {
            DocumentId = "doc-789",
            Status = "completed",
            Provider = "AraSeg",
            Track = "PA",
            PipelineId = "pa-2026-08-01",
            NormalizedText = "  سطر أول\nسطر\tثانٍ \\n [PAR]؟ ",
            Sentences = new[]
            {
                new SegmentedSentence
                {
                    Index = 0,
                    Text = "  سطر أول",
                    StartToken = 0,
                    EndToken = 2
                },
                new SegmentedSentence
                {
                    Index = 1,
                    Text = "سطر\tثانٍ \\n [PAR]؟ ",
                    StartToken = 3,
                    EndToken = 7
                }
            }
        };

        var mapped = DocumentSegmentationMapper.ToCompleted(result, completedAt);

        Assert.Equal("doc-789", mapped.DocumentId);
        Assert.Equal(SegmentationStatus.Completed, mapped.Status);
        Assert.Equal("AraSeg", mapped.Provider);
        Assert.Equal("PA", mapped.Track);
        Assert.Equal("pa-2026-08-01", mapped.PipelineId);
        Assert.Equal("  سطر أول\nسطر\tثانٍ \\n [PAR]؟ ", mapped.NormalizedText);
        Assert.NotNull(mapped.Sentences);
        Assert.Equal(2, mapped.Sentences!.Count);
        Assert.Equal(0, mapped.Sentences[0].Index);
        Assert.Equal("  سطر أول", mapped.Sentences[0].Text);
        Assert.Equal(0, mapped.Sentences[0].StartToken);
        Assert.Equal(2, mapped.Sentences[0].EndToken);
        Assert.Equal("سطر\tثانٍ \\n [PAR]؟ ", mapped.Sentences[1].Text);
        Assert.Equal(3, mapped.Sentences[1].StartToken);
        Assert.Equal(7, mapped.Sentences[1].EndToken);
        Assert.Null(mapped.ErrorCode);
        Assert.Null(mapped.ErrorMessage);
        Assert.Equal(completedAt, mapped.CreatedAt);
        Assert.Equal(completedAt, mapped.UpdatedAt);
        Assert.Equal(completedAt, mapped.CompletedAt);
        Assert.Equal(DateTimeKind.Utc, mapped.CreatedAt.Kind);
        Assert.Equal(DateTimeKind.Utc, mapped.UpdatedAt.Kind);
        Assert.Equal(DateTimeKind.Utc, mapped.CompletedAt!.Value.Kind);
    }
}
