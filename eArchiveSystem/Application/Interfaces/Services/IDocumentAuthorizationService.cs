using eArchiveSystem.Application.DTOs;
using eArchiveSystem.Domain.Models;

namespace eArchiveSystem.Application.Interfaces.Services
{
    public interface IDocumentAuthorizationService
    {
        bool CanAddForOwner(User actor, User owner);
        bool CanView(User actor, Document document);
        bool CanEdit(User actor, Document document);
        bool CanDelete(User actor, Document document);
        SearchAccessScope BuildSearchScope(User actor);

        // Workflow permissions
        bool CanSubmit(User actor, Document document);
        bool CanStartReview(User actor, Document document);
        bool CanApprove(User actor, Document document);
        bool CanReject(User actor, Document document);
        bool CanPublish(User actor, Document document);
        bool CanArchive(User actor, Document document);
        bool CanTransfer(User actor, Document document, Department targetDepartment);
    }
}
