using System.Text.Json.Serialization;

namespace eArchiveSystem.Infrastructure.AI.Clients;

internal sealed class AraSegSegmentTextRequest
{
    [JsonPropertyName("documentId")]
    public required string DocumentId { get; init; }

    [JsonPropertyName("text")]
    public required string Text { get; init; }

    [JsonPropertyName("track")]
    public required string Track { get; init; }
}

internal sealed class AraSegSegmentTextResponse
{
    [JsonPropertyName("documentId")]
    public string? DocumentId { get; init; }

    [JsonPropertyName("status")]
    public string? Status { get; init; }

    [JsonPropertyName("provider")]
    public string? Provider { get; init; }

    [JsonPropertyName("track")]
    public string? Track { get; init; }

    [JsonPropertyName("pipelineId")]
    public string? PipelineId { get; init; }

    [JsonPropertyName("normalizedText")]
    public string? NormalizedText { get; init; }

    [JsonPropertyName("segments")]
    public IReadOnlyList<AraSegSegmentTextSegmentResponse>? Segments { get; init; }
}

internal sealed class AraSegSegmentTextSegmentResponse
{
    [JsonPropertyName("index")]
    public int? Index { get; init; }

    [JsonPropertyName("text")]
    public string? Text { get; init; }

    [JsonPropertyName("startToken")]
    public int? StartToken { get; init; }

    [JsonPropertyName("endToken")]
    public int? EndToken { get; init; }
}

internal sealed class AraSegErrorEnvelope
{
    [JsonPropertyName("error")]
    public AraSegErrorDetails? Error { get; init; }
}

internal sealed class AraSegErrorDetails
{
    [JsonPropertyName("code")]
    public string? Code { get; init; }

    [JsonPropertyName("message")]
    public string? Message { get; init; }

    [JsonPropertyName("requestId")]
    public string? RequestId { get; init; }
}
