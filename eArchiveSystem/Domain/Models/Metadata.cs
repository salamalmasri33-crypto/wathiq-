using MongoDB.Bson;
using MongoDB.Bson.Serialization.Attributes;

namespace eArchiveSystem.Domain.Models
{
        [BsonIgnoreExtraElements]
        public class Metadata
        {
            // Same ID as the related Document (1:1 relation)
            [BsonId]
            [BsonRepresentation(BsonType.ObjectId)]
            public string Id { get; set; } = default!;

            // Short description / summary
            public string? Description { get; set; }

            // Stable technical IDs from the institution taxonomy.
            public string? BroadGenre { get; set; }
            public string? SpecificGenre { get; set; }

            // Document type (e.g. PDF, Report)
            public string? DocumentType { get; set; }

            // Searchable tags
            public List<string>? Tags { get; set; }

            // Structured extraction
            public string? IssuingEntity { get; set; }
            public string? ReferenceNumber { get; set; }
            public DateTime? DocumentDate { get; set; }
            public List<string>? Insights { get; set; }
            public bool HasSignature { get; set; }
            public List<string>? Signatures { get; set; }
            public List<string>? Headers { get; set; }
            public List<string>? Footers { get; set; }
            public List<string>? Stamps { get; set; }
            public string? RawExtractionJson { get; set; }
            public bool StructuredDataProvided { get; set; }
            public bool CoreFieldsComplete { get; set; }
            public bool AdvancedMetadataComplete { get; set; }
            public bool LayoutAnalysisAvailable { get; set; }
            public bool RequiresReview { get; set; }
            public string? ExtractionStatus { get; set; }
            public List<string>? MissingFields { get; set; }

            // Metadata creation timestamp
            public DateTime CreatedAt { get; set; } = DateTime.UtcNow;

            // Last metadata update timestamp
            public DateTime? UpdatedAt { get; set; }

            // Department associated with the document
            public string? Department { get; set; }

            // Department identifier associated with the document
            public string? DepartmentId { get; set; }

            // Optional expiration date
            public DateTime? ExpirationDate { get; set; }
        }
    }
