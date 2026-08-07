using MongoDB.Bson;
using MongoDB.Bson.Serialization.Attributes;

namespace eArchiveSystem.Domain.Models
{
    public class Department
    {
        [BsonId]
        [BsonRepresentation(BsonType.ObjectId)]
        public string Id { get; set; } = string.Empty;

        [BsonElement("name")]
        public string Name { get; set; } = string.Empty;

        [BsonElement("institutionId")]
        public string InstitutionId { get; set; } = string.Empty;

        [BsonElement("parentDepartmentId")]
        public string? ParentDepartmentId { get; set; }

        [BsonElement("createdAt")]
        public DateTime CreatedAt { get; set; } = DateTime.UtcNow;

        [BsonElement("updatedAt")]
        public DateTime UpdatedAt { get; set; } = DateTime.UtcNow;
    }
}
