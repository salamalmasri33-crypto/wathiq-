using eArchiveSystem.Application.Interfaces.Persistence;
using eArchiveSystem.Domain.Models;
using MongoDB.Driver;

namespace eArchiveSystem.Infrastructure.Persistence.Repositories
{
    public class InstitutionSettingsRepository : IInstitutionSettingsRepository
    {
        private readonly IMongoCollection<InstitutionSettings> _settings;

        public InstitutionSettingsRepository(IMongoDatabase database)
        {
            _settings = database.GetCollection<InstitutionSettings>("InstitutionSettings");
        }

        public async Task<InstitutionSettings?> GetByInstitutionIdAsync(string institutionId)
        {
            return await _settings
                .Find(item => item.InstitutionId == institutionId)
                .FirstOrDefaultAsync();
        }

        public async Task UpsertAsync(InstitutionSettings settings)
        {
            await _settings.ReplaceOneAsync(
                item => item.InstitutionId == settings.InstitutionId,
                settings,
                new ReplaceOptions { IsUpsert = true });
        }
    }
}
