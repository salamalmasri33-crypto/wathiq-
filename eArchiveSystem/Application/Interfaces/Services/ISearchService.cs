using eArchiveSystem.Application.DTOs;

namespace eArchiveSystem.Application.Interfaces.Services
{
    public interface ISearchService
    {
        Task<object> SearchDocumentsAsync(
            SearchDocumentsDto dto,
            string userId,
            string role);
    }
}
