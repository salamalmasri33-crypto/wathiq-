namespace eArchiveSystem.Domain.Models
{
    public class Report
    {
        public string UserId { get; set; }
        public int Uploads { get; set; }
        public int Updates { get; set; }
        public int Deletes { get; set; }
        public int Searches { get; set; }
        public int Downloads { get; set; }
    }
}

  