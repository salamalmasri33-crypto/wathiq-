namespace eArchiveSystem.Application.Classification.Models;

public sealed class ClassifyTextResultDto
{
    public required string Id { get; init; }
    public required string BroadGenre { get; init; }
    public required string SpecificGenre { get; init; }
}
