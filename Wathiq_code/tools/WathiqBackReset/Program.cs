// See https://aka.ms/new-console-template for more information
using MongoDB.Bson;
using MongoDB.Driver;

static string? GetArgValue(string[] args, string name)
{
    var match = args
        .Select((value, index) => new { value, index })
        .FirstOrDefault(entry =>
            string.Equals(entry.value, name, StringComparison.OrdinalIgnoreCase) &&
            entry.index + 1 < args.Length);

    return match == null ? null : args[match.index + 1];
}

static bool HasFlag(string[] args, string name)
{
    return args.Any(a => string.Equals(a, name, StringComparison.OrdinalIgnoreCase));
}

static string ResolveDbName(string? dbArg, string? envDbName)
{
    var value = (dbArg ?? envDbName ?? "eArchiveDB").Trim();
    return string.IsNullOrWhiteSpace(value) ? "eArchiveDB" : value;
}

var mongoUrl = (GetArgValue(args, "--mongo") ?? Environment.GetEnvironmentVariable("WATHIQ_MONGO_URL") ?? "mongodb://localhost:27017").Trim();
var dbName = ResolveDbName(GetArgValue(args, "--db"), Environment.GetEnvironmentVariable("WATHIQ_MONGO_DB"));
var email = (GetArgValue(args, "--email") ?? Environment.GetEnvironmentVariable("WATHIQ_ADMIN_EMAIL") ?? "admin@example.com").Trim();
var role = (GetArgValue(args, "--role") ?? Environment.GetEnvironmentVariable("WATHIQ_ADMIN_ROLE") ?? "SystemAdmin").Trim();
var dryRun = HasFlag(args, "--dry-run");

Console.WriteLine("WathiqBackReset (Mongo role fix)");
Console.WriteLine($"Mongo: {mongoUrl}");
Console.WriteLine($"DB: {dbName}");
Console.WriteLine($"Target Email: {email}");
Console.WriteLine($"New Role: {role}");
Console.WriteLine($"Dry Run: {dryRun}");
Console.WriteLine();

var client = new MongoClient(mongoUrl);
var database = client.GetDatabase(dbName);
var users = database.GetCollection<BsonDocument>("Users");

var emailFilter = Builders<BsonDocument>.Filter.Or(
    Builders<BsonDocument>.Filter.Eq("email", email),
    Builders<BsonDocument>.Filter.Eq("Email", email));

var foundUsers = await users.Find(emailFilter).ToListAsync();

Console.WriteLine($"Found {foundUsers.Count} user(s) with email '{email}'.");

if (foundUsers.Count == 0)
{
    Console.WriteLine("Nothing to update. If this is a fresh DB, start the API once so it seeds the bootstrap admin.");
    return;
}

Console.WriteLine("Sample document (first match):");
Console.WriteLine(foundUsers[0].ToJson(new MongoDB.Bson.IO.JsonWriterSettings { Indent = true }));
Console.WriteLine();

var now = DateTime.UtcNow;

var update = Builders<BsonDocument>.Update
    // Backend models use lower-case BSON element names (see eArchiveSystem.Domain.Models.User attributes).
    // Adding extra PascalCase fields can break deserialization, so we keep the update strict and also
    // remove any previously injected fields from earlier runs.
    .Set("role", role)
    .Set("updatedAt", now)
    .Unset("Role")
    .Unset("UpdatedAt");

if (dryRun)
{
    Console.WriteLine("Dry-run enabled; no changes were written.");
    return;
}

var result = await users.UpdateManyAsync(emailFilter, update);

Console.WriteLine($"Matched: {result.MatchedCount} | Modified: {result.ModifiedCount}");
Console.WriteLine("Done.");
