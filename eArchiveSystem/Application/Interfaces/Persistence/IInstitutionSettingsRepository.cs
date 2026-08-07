using eArchiveSystem.Domain.Models;

namespace eArchiveSystem.Application.Interfaces.Persistence
{
    public interface IInstitutionSettingsRepository
    {
        Task<InstitutionSettings?> GetByInstitutionIdAsync(string institutionId);
        Task UpsertAsync(InstitutionSettings settings);
    }
}
