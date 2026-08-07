using eArchiveSystem.Application.DTOs;
using eArchiveSystem.Domain.Models;

namespace eArchiveSystem.Application.Interfaces.Services
{


    public interface IMetadataService
    {

        // Adds metadata to a document.
        Task<bool> AddMetadataAsync(
            string documentId,
            AddMetadataDto dto,
            string userId,
            string role,
            CancellationToken cancellationToken = default
            
        );

        // Returns metadata for a document.
        Task<Metadata?> ViewMetadataAsync(
            string documentId,
            string userId,
            string role
            
        );

        // Updates existing metadata or creates it when missing.
        Task<bool> UpdateMetadataAsync(
            string documentId,
            AddMetadataDto dto,
            string userId,
            string role,
            CancellationToken cancellationToken = default
            
        );
    }
}
