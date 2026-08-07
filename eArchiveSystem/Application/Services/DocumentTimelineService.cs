using eArchiveSystem.Application.DTOs;
using eArchiveSystem.Application.Exceptions;
using eArchiveSystem.Application.Interfaces.Persistence;
using eArchiveSystem.Application.Interfaces.Services;
using eArchiveSystem.Domain.Models;

namespace eArchiveSystem.Application.Services
{
    public class DocumentTimelineService : IDocumentTimelineService
    {
        private readonly IDocumentRepository _documents;
        private readonly IUserRepository _users;
        private readonly IAuditRepository _auditLogs;
        private readonly IDocumentAuthorizationService _authorization;

        public DocumentTimelineService(
            IDocumentRepository documents,
            IUserRepository users,
            IAuditRepository auditLogs,
            IDocumentAuthorizationService authorization)
        {
            _documents = documents;
            _users = users;
            _auditLogs = auditLogs;
            _authorization = authorization;
        }

        public async Task<DocumentTimelineDto> GetTimelineAsync(string documentId, string requesterId)
        {
            var actor = await _users.GetByIdAsync(requesterId)
                ?? throw new NotFoundException("User not found");

            var document = await _documents.GetByIdAsync(documentId)
                ?? throw new NotFoundException("Document not found");

            if (!_authorization.CanView(actor, document))
                throw new UnauthorizedActionException("You are not allowed to view this document timeline");

            var auditLogs = await _auditLogs.GetByDocumentIdAsync(documentId);

            var relatedUserIds = auditLogs
                .Select(log => log.UserId)
                .Concat(new[]
                {
                    document.UserId,
                    document.ReviewedByUserId,
                    document.PublishedByUserId,
                    document.ArchivedByUserId
                })
                .Where(id => !string.IsNullOrWhiteSpace(id))
                .Distinct()
                .ToList();

            var users = await _users.GetByIdsAsync(relatedUserIds);
            var userLookup = users.ToDictionary(user => user.Id, user => user);

            var events = auditLogs
                .Select(log => MapAuditLog(log, userLookup))
                .ToList();

            AddWorkflowEventIfMissing(
                events,
                auditLogs,
                document.CreatedAt,
                "DocumentCreated",
                "Document was created",
                document.UserId,
                userLookup);

            AddWorkflowEventIfMissing(
                events,
                auditLogs,
                document.SubmittedAt,
                "SubmitDocument",
                "Document was submitted for review",
                document.UserId,
                userLookup);

            AddWorkflowEventIfMissing(
                events,
                auditLogs,
                document.ReviewStartedAt,
                "StartReview",
                "Review started",
                document.ReviewedByUserId,
                userLookup);

            if (document.Status == DocumentStatus.Approved)
            {
                AddWorkflowEventIfMissing(
                    events,
                    auditLogs,
                    document.ReviewedAt,
                    "ApproveDocument",
                    "Document was approved",
                    document.ReviewedByUserId,
                    userLookup);
            }

            if (document.Status == DocumentStatus.Rejected)
            {
                var rejectionDescription = string.IsNullOrWhiteSpace(document.RejectionReason)
                    ? "Document was rejected"
                    : $"Document was rejected: {document.RejectionReason}";

                AddWorkflowEventIfMissing(
                    events,
                    auditLogs,
                    document.ReviewedAt,
                    "RejectDocument",
                    rejectionDescription,
                    document.ReviewedByUserId,
                    userLookup);
            }

            AddWorkflowEventIfMissing(
                events,
                auditLogs,
                document.PublishedAt,
                "PublishDocument",
                "Document was published",
                document.PublishedByUserId,
                userLookup);

            AddWorkflowEventIfMissing(
                events,
                auditLogs,
                document.ArchivedAt,
                "ArchiveDocument",
                "Document was archived",
                document.ArchivedByUserId,
                userLookup);

            var owner = userLookup.GetValueOrDefault(document.UserId);
            var reviewedBy = GetUser(userLookup, document.ReviewedByUserId);
            var publishedBy = GetUser(userLookup, document.PublishedByUserId);
            var archivedBy = GetUser(userLookup, document.ArchivedByUserId);

            return new DocumentTimelineDto
            {
                DocumentId = document.Id,
                Title = document.Title,
                Status = document.Status,
                OwnerUserId = document.UserId,
                OwnerName = owner?.Name,
                InstitutionId = document.InstitutionId,
                DepartmentId = document.DepartmentId,
                Department = document.Department,
                CreatedAt = document.CreatedAt,
                UpdatedAt = document.UpdatedAt,
                SubmittedAt = document.SubmittedAt,
                ReviewStartedAt = document.ReviewStartedAt,
                ReviewedAt = document.ReviewedAt,
                PublishedAt = document.PublishedAt,
                ArchivedAt = document.ArchivedAt,
                ReviewedByUserId = document.ReviewedByUserId,
                ReviewedByName = reviewedBy?.Name,
                PublishedByUserId = document.PublishedByUserId,
                PublishedByName = publishedBy?.Name,
                ArchivedByUserId = document.ArchivedByUserId,
                ArchivedByName = archivedBy?.Name,
                RejectionReason = document.RejectionReason,
                Events = events
                    .OrderBy(eventItem => eventItem.OccurredAt)
                    .ToList()
            };
        }

        private static DocumentTimelineEventDto MapAuditLog(
            AuditLog log,
            IReadOnlyDictionary<string, User> userLookup)
        {
            var actor = GetUser(userLookup, log.UserId);

            return new DocumentTimelineEventDto
            {
                OccurredAt = log.Timestamp,
                Source = "Audit",
                Action = log.Action,
                Description = log.Description,
                ActorUserId = log.UserId,
                ActorName = log.UserId == "SYSTEM" ? "System" : actor?.Name,
                ActorRole = string.IsNullOrWhiteSpace(log.UserRole) ? actor?.Role : log.UserRole
            };
        }

        private static void AddWorkflowEventIfMissing(
            ICollection<DocumentTimelineEventDto> events,
            IReadOnlyCollection<AuditLog> auditLogs,
            DateTime? timestamp,
            string action,
            string description,
            string? actorUserId,
            IReadOnlyDictionary<string, User> userLookup)
        {
            if (!timestamp.HasValue)
                return;

            if (auditLogs.Any(log => string.Equals(log.Action, action, StringComparison.OrdinalIgnoreCase)))
                return;

            var actor = GetUser(userLookup, actorUserId);

            events.Add(new DocumentTimelineEventDto
            {
                OccurredAt = timestamp.Value,
                Source = "Workflow",
                Action = action,
                Description = description,
                ActorUserId = actorUserId,
                ActorName = actor?.Name,
                ActorRole = actor?.Role
            });
        }

        private static User? GetUser(IReadOnlyDictionary<string, User> userLookup, string? userId)
        {
            if (string.IsNullOrWhiteSpace(userId))
                return null;

            userLookup.TryGetValue(userId, out var user);
            return user;
        }
    }
}
