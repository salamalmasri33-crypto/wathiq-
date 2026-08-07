using eArchiveSystem.Application.Segmentation.Abstractions;
using eArchiveSystem.Application.Segmentation.Models;
using eArchiveSystem.Infrastructure.AI.Segmentation;
using eArchiveSystem.Infrastructure.Configuration;
using Microsoft.Extensions.Options;

namespace eArchiveSystem.Tests;

public sealed class AraSegSentenceSegmenterTests
{
    [Fact]
    public async Task SegmentAsync_delegates_once_with_exact_text_and_returns_client_result()
    {
        var expected = new SegmentationResult
        {
            DocumentId = "doc-1",
            Status = "completed",
            Provider = "AraSeg",
            Track = "PA",
            PipelineId = "pa-current-micro-ensemble-861752",
            NormalizedText = "  النص\t\n",
            Sentences =
            [
                new SegmentedSentence
                {
                    Index = 0,
                    Text = "  النص\t\n",
                    StartToken = 0,
                    EndToken = 1
                }
            ]
        };

        var fakeClient = new RecordingAraSegClient(expected);
        var segmenter = new AraSegSentenceSegmenter(
            fakeClient,
            Options.Create(new AraSegOptions { Track = "PA" }));

        var result = await segmenter.SegmentAsync(
            "doc-1",
            "  النص\t\n",
            new SegmentationOptions { Track = "PA" });

        Assert.Same(expected, result);
        Assert.Equal(1, fakeClient.CallCount);
        Assert.Equal("doc-1", fakeClient.DocumentId);
        Assert.Equal("  النص\t\n", fakeClient.Text);
        Assert.Equal("PA", fakeClient.Track);
    }

    [Fact]
    public async Task SegmentAsync_uses_configured_track_when_request_track_is_blank()
    {
        var fakeClient = new RecordingAraSegClient(new SegmentationResult());
        var segmenter = new AraSegSentenceSegmenter(
            fakeClient,
            Options.Create(new AraSegOptions { Track = "PA" }));

        await segmenter.SegmentAsync(
            "doc-1",
            "النص",
            new SegmentationOptions(),
            CancellationToken.None);

        Assert.Equal("PA", fakeClient.Track);
    }

    private sealed class RecordingAraSegClient : IAraSegClient
    {
        private readonly SegmentationResult _result;

        public RecordingAraSegClient(SegmentationResult result)
        {
            _result = result;
        }

        public int CallCount { get; private set; }
        public string? DocumentId { get; private set; }
        public string? Text { get; private set; }
        public string? Track { get; private set; }

        public Task<SegmentationResult> SegmentAsync(string documentId, string text, string track, CancellationToken cancellationToken = default)
        {
            CallCount++;
            DocumentId = documentId;
            Text = text;
            Track = track;
            return Task.FromResult(_result);
        }
    }
}
