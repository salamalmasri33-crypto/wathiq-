using System.Text.Json;
using MongoDB.Bson;
using MongoDB.Driver;

var options = ToolOptions.Parse(args);
var backendRoot = Path.GetFullPath(options.BackendRoot ?? Path.Combine(AppContext.BaseDirectory, "..", "..", "..", "..", ".."));
var appSettingsPath = Path.Combine(backendRoot, "appsettings.json");
var appSettings = ReadAppSettings(appSettingsPath);

var connectionString = options.ConnectionString ?? appSettings.ConnectionString;
var databaseName = options.DatabaseName ?? appSettings.DatabaseName;

if (string.IsNullOrWhiteSpace(connectionString) || string.IsNullOrWhiteSpace(databaseName))
{
    throw new InvalidOperationException("MongoDB ConnectionString/DatabaseName was not found.");
}

var client = new MongoClient(connectionString);
var database = client.GetDatabase(databaseName);

var documents = database.GetCollection<BsonDocument>("Documents");
var metadata = database.GetCollection<BsonDocument>("Metadata");
var notifications = database.GetCollection<BsonDocument>("Notifications");
var auditLogs = database.GetCollection<BsonDocument>("AuditLogs");

var existingDocuments = await documents
    .Find(FilterDefinition<BsonDocument>.Empty)
    .Project(Builders<BsonDocument>.Projection.Include("_id").Include("FilePath"))
    .ToListAsync();

var documentIds = existingDocuments
    .Select(document => document.GetValue("_id", BsonNull.Value))
    .Where(value => value != BsonNull.Value)
    .ToList();

var documentIdStrings = documentIds.Select(value => value.ToString()).ToList();
var filePaths = existingDocuments
    .Select(document => document.GetValue("FilePath", BsonNull.Value))
    .Where(value => value.IsString && !string.IsNullOrWhiteSpace(value.AsString))
    .Select(value => value.AsString)
    .ToList();

var documentFilter = documentIds.Count > 0
    ? Builders<BsonDocument>.Filter.In("_id", documentIds)
    : Builders<BsonDocument>.Filter.Eq("_id", BsonNull.Value);

var metadataFilter = documentIds.Count > 0
    ? Builders<BsonDocument>.Filter.In("_id", documentIds)
    : Builders<BsonDocument>.Filter.Eq("_id", BsonNull.Value);

var notificationFilter = documentIdStrings.Count > 0
    ? Builders<BsonDocument>.Filter.In("documentId", documentIdStrings)
    : Builders<BsonDocument>.Filter.Eq("documentId", BsonNull.Value);

var auditFilter = documentIdStrings.Count > 0
    ? Builders<BsonDocument>.Filter.In("DocumentId", documentIdStrings)
    : Builders<BsonDocument>.Filter.Eq("DocumentId", BsonNull.Value);

var counts = new CleanupCounts(
    Documents: existingDocuments.Count,
    Metadata: documentIds.Count > 0 ? await metadata.CountDocumentsAsync(metadataFilter) : 0,
    Notifications: options.IncludeNotifications && documentIdStrings.Count > 0
        ? await notifications.CountDocumentsAsync(notificationFilter)
        : 0,
    AuditLogs: options.IncludeAuditLogs && documentIdStrings.Count > 0
        ? await auditLogs.CountDocumentsAsync(auditFilter)
        : 0,
    FilesFromDocuments: filePaths.Count);

Console.WriteLine($"Database: {databaseName}");
Console.WriteLine(options.Execute ? "Mode: execute" : "Mode: dry-run");
Console.WriteLine($"Documents: {counts.Documents}");
Console.WriteLine($"Metadata: {counts.Metadata}");
Console.WriteLine($"Notifications selected: {counts.Notifications}");
Console.WriteLine($"Audit logs selected: {counts.AuditLogs}");
Console.WriteLine($"Files referenced: {counts.FilesFromDocuments}");

if (!options.Execute)
{
    Console.WriteLine();
    Console.WriteLine("Dry run only. Nothing was deleted.");
    Console.WriteLine("Run again with --execute to delete database records.");
    return;
}

var deletedMetadata = documentIds.Count > 0
    ? (await metadata.DeleteManyAsync(metadataFilter)).DeletedCount
    : 0;

