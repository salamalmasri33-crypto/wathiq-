using System.Text.Json;
using eArchiveSystem.Application.DTOs;
using eArchiveSystem.Application.Exceptions;
using eArchiveSystem.Application.Interfaces.Persistence;
using eArchiveSystem.Application.Interfaces.Services;
using eArchiveSystem.Domain.Models;

namespace eArchiveSystem.Application.Services
{
    public class MetadataPreviewService : IMetadataPreviewService
    {
        private readonly IDocumentRepository _documents;
        private readonly IMetadataRepository _metadata;
        private readonly IUserRepository _users;
        private readonly IDocumentAuthorizationService _authorization;
        private readonly IRuleBasedAnalyzer _analyzer;
        private readonly ITextPreprocessorService _preprocessor;
        private readonly IOcrExtractionAssessmentService _assessmentService;
        private readonly IInstitutionClassificationService _classificationService;
        private readonly ILogger<MetadataPreviewService> _logger;

        public MetadataPreviewService(
            IDocumentRepository documents,
            IMetadataRepository metadata,
            IUserRepository users,
            IDocumentAuthorizationService authorization,
            IRuleBasedAnalyzer analyzer,
            ITextPreprocessorService preprocessor,
            IOcrExtractionAssessmentService assessmentService,
            IInstitutionClassificationService classificationService,
            ILogger<MetadataPreviewService> logger)
        {
            _documents = documents;
            _metadata = metadata;
            _users = users;
            _authorization = authorization;
            _analyzer = analyzer;
            _preprocessor = preprocessor;
            _assessmentService = assessmentService;
            _classificationService = classificationService;
            _logger = logger;
        }

