using eArchiveSystem.Domain.Models;

namespace eArchiveSystem.Application.Interfaces.Services;

public interface IInstitutionScopeResolver
{
    string ResolveForAdministration(User requester, string? requestedInstitutionId);
    string ResolveForMember(User requester, string? requestedInstitutionId);
}
