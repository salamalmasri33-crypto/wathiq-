namespace eArchiveSystem.Application.DTOs
{
    public class UpdateUserDto
    {
        public string? Name { get; set; }
        public string? Email { get; set; }
        public string? NewPassword { get; set; }
        public string? InstitutionId { get; set; }
        public string? DepartmentId { get; set; }
        public string? Department { get; set; }
    }
}
