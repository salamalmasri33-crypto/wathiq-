using MongoDB.Bson;
using MongoDB.Driver;

namespace eArchiveSystem.Infrastructure.Persistence.Migrations;

public sealed class RemoveLegacyMetadataCategoryMigration
{
    public const string MigrationId = "20260804_replace_metadata_category_with_genres_v1";
    private readonly IMongoDatabase _database;
    private readonly ILogger<RemoveLegacyMetadataCategoryMigration> _logger;

    public RemoveLegacyMetadataCategoryMigration(IMongoDatabase database, ILogger<RemoveLegacyMetadataCategoryMigration> logger)
    {
        _database = database;
        _logger = logger;
    }

    public async Task RunAsync(CancellationToken cancellationToken = default)
    {
        var migrations = _database.GetCollection<BsonDocument>("SchemaMigrations");
        if (await migrations.Find(Builders<BsonDocument>.Filter.Eq("_id", MigrationId)).AnyAsync(cancellationToken)) return;

        var metadata = _database.GetCollection<BsonDocument>("Metadata");
        var documents = _database.GetCollection<BsonDocument>("Documents");
        var metadataResult = await metadata.UpdateManyAsync(
            Builders<BsonDocument>.Filter.Exists("Category"), Builders<BsonDocument>.Update.Unset("Category"), cancellationToken: cancellationToken);
        var documentsResult = await documents.UpdateManyAsync(
            Builders<BsonDocument>.Filter.Exists("Metadata.Category"), Builders<BsonDocument>.Update.Unset("Metadata.Category"), cancellationToken: cancellationToken);

        await migrations.InsertOneAsync(new BsonDocument
        {
            ["_id"] = MigrationId,
            ["appliedAt"] = DateTime.UtcNow,
            ["metadataModified"] = metadataResult.ModifiedCount,
            ["documentsModified"] = documentsResult.ModifiedCount
        }, cancellationToken: cancellationToken);

        _logger.LogInformation("Applied migration {MigrationId}: updated {MetadataCount} metadata records and {DocumentCount} documents",
            MigrationId, metadataResult.ModifiedCount, documentsResult.ModifiedCount);
    }
}
