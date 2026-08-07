using MongoDB.Bson;
using MongoDB.Bson.Serialization.Attributes;

namespace eArchiveSystem.Domain.Models
{
    public class Notification
    {
        [BsonId]
        [BsonRepresentation(BsonType.ObjectId)]
        public string Id { get; set; } = default!;

        [BsonElement("userId")]
        public string UserId { get; set; } = default!;

        [BsonElement("documentId")]
        public string? DocumentId { get; set; }

        [BsonElement("institutionId")]
        public string? InstitutionId { get; set; }

        [BsonElement("type")]
        public string Type { get; set; } = default!;

        [BsonElement("title")]
        public string Title { get; set; } = default!;

        [BsonElement("message")]
        public string Message { get; set; } = default!;

        [BsonElement("isRead")]
        public bool IsRead { get; set; }

        [BsonElement("createdAt")]
        public DateTime CreatedAt { get; set; } = DateTime.UtcNow;

        [BsonElement("readAt")]
        public DateTime? ReadAt { get; set; }
    }
}
