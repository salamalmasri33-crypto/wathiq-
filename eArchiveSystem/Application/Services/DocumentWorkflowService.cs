using eArchiveSystem.Application.DTOs;
using eArchiveSystem.Application.Exceptions;
using eArchiveSystem.Application.Interfaces.Persistence;
using eArchiveSystem.Application.Interfaces.Services;
using eArchiveSystem.Domain.Models;
using eArchiveSystem.Utils;

namespace eArchiveSystem.Application.Services
{
    public class DocumentWorkflowService : IDocumentWorkflowService
    {
        private readonly IUserRepository _users;
        private readonly IDocumentRepository _documents;
        private readonly IDepartmentRepository _departments;
        private readonly IMetadataRepository _metadata;
        private readonly IDocumentAuthorizationService _authorization;
        private readonly IAuditService _audit;
        private readonly IIndexingService _indexing;
        private readonly INotificationService _notifications;

        public DocumentWorkflowService(
            IUserRepository users,
            IDocumentRepository documents,
            IDepartmentRepository departments,
            IMetadataRepository metadata,
            IDocumentAuthorizationService authorization,
            IAuditService audit,
            IIndexingService indexing,
            INotificationService notifications)
        {
            _users = users;
            _documents = documents;
            _departments = departments;
            _metadata = metadata;
            _authorization = authorization;
            _audit = audit;
            _indexing = indexing;
            _notifications = notifications;
        }

        private static bool EnsureValidTransition(DocumentStatus current, DocumentStatus next)
        {
            return (current, next) switch
            {
                (DocumentStatus.Draft, DocumentStatus.Submitted) => true,
                (DocumentStatus.Rejected, DocumentStatus.Submitted) => true,
                (DocumentStatus.Submitted, DocumentStatus.UnderReview) => true,
                (DocumentStatus.UnderReview, DocumentStatus.Approved) => true,
                (DocumentStatus.UnderReview, DocumentStatus.Rejected) => true,
                (DocumentStatus.Approved, DocumentStatus.Published) => true,
                (DocumentStatus.Published, DocumentStatus.Archived) => true,
                _ => false
            };
        }

        public async Task<ServiceResult<WorkflowActionResultDto>> SubmitDocumentAsync(string userId, string documentId)
        {
            var actor = await _users.GetByIdAsync(userId)
                ?? throw new NotFoundException("User not found");

            var document = await _documents.GetByIdAsync(documentId)
                ?? throw new NotFoundException("Document not found");

            if (!_authorization.CanSubmit(actor, document))
                return ServiceResult<WorkflowActionResultDto>.Fail("Unauthorized to submit this document");

            if (!EnsureValidTransition(document.Status, DocumentStatus.Submitted))
                return ServiceResult<WorkflowActionResultDto>.Fail("Invalid status transition");

            var metadata = document.Metadata ?? await _metadata.GetByDocumentIdAsync(documentId);

            // Prevent submit if metadata is missing
            if (metadata == null)
                return ServiceResult<WorkflowActionResultDto>.Fail("Document metadata is required before submission");

            // Prevent submit if OCR is not completed (check if Content exists)
            if (string.IsNullOrWhiteSpace(document.Content) &&
                string.IsNullOrWhiteSpace(document.NormalizedOcrText) &&
                string.IsNullOrWhiteSpace(document.RawOcrText))
            {
                return ServiceResult<WorkflowActionResultDto>.Fail("OCR processing must be completed before submission");
            }

            var previousStatus = document.Status;
            document.Metadata = metadata;
            document.Status = DocumentStatus.Submitted;
            document.SubmittedAt = DateTime.Now;
            document.UpdatedAt = DateTime.Now;

            await _documents.UpdateAsync(document.Id, document);
            await _audit.LogAsync(userId, actor.Role, "SubmitDocument", documentId, $"Submitted document from {previousStatus}");
            await _indexing.SyncDocumentAsync(documentId);

            var resultDto = new WorkflowActionResultDto
            {
                DocumentId = document.Id,
                Status = document.Status,
                SubmittedAt = document.SubmittedAt
            };

            return ServiceResult<WorkflowActionResultDto>.Ok(resultDto);
        }

