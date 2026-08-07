using eArchiveSystem.Application.DTOs;

namespace eArchiveSystem.Application.Interfaces.Services
{
    public interface IDocumentTimelineService
    {
        Task<DocumentTimelineDto> GetTimelineAsync(string documentId, string requesterId);
    }
}
