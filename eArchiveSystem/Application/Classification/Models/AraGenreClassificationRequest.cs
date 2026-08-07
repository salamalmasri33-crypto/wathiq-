using System.Text.Json.Serialization;

namespace eArchiveSystem.Application.Classification.Models;

public sealed class AraGenreClassificationRequest
{
    [JsonPropertyName("id")]
    public required string Id { get; init; }

    [JsonPropertyName("text")]
    public required string Text { get; init; }
}
