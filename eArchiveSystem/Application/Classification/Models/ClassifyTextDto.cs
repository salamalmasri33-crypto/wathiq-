using System.ComponentModel.DataAnnotations;

namespace eArchiveSystem.Application.Classification.Models;

public sealed class ClassifyTextDto
{
    [Required, MinLength(1)]
    public string Id { get; init; } = string.Empty;

    [Required, MinLength(1)]
    public string Text { get; init; } = string.Empty;

    public string? InstitutionId { get; init; }
}
