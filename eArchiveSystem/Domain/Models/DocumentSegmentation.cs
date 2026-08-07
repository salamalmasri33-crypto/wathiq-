using MongoDB.Bson;
using MongoDB.Bson.Serialization.Attributes;

namespace eArchiveSystem.Domain.Models
{
    [BsonIgnoreExtraElements]
    public class DocumentSegmentation
    {
        [BsonId]
        [BsonRepresentation(BsonType.ObjectId)]
        public string Id { get; set; } = default!;

        [BsonElement("documentId")]
        public string DocumentId { get; set; } = default!;

        [BsonElement("status")]
        public SegmentationStatus Status { get; set; } = SegmentationStatus.Pending;

        [BsonElement("provider")]
        public string? Provider { get; set; }

        [BsonElement("track")]
        public string Track { get; set; } = "PA";

        [BsonElement("pipelineId")]
        public string? PipelineId { get; set; }

        [BsonElement("normalizedText")]
        public string? NormalizedText { get; set; }

        [BsonElement("sentences")]
        public List<DocumentSentence>? Sentences { get; set; }

        [BsonElement("errorCode")]
        public string? ErrorCode { get; set; }

        [BsonElement("errorMessage")]
        public string? ErrorMessage { get; set; }

        [BsonElement("createdAt")]
        public DateTime CreatedAt { get; set; } = DateTime.UtcNow;

        [BsonElement("updatedAt")]
        public DateTime UpdatedAt { get; set; } = DateTime.UtcNow;

        [BsonElement("completedAt")]
        public DateTime? CompletedAt { get; set; }
    }
}
