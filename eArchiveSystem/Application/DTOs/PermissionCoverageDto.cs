namespace eArchiveSystem.Application.DTOs
{
    public class PermissionCoverageDto
    {
        public IReadOnlyList<string> Implemented { get; set; } = Array.Empty<string>();
        public IReadOnlyList<string> Pending { get; set; } = Array.Empty<string>();
    }
}
