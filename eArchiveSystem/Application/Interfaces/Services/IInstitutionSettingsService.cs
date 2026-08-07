using eArchiveSystem.Application.DTOs;

namespace eArchiveSystem.Application.Interfaces.Services
{
    public interface IInstitutionSettingsService
    {
        Task<InstitutionSettingsDto> GetSettingsAsync(string requesterId, string? requestedInstitutionId = null);
        Task<InstitutionSettingsDto> UpdateSettingsAsync(string requesterId, UpdateInstitutionSettingsDto dto);
    }
}
