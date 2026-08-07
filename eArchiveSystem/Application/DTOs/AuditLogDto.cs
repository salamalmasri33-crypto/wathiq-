namespace eArchiveSystem.Application.DTOs
{
    public class AuditLogDto
    {
        public string Id { get; set; }
        public DateTime Timestamp { get; set; }

        public string UserId { get; set; }
        public string UserName { get; set; }   // Actor display name.
        public string UserRole { get; set; }

        public string Action { get; set; }
        public string? DocumentId { get; set; }
        public string Description { get; set; }


    }
}
