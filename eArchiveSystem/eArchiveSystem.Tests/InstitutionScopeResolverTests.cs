using eArchiveSystem.Application.Exceptions;
using eArchiveSystem.Application.Security;
using eArchiveSystem.Application.Services;
using eArchiveSystem.Domain.Models;

namespace eArchiveSystem.Tests;

public sealed class InstitutionScopeResolverTests
{
    private readonly InstitutionScopeResolver _resolver = new();

    [Fact]
    public void InstitutionAdmin_uses_own_institution() =>
        Assert.Equal("institution-a", _resolver.ResolveForAdministration(User(ApplicationRoles.InstitutionAdmin), null));

    [Fact]
    public void InstitutionAdmin_cannot_select_another_institution() =>
        Assert.Throws<UnauthorizedActionException>(() => _resolver.ResolveForAdministration(User(ApplicationRoles.InstitutionAdmin), "institution-b"));

    [Fact]
    public void SystemAdmin_must_supply_institution() =>
        Assert.Throws<ValidationException>(() => _resolver.ResolveForAdministration(User(ApplicationRoles.SystemAdmin), null));

    [Theory]
    [InlineData(ApplicationRoles.Manager)]
    [InlineData(ApplicationRoles.Employee)]
    public void Members_can_classify_only_for_their_own_institution(string role) =>
        Assert.Equal("institution-a", _resolver.ResolveForMember(User(role), "institution-b"));

    [Theory]
    [InlineData(ApplicationRoles.Manager)]
    [InlineData(ApplicationRoles.Employee)]
    public void Members_cannot_administer_taxonomy(string role) =>
        Assert.Throws<UnauthorizedActionException>(() => _resolver.ResolveForAdministration(User(role), null));

    private static User User(string role) => new() { Id = "user-1", Name = "Test", Email = "test@example.com", Password = "x", Role = role, InstitutionId = "institution-a" };
}
