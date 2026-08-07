using eArchiveSystem.Application.DTOs;
using eArchiveSystem.Application.Interfaces.Services;
using eArchiveSystem.Domain.Models;

namespace eArchiveSystem.Application.Services
{
    public class OcrExtractionAssessmentService : IOcrExtractionAssessmentService
    {
        public OcrExtractionAssessmentDto Assess(Metadata metadata, bool structuredDataProvided)
        {
            var missingCoreFields = new List<string>();
            var missingAdvancedFields = new List<string>();

            if (string.IsNullOrWhiteSpace(metadata.Description))
                missingCoreFields.Add("summary");

            if (metadata.Tags == null || metadata.Tags.Count == 0)
                missingCoreFields.Add("keywords");

            if (string.IsNullOrWhiteSpace(metadata.BroadGenre))
                missingCoreFields.Add("broadGenre");

            if (string.IsNullOrWhiteSpace(metadata.SpecificGenre))
                missingCoreFields.Add("specificGenre");

            if (string.IsNullOrWhiteSpace(metadata.DocumentType))
                missingCoreFields.Add("documentType");

            if (string.IsNullOrWhiteSpace(metadata.IssuingEntity))
                missingAdvancedFields.Add("issuingEntity");

            if (string.IsNullOrWhiteSpace(metadata.ReferenceNumber))
                missingAdvancedFields.Add("referenceNumber");

            if (!metadata.DocumentDate.HasValue)
                missingAdvancedFields.Add("documentDate");

            var layoutAvailable =
                metadata.Headers != null &&
                metadata.Footers != null &&
                metadata.Stamps != null;

            var assessment = new OcrExtractionAssessmentDto
            {
                StructuredDataProvided = structuredDataProvided,
                CoreFieldsComplete = missingCoreFields.Count == 0,
                AdvancedMetadataComplete = missingAdvancedFields.Count == 0,
                LayoutAnalysisAvailable = layoutAvailable,
                MissingFields = missingCoreFields
                    .Concat(missingAdvancedFields)
                    .Distinct(StringComparer.OrdinalIgnoreCase)
                    .ToList()
            };

            assessment.RequiresReview =
                !assessment.CoreFieldsComplete ||
                !assessment.AdvancedMetadataComplete ||
                !assessment.LayoutAnalysisAvailable;

            assessment.ExtractionStatus = assessment switch
            {
                { CoreFieldsComplete: true, AdvancedMetadataComplete: true, LayoutAnalysisAvailable: true } => "Complete",
                { CoreFieldsComplete: true } => "Partial",
                _ => "NeedsReview"
            };

            return assessment;
        }
    }
}
