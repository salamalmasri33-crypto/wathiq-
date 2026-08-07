namespace eArchiveSystem.Application.DTOs
{
    public class InstitutionSettingsDto
    {
        public string InstitutionId { get; set; } = string.Empty;
        public string? InstitutionName { get; set; }
        public string? Description { get; set; }
        public string? ContactEmail { get; set; }
        public string TimeZone { get; set; } = "Asia/Damascus";
        public string DefaultLanguage { get; set; } = "ar";
        public string? BrandingPrimaryColor { get; set; }
        public DateTime UpdatedAt { get; set; }
    }
}