var deletedNotifications = options.IncludeNotifications && documentIdStrings.Count > 0
    ? (await notifications.DeleteManyAsync(notificationFilter)).DeletedCount
    : 0;

var deletedAuditLogs = options.IncludeAuditLogs && documentIdStrings.Count > 0
    ? (await auditLogs.DeleteManyAsync(auditFilter)).DeletedCount
    : 0;

var deletedDocuments = documentIds.Count > 0
    ? (await documents.DeleteManyAsync(documentFilter)).DeletedCount
    : 0;

Console.WriteLine();
Console.WriteLine($"Deleted documents: {deletedDocuments}");
Console.WriteLine($"Deleted metadata: {deletedMetadata}");
Console.WriteLine($"Deleted notifications: {deletedNotifications}");
Console.WriteLine($"Deleted audit logs: {deletedAuditLogs}");

if (options.DeleteFiles)
{
    var uploadsRoot = Path.GetFullPath(Path.Combine(backendRoot, "uploads"));
    var deletedFiles = 0;
    var skippedFiles = 0;

    foreach (var relativePath in filePaths)
    {
        var fullPath = Path.GetFullPath(Path.Combine(backendRoot, relativePath));

        if (!fullPath.StartsWith(uploadsRoot, StringComparison.OrdinalIgnoreCase))
        {
            skippedFiles++;
            continue;
        }

        if (File.Exists(fullPath))
        {
            File.Delete(fullPath);
            deletedFiles++;
        }
    }

    Console.WriteLine($"Deleted files: {deletedFiles}");
    Console.WriteLine($"Skipped files: {skippedFiles}");
}
else
{
    Console.WriteLine("Uploaded files were left on disk. Add --delete-files if you want to remove them too.");
}

static MongoSettings ReadAppSettings(string appSettingsPath)
{
    if (!File.Exists(appSettingsPath))
    {
        return new MongoSettings(null, null);
    }

    using var stream = File.OpenRead(appSettingsPath);
    using var document = JsonDocument.Parse(stream);

    if (!document.RootElement.TryGetProperty("MongoDB", out var mongoDb))
    {
        return new MongoSettings(null, null);
    }

    var connectionString = mongoDb.TryGetProperty("ConnectionString", out var connectionStringProperty)
        ? connectionStringProperty.GetString()
        : null;

    var databaseName = mongoDb.TryGetProperty("DatabaseName", out var databaseNameProperty)
        ? databaseNameProperty.GetString()
        : null;

    return new MongoSettings(connectionString, databaseName);
}

internal sealed record MongoSettings(string? ConnectionString, string? DatabaseName);

internal sealed record CleanupCounts(
    int Documents,
    long Metadata,
    long Notifications,
    long AuditLogs,
    int FilesFromDocuments);

internal sealed class ToolOptions
{
    public bool Execute { get; private set; }
    public bool DeleteFiles { get; private set; }
    public bool IncludeAuditLogs { get; private set; }
    public bool IncludeNotifications { get; private set; }
    public string? BackendRoot { get; private set; }
    public string? ConnectionString { get; private set; }
    public string? DatabaseName { get; private set; }

    public static ToolOptions Parse(string[] args)
    {
        var options = new ToolOptions();

        for (var index = 0; index < args.Length; index++)
        {
            var arg = args[index];

            switch (arg)
            {
                case "--execute":
                    options.Execute = true;
                    break;
                case "--delete-files":
                    options.DeleteFiles = true;
                    break;
                case "--include-audit-logs":
                    options.IncludeAuditLogs = true;
                    break;
                case "--include-notifications":
                    options.IncludeNotifications = true;
                    break;
                case "--backend-root":
                    options.BackendRoot = ReadValue(args, ref index, arg);
                    break;
                case "--connection-string":
                    options.ConnectionString = ReadValue(args, ref index, arg);
                    break;
                case "--database-name":
                    options.DatabaseName = ReadValue(args, ref index, arg);
                    break;
                default:
                    throw new ArgumentException($"Unknown argument: {arg}");
            }
        }

        return options;
    }

    private static string ReadValue(string[] args, ref int index, string optionName)
    {
        if (index + 1 >= args.Length)
        {
            throw new ArgumentException($"Missing value for {optionName}");
        }

        index++;
        return args[index];
    }
}
