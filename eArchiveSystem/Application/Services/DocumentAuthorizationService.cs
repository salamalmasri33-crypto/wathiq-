using eArchiveSystem.Application.DTOs;
using eArchiveSystem.Application.Interfaces.Services;
using eArchiveSystem.Application.Security;
using eArchiveSystem.Domain.Models;

namespace eArchiveSystem.Application.Services
{
    public class DocumentAuthorizationService : IDocumentAuthorizationService
    {
        public bool CanAddForOwner(User actor, User owner)
        {
            if (ApplicationRoles.IsManager(actor.Role))
                return SameInstitution(actor, owner) && SameDepartment(actor, owner);

            return actor.Id == owner.Id;
        }

        public bool CanView(User actor, Document document)
        {
            if (ApplicationRoles.IsSystemAdmin(actor.Role))
                return true;

            if (ApplicationRoles.IsInstitutionAdmin(actor.Role))
                return SameInstitution(actor, document);

            if (ApplicationRoles.IsManager(actor.Role))
                return SameInstitution(actor, document) && SameDepartment(actor, document);

            return document.UserId == actor.Id;
        }

        public bool CanEdit(User actor, Document document)
        {
            var canEditMetadataStatus =
                document.Status == DocumentStatus.Draft ||
                document.Status == DocumentStatus.Rejected ||
                document.Status == DocumentStatus.Processing;

            if (ApplicationRoles.IsEmployee(actor.Role))
                return canEditMetadataStatus && document.UserId == actor.Id;

            if (ApplicationRoles.IsManager(actor.Role))
                return canEditMetadataStatus && SameInstitution(actor, document) && SameDepartment(actor, document);

            return false;
        }

        public bool CanDelete(User actor, Document document)
        {
            // Draft, Rejected, and stuck OCR Processing documents can be deleted.
            if (document.Status != DocumentStatus.Draft &&
                document.Status != DocumentStatus.Rejected &&
                document.Status != DocumentStatus.Processing)
            {
                return false;
            }

            if (document.Status == DocumentStatus.Processing)
            {
                if (ApplicationRoles.IsSystemAdmin(actor.Role))
                    return true;

                if (ApplicationRoles.IsInstitutionAdmin(actor.Role))
                    return SameInstitution(actor, document);
            }

            if (ApplicationRoles.IsManager(actor.Role))
                return SameInstitution(actor, document) && SameDepartment(actor, document);

            return document.UserId == actor.Id;
        }

        public SearchAccessScope BuildSearchScope(User actor)
        {
            if (ApplicationRoles.IsSystemAdmin(actor.Role))
                return new SearchAccessScope();

            if (ApplicationRoles.IsInstitutionAdmin(actor.Role))
            {
                return new SearchAccessScope
                {
                    InstitutionId = NormalizeInstitution(actor.InstitutionId)
                };
            }

            if (ApplicationRoles.IsManager(actor.Role))
            {
                return new SearchAccessScope
                {
                    InstitutionId = NormalizeInstitution(actor.InstitutionId),
                    DepartmentId = NormalizeDepartment(actor.DepartmentId, actor.Department)
                };
            }

            return new SearchAccessScope
            {
                OwnerUserId = actor.Id
            };
        }

        private static bool SameInstitution(User actor, User target)
        {
            var actorInstitution = NormalizeInstitution(actor.InstitutionId);
            var targetInstitution = NormalizeInstitution(target.InstitutionId);

            if (string.IsNullOrWhiteSpace(actorInstitution) || string.IsNullOrWhiteSpace(targetInstitution))
                return false;

            return string.Equals(actorInstitution, targetInstitution, StringComparison.OrdinalIgnoreCase);
        }

        private static bool SameInstitution(User actor, Document document)
        {
            var actorInstitution = NormalizeInstitution(actor.InstitutionId);
            var documentInstitution = NormalizeInstitution(document.InstitutionId);

            if (string.IsNullOrWhiteSpace(actorInstitution) || string.IsNullOrWhiteSpace(documentInstitution))
                return false;

            return string.Equals(actorInstitution, documentInstitution, StringComparison.OrdinalIgnoreCase);
        }

