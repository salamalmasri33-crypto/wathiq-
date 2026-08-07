using eArchiveSystem.Application.Exceptions;
using eArchiveSystem.Application.Interfaces.Services;
using eArchiveSystem.Application.Security;
using eArchiveSystem.Domain.Models;

namespace eArchiveSystem.Application.Services;

public sealed class InstitutionScopeResolver : IInstitutionScopeResolver
{
    public string ResolveForAdministration(User requester, string? requestedInstitutionId)
    {
        if (ApplicationRoles.IsSystemAdmin(requester.Role))
            return RequireRequestedInstitution(requestedInstitutionId);

        if (!ApplicationRoles.IsInstitutionAdmin(requester.Role))
            throw new UnauthorizedActionException("You are not allowed to manage classification settings");

        return ResolveOwnInstitution(requester, requestedInstitutionId);
    }

    public string ResolveForMember(User requester, string? requestedInstitutionId)
    {
        if (ApplicationRoles.IsSystemAdmin(requester.Role))
            return RequireRequestedInstitution(requestedInstitutionId);

        if (!ApplicationRoles.IsInstitutionMember(requester.Role))
            throw new UnauthorizedActionException("You are not allowed to test classification");

        // Institution-scoped members never select the tenant for classification;
        // any client-supplied value is intentionally ignored.
        return RequireOwnInstitution(requester);
    }

    private static string RequireRequestedInstitution(string? value) =>
        string.IsNullOrWhiteSpace(value)
            ? throw new ValidationException("InstitutionId is required")
            : value.Trim();

    private static string ResolveOwnInstitution(User requester, string? requestedInstitutionId)
    {
        if (string.IsNullOrWhiteSpace(requester.InstitutionId))
            throw new ValidationException("User is not assigned to an institution");

        if (!string.IsNullOrWhiteSpace(requestedInstitutionId) &&
            !string.Equals(requestedInstitutionId.Trim(), requester.InstitutionId, StringComparison.OrdinalIgnoreCase))
            throw new UnauthorizedActionException("You can only access classification for your own institution");

        return requester.InstitutionId;
    }

    private static string RequireOwnInstitution(User requester) =>
        string.IsNullOrWhiteSpace(requester.InstitutionId)
            ? throw new ValidationException("User is not assigned to an institution")
            : requester.InstitutionId;
}
