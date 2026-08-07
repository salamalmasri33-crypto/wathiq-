namespace eArchiveSystem.Application.Classification.Models;

public sealed record GenreTaxonomyBroad(string Id, bool IsActive);
public sealed record GenreTaxonomySpecific(string Id, string BroadId, bool IsActive);
public sealed record GenreTaxonomySnapshot(
    IReadOnlyDictionary<string, GenreTaxonomyBroad> BroadGenres,
    IReadOnlyDictionary<string, GenreTaxonomySpecific> SpecificGenres);