        private static bool SameDepartment(User actor, User target)
        {
            var actorDepartment = NormalizeDepartment(actor.DepartmentId, actor.Department);
            var targetDepartment = NormalizeDepartment(target.DepartmentId, target.Department);

            if (string.IsNullOrWhiteSpace(actorDepartment) || string.IsNullOrWhiteSpace(targetDepartment))
                return false;

            return string.Equals(actorDepartment, targetDepartment, StringComparison.OrdinalIgnoreCase);
        }

        private static bool SameDepartment(User actor, Document document)
        {
            var actorDepartment = NormalizeDepartment(actor.DepartmentId, actor.Department);
            var documentDepartment = NormalizeDepartment(document.DepartmentId, document.Department);

            if (string.IsNullOrWhiteSpace(actorDepartment) || string.IsNullOrWhiteSpace(documentDepartment))
                return false;

            return string.Equals(actorDepartment, documentDepartment, StringComparison.OrdinalIgnoreCase);
        }

        private static string? NormalizeInstitution(string? institutionId) =>
            string.IsNullOrWhiteSpace(institutionId) ? null : institutionId.Trim();

        private static string? NormalizeDepartment(string? departmentId, string? fallbackDepartment) =>
            !string.IsNullOrWhiteSpace(departmentId)
                ? departmentId.Trim()
                : string.IsNullOrWhiteSpace(fallbackDepartment)
                    ? null
                    : fallbackDepartment.Trim();

        // Workflow permissions
        public bool CanSubmit(User actor, Document document)
        {
            // Only the owner can submit a draft or resubmit a rejected document.
            return document.UserId == actor.Id &&
                   (document.Status == DocumentStatus.Draft || document.Status == DocumentStatus.Rejected);
        }

        public bool CanApprove(User actor, Document document)
        {
            // Manager can approve submitted documents in same institution and department
            return ApplicationRoles.IsManager(actor.Role) &&
                   document.Status == DocumentStatus.Submitted &&
                   SameInstitution(actor, document) &&
                   SameDepartment(actor, document);
        }

        public bool CanReject(User actor, Document document)
        {
            // Manager can reject submitted documents in same institution and department
            return ApplicationRoles.IsManager(actor.Role) &&
                   document.Status == DocumentStatus.Submitted &&
                   SameInstitution(actor, document) &&
                   SameDepartment(actor, document);
        }

        public bool CanPublish(User actor, Document document)
        {
            // InstitutionAdmin can publish approved documents in same institution
            return ApplicationRoles.IsInstitutionAdmin(actor.Role) &&
                   document.Status == DocumentStatus.Approved &&
                   SameInstitution(actor, document);
        }

        public bool CanStartReview(User actor, Document document)
        {
            // Manager can start review on submitted documents in same institution and department
            return ApplicationRoles.IsManager(actor.Role) &&
                   document.Status == DocumentStatus.Submitted &&
                   SameInstitution(actor, document) &&
                   SameDepartment(actor, document);
        }

        public bool CanArchive(User actor, Document document)
        {
            // InstitutionAdmin can archive published documents in same institution
            return ApplicationRoles.IsInstitutionAdmin(actor.Role) &&
                   document.Status == DocumentStatus.Published &&
                   SameInstitution(actor, document);
        }

        public bool CanTransfer(User actor, Document document, Department targetDepartment)
        {
            if (!string.Equals(document.InstitutionId, targetDepartment.InstitutionId, StringComparison.OrdinalIgnoreCase))
                return false;

            if (ApplicationRoles.IsSystemAdmin(actor.Role))
                return true;

            if (ApplicationRoles.IsInstitutionAdmin(actor.Role))
            {
                return SameInstitution(actor, document) &&
                       string.Equals(actor.InstitutionId, targetDepartment.InstitutionId, StringComparison.OrdinalIgnoreCase);
            }

            if (ApplicationRoles.IsManager(actor.Role))
            {
                return SameInstitution(actor, document) &&
                       SameDepartment(actor, document) &&
                       string.Equals(actor.InstitutionId, targetDepartment.InstitutionId, StringComparison.OrdinalIgnoreCase);
            }

            return false;
        }
    }
}