        public async Task<MetadataPreviewDto> GeneratePreviewAsync(string documentId, string userId, string role, CancellationToken cancellationToken = default)
        {
            var document = await _documents.GetByIdAsync(documentId)
                ?? throw new NotFoundException("Document not found");

            var actor = await _users.GetByIdAsync(userId)
                ?? throw new NotFoundException("User not found");

            if (!_authorization.CanView(actor, document))
                throw new UnauthorizedActionException("You are not allowed to preview metadata for this document");

            var savedMetadata = await _metadata.GetByDocumentIdAsync(documentId);

            var normalizedText = string.IsNullOrWhiteSpace(document.NormalizedOcrText)
                ? document.Content
                : document.NormalizedOcrText;

            var rawText = string.IsNullOrWhiteSpace(document.RawOcrText)
                ? normalizedText
                : document.RawOcrText;

            var preview = new MetadataPreviewDto
            {
                DocumentId = document.Id,
                Title = document.Title,
                Status = document.Status,
                HasSavedMetadata = savedMetadata != null,
                HasExtractedText = !string.IsNullOrWhiteSpace(rawText) || !string.IsNullOrWhiteSpace(normalizedText),
                Department = document.Department,
                DepartmentId = document.DepartmentId ?? document.Department,
                BroadGenre = savedMetadata?.BroadGenre,
                SpecificGenre = savedMetadata?.SpecificGenre
            };

            if (!string.IsNullOrWhiteSpace(savedMetadata?.BroadGenre) &&
                !string.IsNullOrWhiteSpace(savedMetadata.SpecificGenre))
                preview.GenreClassificationStatus = "SavedMetadata";

            if (!preview.HasExtractedText)
            {
                if (preview.GenreClassificationStatus != "SavedMetadata")
                    preview.GenreClassificationStatus = "NoText";
                return preview;
            }

            var cleaned = _preprocessor.Clean(normalizedText ?? string.Empty);

            var generatedMetadata = new Metadata
            {
                Id = documentId,
                Description = _analyzer.ExtractDescription(cleaned),
                DocumentType = _analyzer.DetectDocumentType(cleaned, document.FileName),
                Tags = _analyzer.ExtractKeywords(cleaned),
                IssuingEntity = _analyzer.DetectIssuingEntity(cleaned),
                ReferenceNumber = _analyzer.ExtractReferenceNumber(cleaned),
                DocumentDate = _analyzer.ExtractDocumentDate(cleaned),
                Insights = _analyzer.ExtractInsights(cleaned),
                Signatures = _analyzer.DetectSignatures(rawText ?? string.Empty),
                Headers = _analyzer.ExtractHeaders(rawText ?? string.Empty),
                Footers = _analyzer.ExtractFooters(rawText ?? string.Empty),
                Stamps = _analyzer.DetectStamps(rawText ?? string.Empty),
                Department = document.Department,
                DepartmentId = document.DepartmentId ?? document.Department,
                CreatedAt = DateTime.UtcNow,
                UpdatedAt = DateTime.UtcNow
            };

            if (preview.GenreClassificationStatus == "SavedMetadata")
            {
                generatedMetadata.BroadGenre = savedMetadata!.BroadGenre;
                generatedMetadata.SpecificGenre = savedMetadata.SpecificGenre;
            }
            else if (string.IsNullOrWhiteSpace(cleaned))
            {
                preview.GenreClassificationStatus = "NoText";
            }
            else
            {
                var institutionId = document.InstitutionId;
                if (string.IsNullOrWhiteSpace(institutionId))
                    institutionId = (await _users.GetByIdAsync(document.UserId))?.InstitutionId;

                if (string.IsNullOrWhiteSpace(institutionId))
                {
                    preview.GenreClassificationStatus = "NotConfigured";
                    preview.GenreClassificationMessage = "The document is not assigned to an institution.";
                }
                else
                {
                    try
                    {
                        var classification = await _classificationService.ClassifyForDocumentAsync(
                            institutionId, document.Id, cleaned, cancellationToken);
                        generatedMetadata.BroadGenre = classification.BroadGenre;
                        generatedMetadata.SpecificGenre = classification.SpecificGenre;
                        preview.GenreClassificationStatus = "Succeeded";
                    }
                    catch (NotFoundException)
                    {
                        preview.GenreClassificationStatus = "NotConfigured";
                        preview.GenreClassificationMessage = "Classification is not configured for this institution.";
                    }
                    catch (ConflictException)
                    {
                        preview.GenreClassificationStatus = "IndexNotReady";
                        preview.GenreClassificationMessage = "The institution classifier must be rebuilt.";
                    }
                    catch (ExternalServiceException exception)
                    {
                        preview.GenreClassificationStatus = "Unavailable";
                        preview.GenreClassificationMessage = "The classification service is temporarily unavailable.";
                        _logger.LogWarning(exception, "AraGenre unavailable while previewing document {DocumentId} for institution {InstitutionId}", document.Id, institutionId);
                    }
                    catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
                    {
                        throw;
                    }
                    catch (Exception exception)
                    {
                        preview.GenreClassificationStatus = "Failed";
                        preview.GenreClassificationMessage = "Document classification could not be completed.";
                        _logger.LogError(exception, "Unexpected AraGenre failure while previewing document {DocumentId} for institution {InstitutionId}", document.Id, institutionId);
                    }
                }
            }

            generatedMetadata.HasSignature = generatedMetadata.Signatures?.Count > 0;

            var assessment = _assessmentService.Assess(generatedMetadata, structuredDataProvided: false);

            generatedMetadata.StructuredDataProvided = assessment.StructuredDataProvided;
            generatedMetadata.CoreFieldsComplete = assessment.CoreFieldsComplete;
            generatedMetadata.AdvancedMetadataComplete = assessment.AdvancedMetadataComplete;
            generatedMetadata.LayoutAnalysisAvailable = assessment.LayoutAnalysisAvailable;
            generatedMetadata.RequiresReview = assessment.RequiresReview;
            generatedMetadata.ExtractionStatus = assessment.ExtractionStatus;
            generatedMetadata.MissingFields = assessment.MissingFields;

            preview.Description = generatedMetadata.Description;
            preview.BroadGenre = generatedMetadata.BroadGenre;
            preview.SpecificGenre = generatedMetadata.SpecificGenre;
            preview.Tags = generatedMetadata.Tags;
            preview.Department = generatedMetadata.Department;
            preview.DepartmentId = generatedMetadata.DepartmentId;
            preview.DocumentType = generatedMetadata.DocumentType;
            preview.ExpirationDate = generatedMetadata.ExpirationDate;
            preview.IssuingEntity = generatedMetadata.IssuingEntity;
            preview.ReferenceNumber = generatedMetadata.ReferenceNumber;
            preview.DocumentDate = generatedMetadata.DocumentDate;
            preview.Insights = generatedMetadata.Insights;
            preview.HasSignature = generatedMetadata.HasSignature;
            preview.Signatures = generatedMetadata.Signatures;
            preview.Headers = generatedMetadata.Headers;
            preview.Footers = generatedMetadata.Footers;
            preview.Stamps = generatedMetadata.Stamps;
            preview.RawExtractionJson = JsonSerializer.Serialize(new
            {
                metadataSource = "RuleBasedAnalyzer",
                classificationSource = "AraGenre",
                classificationStatus = preview.GenreClassificationStatus,
                provider = document.OcrProvider,
                language = document.OcrLanguage,
                pages = document.OcrPages
            });
            preview.StructuredDataProvided = generatedMetadata.StructuredDataProvided;
            preview.CoreFieldsComplete = generatedMetadata.CoreFieldsComplete;
            preview.AdvancedMetadataComplete = generatedMetadata.AdvancedMetadataComplete;
            preview.LayoutAnalysisAvailable = generatedMetadata.LayoutAnalysisAvailable;
            preview.RequiresReview = generatedMetadata.RequiresReview;
            preview.ExtractionStatus = generatedMetadata.ExtractionStatus ?? "NeedsReview";
            preview.MissingFields = generatedMetadata.MissingFields ?? new List<string>();

            return preview;
        }
    }
}
