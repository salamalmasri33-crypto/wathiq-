namespace eArchiveSystem.Infrastructure.Configuration;

/// <summary>
/// Configuration options for the AraSeg raw-text segmentation integration.
/// </summary>
public sealed class AraSegOptions
{
    public string BaseUrl { get; init; } = "http://127.0.0.1:8000";
    public string SegmentTextPath { get; init; } = "/internal/api/v1/segment-text";
    public string Track { get; init; } = "PA";
    public int TimeoutSeconds { get; init; } = 120;
}
