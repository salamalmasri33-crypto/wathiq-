namespace eArchiveSystem.Application.DTOs
{
    public class UpdateInstitutionSettingsDto
    {
        public string? InstitutionId { get; set; }
        public string? InstitutionName { get; set; }
        public string? Description { get; set; }
        public string? ContactEmail { get; set; }
        public string? TimeZone { get; set; }
        public string? DefaultLanguage { get; set; }
        public string? BrandingPrimaryColor { get; set; }
    }
}
