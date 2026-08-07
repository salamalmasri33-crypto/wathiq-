using eArchiveSystem.Application.DTOs;
using eArchiveSystem.Domain.Models;

namespace eArchiveSystem.Application.Interfaces.Services
{
    public interface IOcrExtractionAssessmentService
    {
        OcrExtractionAssessmentDto Assess(Metadata metadata, bool structuredDataProvided);
    }
}
