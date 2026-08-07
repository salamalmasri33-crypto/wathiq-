namespace eArchiveSystem.Domain.Models
{
    public class AuditLog
    {
        public string Id { get; set; }

        public DateTime Timestamp { get; set; }  // Event timestamp.

        public string UserId { get; set; }       // Actor user id.
        public string UserRole { get; set; }     // Actor role at event time.

        public string Action { get; set; }       // Event name.

        public string DocumentId { get; set; }   // Related document id, when available.
        public string Description { get; set; }  // Human-readable event details.

        
    }
}
