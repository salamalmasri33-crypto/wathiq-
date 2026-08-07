using System.Text.Json.Serialization;

namespace eArchiveSystem.Application.Classification.Models;

public sealed class AraGenreClassificationResult
{
    [JsonPropertyName("id")]
    public required string Id { get; init; }

    [JsonPropertyName("broad_genre")]
    public required string BroadGenre { get; init; }

    [JsonPropertyName("specific_genre")]
    public required string SpecificGenre { get; init; }
}
