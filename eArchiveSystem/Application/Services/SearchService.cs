using eArchiveSystem.Application.DTOs;
using eArchiveSystem.Application.Exceptions;
using eArchiveSystem.Application.Interfaces.Persistence;
using eArchiveSystem.Application.Interfaces.Services;
using eArchiveSystem.Application.Security;

namespace eArchiveSystem.Application.Services
{
    public class SearchService : ISearchService
    {
        private readonly IIndexingService _indexingService;
        private readonly IUserRepository _users;
        private readonly IDocumentAuthorizationService _authorization;
        private readonly IAuditService _audit;

        public SearchService(
            IIndexingService indexingService,
            IUserRepository users,
            IDocumentAuthorizationService authorization,
            IAuditService audit)
        {
            _indexingService = indexingService;
            _users = users;
            _authorization = authorization;
            _audit = audit;
        }

        public async Task<object> SearchDocumentsAsync(
            SearchDocumentsDto dto,
            string userId,
            string role)
        {
            await _audit.LogAsync(
                userId,
                role,
                "SearchDocuments",
                null,
                $"Search Query: {dto.Query}"
            );

            var actor = await _users.GetByIdAsync(userId);
            if (actor == null)
                throw new NotFoundException("User not found");

            var normalizedDto = new SearchDocumentsDto
            {
                Query = dto.Query,
                InstitutionId = ApplicationRoles.IsSystemAdmin(actor.Role) ? dto.InstitutionId?.Trim() : null,
                BroadGenre = dto.BroadGenre?.Trim(),
                SpecificGenre = dto.SpecificGenre?.Trim(),
                Department = dto.Department,
                DepartmentId = string.IsNullOrWhiteSpace(dto.DepartmentId) ? dto.Department : dto.DepartmentId,
                Status = dto.Status,
                Priority = dto.Priority,
                FromDate = dto.FromDate,
                ToDate = dto.ToDate,
                SortBy = dto.SortBy,
                Desc = dto.Desc,
                Page = dto.Page <= 0 ? 1 : dto.Page,
                PageSize = dto.PageSize <= 0 ? 10 : Math.Min(dto.PageSize, 50)
            };

            var scope = _authorization.BuildSearchScope(actor);
            var searchResult = await _indexingService.SearchAsync(normalizedDto, scope);

            return new
            {
                total = searchResult.Total,
                page = normalizedDto.Page,
                pageSize = normalizedDto.PageSize,
                data = searchResult.Results
            };
        }
    }
}
