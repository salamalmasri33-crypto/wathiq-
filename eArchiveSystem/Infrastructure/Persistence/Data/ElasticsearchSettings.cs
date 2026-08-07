namespace eArchiveSystem.Infrastructure.Persistence.Data
{
    public class ElasticsearchSettings
    {
        public string Url { get; set; } = "http://localhost:9200";
        public string IndexName { get; set; } = "documents";
        public string Username { get; set; } = "elastic";
        public string Password { get; set; } = "";
    }
}
