namespace eArchiveSystem.Application.Security
{
    public static class ApplicationRoles
    {
        public const string SystemAdmin = "SystemAdmin";
        public const string InstitutionAdmin = "InstitutionAdmin";
        public const string Manager = "Manager";
        public const string Employee = "Employee";

        public static bool IsSystemAdmin(string? role) =>
            role == SystemAdmin;

        public static bool IsInstitutionAdmin(string? role) =>
            role == InstitutionAdmin;

        public static bool IsManager(string? role) =>
            role == Manager;

        public static bool IsEmployee(string? role) =>
            role == Employee;

        public static bool IsInstitutionMember(string? role) =>
            IsInstitutionAdmin(role) || IsManager(role) || IsEmployee(role);
    }
}
