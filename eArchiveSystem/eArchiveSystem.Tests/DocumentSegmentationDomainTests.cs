using eArchiveSystem.Domain.Models;
using MongoDB.Bson;
using MongoDB.Bson.Serialization;

namespace eArchiveSystem.Tests;

public sealed class DocumentSegmentationDomainTests
{
    [Fact]
    public void Segmentation_status_enum_values_are_stable()
    {
        Assert.Equal(0, (int)SegmentationStatus.Pending);
        Assert.Equal(1, (int)SegmentationStatus.Processing);
        Assert.Equal(2, (int)SegmentationStatus.Completed);
        Assert.Equal(3, (int)SegmentationStatus.Failed);
    }

    [Fact]
    public void Document_segmentation_serializes_with_expected_bson_shape()
    {
        var timestamp = new DateTime(2026, 8, 7, 9, 30, 0, DateTimeKind.Utc);
        var model = new DocumentSegmentation
        {
            Id = "507f1f77bcf86cd799439011",
            DocumentId = "doc-123",
            Status = SegmentationStatus.Completed,
            Provider = "AraSeg",
            Track = "PA",
            PipelineId = "pa-prod-v1",
            NormalizedText = "  قبل\nبعد\t\\n [PAR]؟ ",
            Sentences = new List<DocumentSentence>
            {
                new()
                {
                    Index = 0,
                    Text = "  قبل",
                    StartToken = 0,
                    EndToken = 1
                },
                new()
                {
                    Index = 1,
                    Text = "بعد\t\\n [PAR]؟ ",
                    StartToken = 2,
                    EndToken = 5
                }
            },
            ErrorCode = null,
            ErrorMessage = null,
            CreatedAt = timestamp,
            UpdatedAt = timestamp,
            CompletedAt = timestamp
        };

        var bson = model.ToBsonDocument();

        Assert.Equal(BsonType.ObjectId, bson["_id"].BsonType);
        Assert.Equal("doc-123", bson["documentId"].AsString);
        Assert.Equal((int)SegmentationStatus.Completed, bson["status"].AsInt32);
        Assert.Equal("AraSeg", bson["provider"].AsString);
        Assert.Equal("PA", bson["track"].AsString);
        Assert.Equal("pa-prod-v1", bson["pipelineId"].AsString);
        Assert.Equal("  قبل\nبعد\t\\n [PAR]؟ ", bson["normalizedText"].AsString);
        Assert.Equal(BsonType.Array, bson["sentences"].BsonType);
        Assert.Equal(2, bson["sentences"].AsBsonArray.Count);

        var firstSentence = bson["sentences"].AsBsonArray[0].AsBsonDocument;
        Assert.Equal(0, firstSentence["index"].AsInt32);
        Assert.Equal("  قبل", firstSentence["text"].AsString);
        Assert.Equal(0, firstSentence["startToken"].AsInt32);
        Assert.Equal(1, firstSentence["endToken"].AsInt32);

        Assert.Equal(BsonType.DateTime, bson["createdAt"].BsonType);
        Assert.Equal(BsonType.DateTime, bson["updatedAt"].BsonType);
        Assert.Equal(BsonType.DateTime, bson["completedAt"].BsonType);
        Assert.False(bson.Contains("confidence"));
        Assert.False(bson.Contains("modelVersion"));

        var roundTrip = BsonSerializer.Deserialize<DocumentSegmentation>(bson);
        Assert.Equal(model.DocumentId, roundTrip.DocumentId);
        Assert.Equal(model.NormalizedText, roundTrip.NormalizedText);
        Assert.Equal(model.Sentences![1].Text, roundTrip.Sentences![1].Text);
    }
}
