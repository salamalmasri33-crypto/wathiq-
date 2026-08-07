using MongoDB.Bson;
using MongoDB.Bson.Serialization.Attributes;

namespace eArchiveSystem.Domain.Models
{
    [BsonIgnoreExtraElements]
    public class Document
        { 
            // MongoDB ObjectId
            [BsonId]
            [BsonRepresentation(BsonType.ObjectId)]
            public string Id { get; set; }

            // Document title
            public string Title { get; set; }

            // OCR extracted text (optional)
            public string? Content { get; set; }

            // OCR raw text returned by the OCR provider
            public string? RawOcrText { get; set; }

            // OCR normalized text before downstream analysis/search cleaning
            public string? NormalizedOcrText { get; set; }

            // OCR provider metadata
            public string? OcrProvider { get; set; }
            public string? OcrLanguage { get; set; }
            public int? OcrPages { get; set; }
            public DateTime? OcrUpdatedAt { get; set; }

            // File path on the server
            public string FilePath { get; set; }

            // Original file name
            public string FileName { get; set; }

            // File MIME type (e.g. application/pdf)
            public string ContentType { get; set; }

            // File size in bytes
            public long Size { get; set; }

            // File hash (duplicate detection)
            public string FileHash { get; set; }

            // Creation & last update timestamps
            public DateTime CreatedAt { get; set; }
            public DateTime UpdatedAt { get; set; }

            // Owner user ID
            public string UserId { get; set; }

            // Institution that owns this document
            public string? InstitutionId { get; set; }

            // Department identifier used for authorization/search
            public string? DepartmentId { get; set; }

            // Department the document belongs to
            public string? Department { get; set; }

            // Document priority
            [BsonElement("priority")]
            public DocumentPriority Priority { get; set; } = DocumentPriority.Normal;

            // Sensitivity label used by secure download workflows
            [BsonElement("isSensitive")]
            public bool IsSensitive { get; set; } = false;

            // Document workflow status
            [BsonElement("status")]
            public DocumentStatus Status { get; set; } = DocumentStatus.Draft;

            // Workflow timestamps
            [BsonElement("submittedAt")]
            public DateTime? SubmittedAt { get; set; }

            [BsonElement("reviewStartedAt")]
            public DateTime? ReviewStartedAt { get; set; }

            [BsonElement("reviewedAt")]
            public DateTime? ReviewedAt { get; set; }

            [BsonElement("publishedAt")]
            public DateTime? PublishedAt { get; set; }

            [BsonElement("archivedAt")]
            public DateTime? ArchivedAt { get; set; }

            // Workflow actors
            [BsonElement("reviewedByUserId")]
            public string? ReviewedByUserId { get; set; }

            [BsonElement("publishedByUserId")]
            public string? PublishedByUserId { get; set; }

            [BsonElement("archivedByUserId")]
            public string? ArchivedByUserId { get; set; }

            // Rejection reason
            [BsonElement("rejectionReason")]
            public string? RejectionReason { get; set; }

            // Embedded metadata (synced with Metadata collection)
            [BsonElement("Metadata")]
            public Metadata? Metadata { get; set; }

            // Owner name (for view only – not stored in DB)
            [BsonIgnore]
            public string? OwnerName { get; set; }
        }
    }

