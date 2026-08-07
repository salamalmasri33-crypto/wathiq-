using eArchiveSystem.Application.DTOs;
using eArchiveSystem.Application.Exceptions;
using eArchiveSystem.Application.Interfaces.Persistence;
using eArchiveSystem.Application.Interfaces.Services;
using eArchiveSystem.Domain.Models;

namespace eArchiveSystem.Application.Services
{
    // Summarizes permission coverage and sample access checks.
    public class PermissionReviewService : IPermissionReviewService
    {
        private static readonly string[] ImplementedItems =
        {
            "InstitutionId and DepartmentId were added to users, documents, metadata, and search index.",
            "JWT now includes institutionId, departmentId, and department claims.",
            "Document access is enforced through a centralized authorization service.",
            "InstitutionAdmin is restricted to documents inside the same institution.",
            "Manager is restricted to documents inside the same institution and same department only.",
            "Employee is restricted to own documents only.",
            "Search scope follows the same institution and department rules.",
            "Document workflow implemented with status transitions: Draft -> Submitted -> Approved/Rejected -> Published"
        };

        private static readonly string[] PendingItems =
        {
            "Reports and dashboard still need endpoint-level verification after the new scoping changes.",
            "Audit visibility still needs real-world verification with institution and department test data."
        };

        private readonly IUserRepository _users;
        private readonly IDocumentRepository _documents;
        private readonly IDocumentAuthorizationService _authorization;

        public PermissionReviewService(
            IUserRepository users,
            IDocumentRepository documents,
            IDocumentAuthorizationService authorization)
        {
            _users = users;
            _documents = documents;
            _authorization = authorization;
        }

        public Task<PermissionCoverageDto> GetCoverageAsync()
        {
            return Task.FromResult(new PermissionCoverageDto
            {
                Implemented = ImplementedItems,
                Pending = PendingItems
            });
        }

        public async Task<CurrentPermissionScopeDto> GetCurrentScopeAsync(string userId)
        {
            var actor = await _users.GetByIdAsync(userId)
                ?? throw new NotFoundException("User not found");

            var selfScope = _authorization.BuildSearchScope(actor);
            var sameDepartmentMember = BuildSyntheticMember(actor, actor.InstitutionId, actor.DepartmentId ?? actor.Department);
            var otherDepartmentMember = BuildSyntheticMember(actor, actor.InstitutionId, "__other-department__");
            var otherInstitutionMember = BuildSyntheticMember(actor, "__other-institution__", actor.DepartmentId ?? actor.Department);

            return new CurrentPermissionScopeDto
            {
                UserId = actor.Id,
                Role = actor.Role,
                InstitutionId = actor.InstitutionId,
                DepartmentId = actor.DepartmentId,
                Department = actor.Department,
                SearchScope = selfScope,
                CanCreateForSelf = _authorization.CanAddForOwner(actor, actor),
                CanCreateForSameDepartmentMember = _authorization.CanAddForOwner(actor, sameDepartmentMember),
                CanCreateForOtherDepartmentMember = _authorization.CanAddForOwner(actor, otherDepartmentMember),
                CanCreateForOtherInstitutionMember = _authorization.CanAddForOwner(actor, otherInstitutionMember)
            };
        }

        public async Task<DocumentPermissionCheckDto> CheckDocumentAccessAsync(string userId, string documentId)
        {
            var actor = await _users.GetByIdAsync(userId)
                ?? throw new NotFoundException("User not found");

            var document = await _documents.GetByIdAsync(documentId)
                ?? throw new NotFoundException("Document not found");

            var canView = _authorization.CanView(actor, document);

            return new DocumentPermissionCheckDto
            {
                DocumentId = document.Id,
                // Hide sensitive document details when access is denied.
                OwnerUserId = canView ? document.UserId : null,
                InstitutionId = canView ? document.InstitutionId : null,
                DepartmentId = canView ? document.DepartmentId : null,
                Department = canView ? document.Department : null,
                Status = canView ? document.Status : default,
                CanView = canView,
                CanEdit = canView && _authorization.CanEdit(actor, document),
                CanDelete = canView && _authorization.CanDelete(actor, document),
                CanSubmit = canView && _authorization.CanSubmit(actor, document),
                CanStartReview = canView && _authorization.CanStartReview(actor, document),
                CanApprove = canView && _authorization.CanApprove(actor, document),
                CanReject = canView && _authorization.CanReject(actor, document),
                CanPublish = canView && _authorization.CanPublish(actor, document),
                CanArchive = canView && _authorization.CanArchive(actor, document)
            };
        }

        private static User BuildSyntheticMember(User actor, string? institutionId, string? departmentId)
        {
            return new User
            {
                Id = "__synthetic__",
                Name = "Synthetic Member",
                Email = "synthetic@example.com",
                Password = string.Empty,
                Role = Application.Security.ApplicationRoles.Employee,
                InstitutionId = institutionId,
                DepartmentId = departmentId,
                Department = departmentId
            };
        }
    }
}
