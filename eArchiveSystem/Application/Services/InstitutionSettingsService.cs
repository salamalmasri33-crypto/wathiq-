using eArchiveSystem.Application.DTOs;
using eArchiveSystem.Application.Exceptions;
using eArchiveSystem.Application.Interfaces.Persistence;
using eArchiveSystem.Application.Interfaces.Services;
using eArchiveSystem.Application.Security;
using eArchiveSystem.Domain.Models;

namespace eArchiveSystem.Application.Services
{
    public class InstitutionSettingsService : IInstitutionSettingsService
    {
        private readonly IUserRepository _users;
        private readonly IInstitutionSettingsRepository _settings;

        public InstitutionSettingsService(
            IUserRepository users,
            IInstitutionSettingsRepository settings)
        {
            _users = users;
            _settings = settings;
        }

        public async Task<InstitutionSettingsDto> GetSettingsAsync(string requesterId, string? requestedInstitutionId = null)
        {
            var requester = await _users.GetByIdAsync(requesterId)
                ?? throw new NotFoundException("User not found");

            var institutionId = ResolveInstitutionId(requester, requestedInstitutionId);
            var settings = await _settings.GetByInstitutionIdAsync(institutionId)
                ?? CreateDefaultSettings(institutionId);

            return Map(settings);
        }

        public async Task<InstitutionSettingsDto> UpdateSettingsAsync(string requesterId, UpdateInstitutionSettingsDto dto)
        {
            var requester = await _users.GetByIdAsync(requesterId)
                ?? throw new NotFoundException("User not found");

            var institutionId = ResolveInstitutionId(requester, dto.InstitutionId);
            var settings = await _settings.GetByInstitutionIdAsync(institutionId)
                ?? CreateDefaultSettings(institutionId);

            settings.InstitutionName = string.IsNullOrWhiteSpace(dto.InstitutionName) ? settings.InstitutionName : dto.InstitutionName.Trim();
            settings.Description = string.IsNullOrWhiteSpace(dto.Description) ? settings.Description : dto.Description.Trim();
            settings.ContactEmail = string.IsNullOrWhiteSpace(dto.ContactEmail) ? settings.ContactEmail : dto.ContactEmail.Trim();
            settings.TimeZone = string.IsNullOrWhiteSpace(dto.TimeZone) ? settings.TimeZone : dto.TimeZone.Trim();
            settings.DefaultLanguage = string.IsNullOrWhiteSpace(dto.DefaultLanguage) ? settings.DefaultLanguage : dto.DefaultLanguage.Trim();
            settings.BrandingPrimaryColor = string.IsNullOrWhiteSpace(dto.BrandingPrimaryColor) ? settings.BrandingPrimaryColor : dto.BrandingPrimaryColor.Trim();
            settings.UpdatedAt = DateTime.UtcNow;

            await _settings.UpsertAsync(settings);
            return Map(settings);
        }

        private static string ResolveInstitutionId(User requester, string? requestedInstitutionId)
        {
            if (ApplicationRoles.IsSystemAdmin(requester.Role))
            {
                if (string.IsNullOrWhiteSpace(requestedInstitutionId))
                    throw new ValidationException("InstitutionId is required");

                return requestedInstitutionId.Trim();
            }

            if (ApplicationRoles.IsInstitutionAdmin(requester.Role))
            {
                if (string.IsNullOrWhiteSpace(requester.InstitutionId))
                    throw new ValidationException("InstitutionAdmin is not assigned to an institution");

                if (!string.IsNullOrWhiteSpace(requestedInstitutionId) &&
                    !string.Equals(requestedInstitutionId, requester.InstitutionId, StringComparison.OrdinalIgnoreCase))
                {
                    throw new UnauthorizedActionException("You can only manage settings for your own institution");
                }

                return requester.InstitutionId;
            }

            throw new UnauthorizedActionException("You are not allowed to manage institution settings");
        }

        private static InstitutionSettings CreateDefaultSettings(string institutionId)
        {
            return new InstitutionSettings
            {
                InstitutionId = institutionId
            };
        }

        private static InstitutionSettingsDto Map(InstitutionSettings settings)
        {
            return new InstitutionSettingsDto
            {
                InstitutionId = settings.InstitutionId,
                InstitutionName = settings.InstitutionName,
                Description = settings.Description,
                ContactEmail = settings.ContactEmail,
                TimeZone = settings.TimeZone,
                DefaultLanguage = settings.DefaultLanguage,
                BrandingPrimaryColor = settings.BrandingPrimaryColor,
                UpdatedAt = settings.UpdatedAt
            };
        }
    }
}
