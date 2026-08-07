namespace eArchiveSystem.Application.DTOs
{
    public class DocumentTimelineEventDto
    {
        public DateTime OccurredAt { get; set; }
        public string Source { get; set; } = string.Empty;
        public string Action { get; set; } = string.Empty;
        public string Description { get; set; } = string.Empty;
        public string? ActorUserId { get; set; }
        public string? ActorName { get; set; }
        public string? ActorRole { get; set; }
    }
}
