namespace eArchiveSystem.Infrastructure.Configuration;

public sealed class AraGenreOptions
{
    public string BaseUrl { get; init; } = "http://127.0.0.1:8001";
    public int TimeoutSeconds { get; init; } = 120;
    public bool Enabled { get; init; } = true;
    public long MaxImportFileBytes { get; init; } = 10 * 1024 * 1024;
}
