using MongoDB.Bson;
using MongoDB.Bson.Serialization.Attributes;

namespace eArchiveSystem.Domain.Models
{
    public class User
    {
        [BsonId]
        [BsonRepresentation(BsonType.ObjectId)]
        public string Id { get; set; }

        [BsonElement("name")]
        public string Name { get; set; }

        [BsonElement("email")]
        public string Email { get; set; }

        [BsonElement("password")]
        public string Password { get; set; }

        [BsonElement("role")]
        public string Role { get; set; }   // Access role used by authorization.

        [BsonElement("institutionId")]
        public string? InstitutionId { get; set; }

        [BsonElement("departmentId")]
        public string? DepartmentId { get; set; }

        [BsonElement("createdAt")]
        public DateTime CreatedAt { get; set; } = DateTime.Now;

        [BsonElement("updatedAt")]
        public DateTime UpdatedAt { get; set; } = DateTime.Now;

        [BsonElement("resetCode")]
        public string? ResetCode { get; set; }

        [BsonElement("resetCodeExpiry")]
        public DateTime? ResetCodeExpiry { get; set; }

        [BsonElement("failedLoginAttempts")]
        public int FailedLoginAttempts { get; set; } = 0;

        [BsonElement("lockoutUntil")]
        public DateTime? LockoutUntil { get; set; } = null;

        [BsonElement("department")]
        public string? Department { get; set; }

        [BsonElement("twoFactorEnabled")]
        public bool TwoFactorEnabled { get; set; } = false;

        [BsonElement("twoFactorCode")]
        public string? TwoFactorCode { get; set; }

        [BsonElement("twoFactorExpiry")]
        public DateTime? TwoFactorExpiry { get; set; }


    }
}
