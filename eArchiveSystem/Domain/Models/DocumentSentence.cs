using MongoDB.Bson.Serialization.Attributes;

namespace eArchiveSystem.Domain.Models
{
    public class DocumentSentence
    {
        [BsonElement("index")]
        public int Index { get; set; }

        [BsonElement("text")]
        public string Text { get; set; } = string.Empty;

        [BsonElement("startToken")]
        public int StartToken { get; set; }

        [BsonElement("endToken")]
        public int EndToken { get; set; }
    }
}
