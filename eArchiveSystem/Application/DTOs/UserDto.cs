namespace eArchiveSystem.Application.DTOs
{
    public class UserDto
    {
        public string Id { get; set; }
        public string Name { get; set; }
        public string Email { get; set; }
        public string Role { get; set; }
        public string? InstitutionId { get; set; }
        public string? DepartmentId { get; set; }
        public string? Department { get; set; }
    }
}
 