        public async Task<ServiceResult<WorkflowActionResultDto>> StartReviewAsync(string userId, string documentId)
        {
            var actor = await _users.GetByIdAsync(userId)
                ?? throw new NotFoundException("User not found");

            var document = await _documents.GetByIdAsync(documentId)
                ?? throw new NotFoundException("Document not found");

            if (!_authorization.CanStartReview(actor, document))
                return ServiceResult<WorkflowActionResultDto>.Fail("Unauthorized to start review on this document");

            if (!EnsureValidTransition(document.Status, DocumentStatus.UnderReview))
                return ServiceResult<WorkflowActionResultDto>.Fail("Invalid status transition");

            var previousStatus = document.Status;
            document.Status = DocumentStatus.UnderReview;
            document.ReviewStartedAt = DateTime.Now;
            document.UpdatedAt = DateTime.Now;

            await _documents.UpdateAsync(document.Id, document);
            await _audit.LogAsync(userId, actor.Role, "StartReview", documentId, $"Started review on document from {previousStatus}");
            await _indexing.SyncDocumentAsync(documentId);

            var resultDto = new WorkflowActionResultDto
            {
                DocumentId = document.Id,
                Status = document.Status,
                SubmittedAt = document.SubmittedAt,
                ReviewStartedAt = document.ReviewStartedAt
            };

            return ServiceResult<WorkflowActionResultDto>.Ok(resultDto);
        }
        public async Task<ServiceResult<WorkflowActionResultDto>> ApproveDocumentAsync(string userId, string documentId, ReviewDecisionDto? decision = null)
        {
            var actor = await _users.GetByIdAsync(userId)
                ?? throw new NotFoundException("User not found");

            var document = await _documents.GetByIdAsync(documentId)
                ?? throw new NotFoundException("Document not found");

            if (!_authorization.CanApprove(actor, document))
                return ServiceResult<WorkflowActionResultDto>.Fail("Unauthorized to approve this document");

            if (!EnsureValidTransition(document.Status, DocumentStatus.Approved))
                return ServiceResult<WorkflowActionResultDto>.Fail("Invalid status transition");

            var previousStatus = document.Status;
            document.Status = DocumentStatus.Approved;
            document.ReviewedAt = DateTime.Now;
            document.ReviewedByUserId = userId;
            document.UpdatedAt = DateTime.Now;

            await _documents.UpdateAsync(document.Id, document);
            await _audit.LogAsync(userId, actor.Role, "ApproveDocument", documentId, $"Approved document from {previousStatus}");
            await _indexing.SyncDocumentAsync(documentId);
            await _notifications.NotifyDocumentApprovedAsync(document, actor);

            var resultDto = new WorkflowActionResultDto
            {
                DocumentId = document.Id,
                Status = document.Status,
                SubmittedAt = document.SubmittedAt,
                ReviewStartedAt = document.ReviewStartedAt,
                ReviewedAt = document.ReviewedAt
            };

            return ServiceResult<WorkflowActionResultDto>.Ok(resultDto);
        }

        public async Task<ServiceResult<WorkflowActionResultDto>> RejectDocumentAsync(string userId, string documentId, ReviewDecisionDto decision)
        {
            if (string.IsNullOrWhiteSpace(decision.Comment))
                return ServiceResult<WorkflowActionResultDto>.Fail("Rejection comment is required");

            var actor = await _users.GetByIdAsync(userId)
                ?? throw new NotFoundException("User not found");

            var document = await _documents.GetByIdAsync(documentId)
                ?? throw new NotFoundException("Document not found");

            if (!_authorization.CanReject(actor, document))
                return ServiceResult<WorkflowActionResultDto>.Fail("Unauthorized to reject this document");

            if (!EnsureValidTransition(document.Status, DocumentStatus.Rejected))
                return ServiceResult<WorkflowActionResultDto>.Fail("Invalid status transition");

            var previousStatus = document.Status;
            document.Status = DocumentStatus.Rejected;
            document.ReviewedAt = DateTime.Now;
            document.ReviewedByUserId = userId;
            document.RejectionReason = decision.Comment;
            document.UpdatedAt = DateTime.Now;

            await _documents.UpdateAsync(document.Id, document);
            await _audit.LogAsync(userId, actor.Role, "RejectDocument", documentId, $"Rejected document from {previousStatus}: {decision.Comment}");
            await _indexing.SyncDocumentAsync(documentId);
            await _notifications.NotifyDocumentRejectedAsync(document, actor, decision.Comment);

            var resultDto = new WorkflowActionResultDto
            {
                DocumentId = document.Id,
                Status = document.Status,
                SubmittedAt = document.SubmittedAt,
                ReviewStartedAt = document.ReviewStartedAt,
                ReviewedAt = document.ReviewedAt,
                RejectionReason = document.RejectionReason
            };

            return ServiceResult<WorkflowActionResultDto>.Ok(resultDto);
        }

        public async Task<ServiceResult<WorkflowActionResultDto>> PublishDocumentAsync(string userId, string documentId)
        {
            var actor = await _users.GetByIdAsync(userId)
                ?? throw new NotFoundException("User not found");

            var document = await _documents.GetByIdAsync(documentId)
                ?? throw new NotFoundException("Document not found");

            if (!_authorization.CanPublish(actor, document))
                return ServiceResult<WorkflowActionResultDto>.Fail("Unauthorized to publish this document");

            if (!EnsureValidTransition(document.Status, DocumentStatus.Published))
                return ServiceResult<WorkflowActionResultDto>.Fail("Invalid status transition");

            var previousStatus = document.Status;
            document.Status = DocumentStatus.Published;
            document.PublishedAt = DateTime.Now;
            document.PublishedByUserId = userId;
            document.UpdatedAt = DateTime.Now;

            await _documents.UpdateAsync(document.Id, document);
            await _audit.LogAsync(userId, actor.Role, "PublishDocument", documentId, $"Published document from {previousStatus}");
            await _indexing.SyncDocumentAsync(documentId);

            var resultDto = new WorkflowActionResultDto
            {
                DocumentId = document.Id,
                Status = document.Status,
                SubmittedAt = document.SubmittedAt,
                ReviewStartedAt = document.ReviewStartedAt,
                ReviewedAt = document.ReviewedAt,
                PublishedAt = document.PublishedAt
            };

            return ServiceResult<WorkflowActionResultDto>.Ok(resultDto);
        }

