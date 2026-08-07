using eArchiveSystem.Application.DTOs;
using eArchiveSystem.Domain.Models;

namespace eArchiveSystem.Application.Interfaces.Services
{
    public interface IDocumentService
    {
        Task<DocumentAddResult> AddDocumentAsync(string actorUserId, AddDocumentDto dto);
        Task<Document> GetByIdAsync(string id);
        Task DeleteDocumentAsync(string id, string userId, string role);
        Task<DocumentViewDto> ViewDocumentAsync(string documentId, string userId, string role);
        Task<DocumentOcrTextDto> GetExtractedTextAsync(string documentId, string userId, string role);
        Task<(Stream FileStream, string FileName, string ContentType)> DownloadDocumentAsync(
            string documentId,
            string userId,
            string role);
        Task<DocumentUpdateResult> UpdateDocumentAsync(
            string documentId,
            UpdateDocumentDto dto,
            string userId,
            string role);
        Task AttachMetadataAsync(string documentId);
    }
}