        public async Task<ServiceResult<WorkflowActionResultDto>> ArchiveDocumentAsync(string userId, string documentId)
        {
            var actor = await _users.GetByIdAsync(userId)
                ?? throw new NotFoundException("User not found");

            var document = await _documents.GetByIdAsync(documentId)
                ?? throw new NotFoundException("Document not found");

            if (!_authorization.CanArchive(actor, document))
                return ServiceResult<WorkflowActionResultDto>.Fail("Unauthorized to archive this document");

            if (!EnsureValidTransition(document.Status, DocumentStatus.Archived))
                return ServiceResult<WorkflowActionResultDto>.Fail("Invalid status transition");

            var previousStatus = document.Status;
            document.Status = DocumentStatus.Archived;
            document.ArchivedAt = DateTime.Now;
            document.ArchivedByUserId = userId;
            document.UpdatedAt = DateTime.Now;

            await _documents.UpdateAsync(document.Id, document);
            await _audit.LogAsync(userId, actor.Role, "ArchiveDocument", documentId, $"Archived document from {previousStatus}");
            await _indexing.SyncDocumentAsync(documentId);

            var resultDto = new WorkflowActionResultDto
            {
                DocumentId = document.Id,
                Status = document.Status,
                SubmittedAt = document.SubmittedAt,
                ReviewStartedAt = document.ReviewStartedAt,
                ReviewedAt = document.ReviewedAt,
                PublishedAt = document.PublishedAt,
                ArchivedAt = document.ArchivedAt
            };

            return ServiceResult<WorkflowActionResultDto>.Ok(resultDto);
        }

        public async Task<ServiceResult<DocumentTransferResultDto>> TransferDocumentAsync(string userId, string documentId, TransferDocumentDto dto)
        {
            if (string.IsNullOrWhiteSpace(dto.TargetDepartmentId))
                return ServiceResult<DocumentTransferResultDto>.Fail("Target department is required");

            if (string.IsNullOrWhiteSpace(dto.Justification))
                return ServiceResult<DocumentTransferResultDto>.Fail("Transfer justification is required");

            var actor = await _users.GetByIdAsync(userId)
                ?? throw new NotFoundException("User not found");

            var document = await _documents.GetByIdAsync(documentId)
                ?? throw new NotFoundException("Document not found");

            if (document.Status == DocumentStatus.Archived)
                return ServiceResult<DocumentTransferResultDto>.Fail("Archived documents cannot be transferred");

            var targetDepartment = await _departments.GetByIdAsync(dto.TargetDepartmentId.Trim())
                ?? throw new NotFoundException("Target department not found");

            if (!_authorization.CanTransfer(actor, document, targetDepartment))
                return ServiceResult<DocumentTransferResultDto>.Fail("Unauthorized to transfer this document");

            if (string.Equals(document.DepartmentId, targetDepartment.Id, StringComparison.OrdinalIgnoreCase))
                return ServiceResult<DocumentTransferResultDto>.Fail("Document is already assigned to this department");

            var previousDepartmentId = document.DepartmentId;
            var previousDepartmentName = document.Department;
            var transferredAt = DateTime.UtcNow;

            document.DepartmentId = targetDepartment.Id;
            document.Department = targetDepartment.Name;
            document.UpdatedAt = transferredAt;

            await _documents.UpdateAsync(document.Id, document);

            var metadata = await _metadata.GetByDocumentIdAsync(documentId);
            if (metadata != null)
            {
                metadata.DepartmentId = targetDepartment.Id;
                metadata.Department = targetDepartment.Name;
                metadata.UpdatedAt = transferredAt;
                await _metadata.UpsertAsync(metadata);
                await _documents.UpdateMetadataFieldsAsync(document.Id, metadata);
            }

            await _audit.LogAsync(
                userId,
                actor.Role,
                "TransferDocument",
                documentId,
                $"Transferred document from department '{previousDepartmentName ?? previousDepartmentId ?? "Unknown"}' to '{targetDepartment.Name}'. Justification: {dto.Justification.Trim()}");

            await _indexing.SyncDocumentAsync(documentId);
            await _notifications.NotifyDocumentTransferredAsync(document, actor, previousDepartmentName ?? previousDepartmentId, targetDepartment, dto.Justification);

            var resultDto = new DocumentTransferResultDto
            {
                DocumentId = document.Id,
                Status = document.Status,
                PreviousDepartmentId = previousDepartmentId,
                PreviousDepartmentName = previousDepartmentName,
                TargetDepartmentId = targetDepartment.Id,
                TargetDepartmentName = targetDepartment.Name,
                Justification = dto.Justification.Trim(),
                TransferredAt = transferredAt
            };

            return ServiceResult<DocumentTransferResultDto>.Ok(resultDto);
        }
    }
}
