using eArchiveSystem.Application.DTOs;
using eArchiveSystem.Application.Exceptions;
using eArchiveSystem.Application.Interfaces.Persistence;
using eArchiveSystem.Application.Interfaces.Security;
using eArchiveSystem.Application.Interfaces.Services;
using eArchiveSystem.Application.Segmentation.Abstractions;
using eArchiveSystem.Domain.Models;
using System.Net.Http.Json;

namespace eArchiveSystem.Application.Services
{
    public class DocumentService : IDocumentService
    {
        private readonly IDocumentRepository _documents;
        private readonly IFileHashCalculator _hashCalculator;
        private readonly IStorageService _storage;
        private readonly IUserRepository _users;
        private readonly IMetadataRepository _metadata;
        private readonly IAuditService _audit;
        private readonly HttpClient _httpClient;
        private readonly IConfiguration _config;
        private readonly IIndexingService _indexing;
        private readonly IDocumentAuthorizationService _authorization;
        private readonly INotificationService _notifications;
        private readonly IDocumentWatermarkService _watermarkService;
        private readonly IPdfTextExtractor _pdfTextExtractor;
        private readonly ITextPreprocessorService _textPreprocessor;
        private readonly IDocumentSegmentationService _documentSegmentationService;
        private readonly ILogger<DocumentService> _logger;

        public DocumentService(
            IDocumentRepository documents,
            IFileHashCalculator hashCalculator,
            IStorageService storage,
            IUserRepository users,
            IMetadataRepository metadata,
            IAuditService audit,
            HttpClient httpClient,
            IConfiguration config,
            IIndexingService indexing,
            IDocumentAuthorizationService authorization,
            INotificationService notifications,
            IDocumentWatermarkService watermarkService,
            IPdfTextExtractor pdfTextExtractor,
            ITextPreprocessorService textPreprocessor,
            IDocumentSegmentationService documentSegmentationService,
            ILogger<DocumentService> logger)
        {
            _documents = documents;
            _hashCalculator = hashCalculator;
            _storage = storage;
            _users = users;
            _metadata = metadata;
            _audit = audit;
            _httpClient = httpClient;
            _config = config;
            _indexing = indexing;
            _authorization = authorization;
            _notifications = notifications;
            _watermarkService = watermarkService;
            _pdfTextExtractor = pdfTextExtractor;
            _textPreprocessor = textPreprocessor;
            _documentSegmentationService = documentSegmentationService;
            _logger = logger;
        }

        public async Task<DocumentAddResult> AddDocumentAsync(string actorUserId, AddDocumentDto dto)
        {
            var actor = await _users.GetByIdAsync(actorUserId)
                ?? throw new NotFoundException("User not found");

            if (dto.File == null)
                throw new ValidationException("File is required");

            var ownerId = string.IsNullOrWhiteSpace(dto.TargetUserId)
                ? actor.Id
                : dto.TargetUserId;

            var owner = await _users.GetByIdAsync(ownerId)
                ?? throw new NotFoundException("Target user not found");

            if (!_authorization.CanAddForOwner(actor, owner))
                throw new UnauthorizedActionException("You are not allowed to add documents for this user");

            var fileHash = await _hashCalculator.ComputeHashAsync(dto.File);
            var existing = await _documents.GetByHashAsync(fileHash);

            if (existing != null)
            {
                return new DocumentAddResult
                {
                    IsDuplicate = true,
                    Document = existing,
                    Message = "File already exists"
                };
            }

            var savedPath = await _storage.SaveFileAsync(dto.File, "uploads");

            var isPdf = IsPdf(dto.File.ContentType, dto.File.FileName);
            var shouldTriggerOcr = dto.EnableOcr && IsImage(dto.File.ContentType, dto.File.FileName);
            var shouldExtractPdfText = isPdf;

            var doc = new Document
            {
                Title = string.IsNullOrWhiteSpace(dto.Title)
                    ? dto.File.FileName
                    : dto.Title,
                FileName = dto.File.FileName,
                FilePath = savedPath,
                ContentType = dto.File.ContentType,
                Size = dto.File.Length,
                FileHash = fileHash,
                Content = null,
                UserId = owner.Id,
                InstitutionId = owner.InstitutionId,
                DepartmentId = owner.DepartmentId ?? owner.Department,
                Department = owner.Department ?? owner.DepartmentId,
                Priority = dto.Priority ?? DocumentPriority.Normal,
                IsSensitive = dto.IsSensitive,
                Status = shouldTriggerOcr || shouldExtractPdfText ? DocumentStatus.Processing : DocumentStatus.Draft,
                CreatedAt = DateTime.UtcNow,
                UpdatedAt = DateTime.UtcNow
            };

            await _documents.CreateAsync(doc);
            _logger.LogInformation("Document {DocumentId} was created and saved successfully", doc.Id);

            var fullSavedPath = Path.Combine(Directory.GetCurrentDirectory(), savedPath);
            if (!File.Exists(fullSavedPath))
                throw new NotFoundException("Document file not found");

            if (shouldExtractPdfText)
            {
                await ExtractPdfTextAsync(doc.Id, fullSavedPath);
            }
            else if (shouldTriggerOcr)
            {
                await TriggerOcrAsync(doc.Id, fullSavedPath);
            }
            else
            {
                await _indexing.SyncDocumentAsync(doc.Id);
            }

            await _audit.LogAsync(
                actor.Id,
                actor.Role,
                "AddDocument",
                doc.Id,
                $"User {actor.Id} uploaded document '{doc.Title}' for owner {owner.Id}");

            return new DocumentAddResult
            {
                IsDuplicate = false,
                Document = doc,
                Message = "Uploaded successfully"
            };
        }

        public async Task<Document> GetByIdAsync(string id)
        {
            var doc = await _documents.GetByIdAsync(id);
            if (doc == null)
                throw new NotFoundException("Document not found");

            var meta = await _metadata.GetByDocumentIdAsync(id);
            doc.Metadata = meta;

            return doc;
        }

        public async Task AttachMetadataAsync(string documentId)
        {
            var metadata = await _metadata.GetByDocumentIdAsync(documentId);
            if (metadata == null)
                return;

            await _documents.UpdateMetadataFieldsAsync(documentId, metadata);
        }

        public async Task<DocumentViewDto> ViewDocumentAsync(string id, string userId, string role)
        {
            var doc = await _documents.GetByIdAsync(id);
            if (doc == null)
                throw new NotFoundException("Document not found");

            var actor = await _users.GetByIdAsync(userId)
                ?? throw new NotFoundException("User not found");

            if (!_authorization.CanView(actor, doc))
                throw new UnauthorizedActionException("You are not allowed to view this document");

            var metadata = await _metadata.GetByDocumentIdAsync(id);
            doc.Metadata = metadata ?? doc.Metadata;

            var owner = await _users.GetByIdAsync(doc.UserId);
            doc.OwnerName = owner?.Name;

            await _audit.LogAsync(
                userId,
                role,
                "ViewDocument",
                id,
                $"User {userId} viewed document {id}");

            return new DocumentViewDto
            {
                Id = doc.Id,
                Title = doc.Title,
                InstitutionId = doc.InstitutionId,
                DepartmentId = doc.DepartmentId,
                Department = doc.Department,
                Priority = doc.Priority,
                IsSensitive = doc.IsSensitive,
                Status = doc.Status,
                OwnerName = owner?.Name,
                CreatedAt = doc.CreatedAt,
                Metadata = doc.Metadata,
                OwnerEmail = owner?.Email
            };
        }

        public async Task<DocumentOcrTextDto> GetExtractedTextAsync(string documentId, string userId, string role)
        {
            var doc = await _documents.GetByIdAsync(documentId);
            if (doc == null)
                throw new NotFoundException("Document not found");

            var actor = await _users.GetByIdAsync(userId)
                ?? throw new NotFoundException("User not found");

            if (!_authorization.CanView(actor, doc))
                throw new UnauthorizedActionException("You are not allowed to view this document");

            await _audit.LogAsync(
                userId,
                role,
                "ViewDocumentOcrText",
                documentId,
                $"User {userId} viewed OCR text for document {documentId}");

            return new DocumentOcrTextDto
            {
                DocumentId = doc.Id,
                Title = doc.Title,
                Status = doc.Status,
                RawText = doc.RawOcrText ?? string.Empty,
                NormalizedText = doc.NormalizedOcrText ?? doc.Content ?? string.Empty,
                Provider = doc.OcrProvider,
                Language = doc.OcrLanguage,
                Pages = doc.OcrPages,
                ExtractedAt = doc.OcrUpdatedAt
            };
        }

        public async Task<(Stream FileStream, string FileName, string ContentType)> DownloadDocumentAsync(
            string id,
            string userId,
            string role)
        {
            var doc = await _documents.GetByIdAsync(id);
            if (doc == null)
                throw new NotFoundException("Document not found");

            var actor = await _users.GetByIdAsync(userId)
                ?? throw new NotFoundException("User not found");

            if (!_authorization.CanView(actor, doc))
                throw new UnauthorizedActionException("You are not allowed to download this document");

            var fullPath = Path.Combine(Directory.GetCurrentDirectory(), doc.FilePath);

            if (!File.Exists(fullPath))
                throw new NotFoundException("Document file not found");

            await _audit.LogAsync(
                userId,
                role,
                "DownloadDocument",
                id,
                $"User {userId} downloaded document {id}");

            return await _watermarkService.PrepareDownloadAsync(doc, actor, fullPath);
        }

        public async Task<DocumentUpdateResult> UpdateDocumentAsync(
            string documentId,
            UpdateDocumentDto dto,
            string userId,
            string role)
        {
            var doc = await _documents.GetByIdAsync(documentId);
            if (doc == null)
                throw new NotFoundException("Document not found");

            var actor = await _users.GetByIdAsync(userId)
                ?? throw new NotFoundException("User not found");

            if (!_authorization.CanEdit(actor, doc))
                throw new UnauthorizedActionException("You are not allowed to update this document");

            if (!string.IsNullOrWhiteSpace(dto.Title))
                doc.Title = dto.Title;

            if (dto.Priority.HasValue)
                doc.Priority = dto.Priority.Value;

            if (dto.IsSensitive.HasValue)
                doc.IsSensitive = dto.IsSensitive.Value;

            var fileWasReplaced = false;

            if (dto.File != null)
            {
                var newHash = await _hashCalculator.ComputeHashAsync(dto.File);
                var existing = await _documents.GetByHashAsync(newHash);

                if (existing != null && existing.Id != documentId)
                    throw new ConflictException("Duplicate file detected");

                var oldPath = Path.Combine(Directory.GetCurrentDirectory(), doc.FilePath);
                if (File.Exists(oldPath))
                    File.Delete(oldPath);

                var newPath = await _storage.SaveFileAsync(dto.File, "uploads");

                doc.FileName = dto.File.FileName;
                doc.ContentType = dto.File.ContentType;
                doc.Size = dto.File.Length;
                doc.FileHash = newHash;
                doc.FilePath = newPath;
                doc.Content = null;
                doc.RawOcrText = null;
                doc.NormalizedOcrText = null;
                doc.OcrProvider = null;
                doc.OcrLanguage = null;
                doc.OcrPages = null;
                doc.OcrUpdatedAt = null;
                doc.Metadata = null;
                doc.Status = IsPdf(dto.File.ContentType, dto.File.FileName) ||
                             IsImage(dto.File.ContentType, dto.File.FileName)
                    ? DocumentStatus.Processing
                    : DocumentStatus.Draft;
                fileWasReplaced = true;
            }

            doc.UpdatedAt = DateTime.UtcNow;
            await _documents.UpdateAsync(documentId, doc);
            _logger.LogInformation("Document {DocumentId} was updated successfully", documentId);

            if (fileWasReplaced)
            {
                await _indexing.RemoveDocumentAsync(documentId);
                var replacementPath = Path.Combine(Directory.GetCurrentDirectory(), doc.FilePath);
                if (IsPdf(doc.ContentType, doc.FileName))
                    await ExtractPdfTextAsync(doc.Id, replacementPath);
                else if (IsImage(doc.ContentType, doc.FileName))
                    await TriggerOcrAsync(doc.Id, replacementPath);
                else
                    await _indexing.SyncDocumentAsync(documentId);
            }
            else
            {
                await _documents.AttachMetadataAsync(documentId);
                await _indexing.SyncDocumentAsync(documentId);
            }

            await _audit.LogAsync(
                userId,
                role,
                "UpdateDocument",
                documentId,
                $"User {userId} updated document {documentId}");

            await _notifications.NotifyDocumentUpdatedAsync(doc, actor);

            return new DocumentUpdateResult
            {
                Success = true,
                Document = doc,
                Message = "Updated successfully"
            };
        }

        public async Task DeleteDocumentAsync(string id, string userId, string role)
        {
            var doc = await _documents.GetByIdAsync(id);
            if (doc == null)
                throw new NotFoundException("Document not found");

            var actor = await _users.GetByIdAsync(userId)
                ?? throw new NotFoundException("User not found");

            if (!_authorization.CanDelete(actor, doc))
                throw new UnauthorizedActionException("You are not allowed to delete this document");

            var fullPath = Path.Combine(Directory.GetCurrentDirectory(), doc.FilePath);
            if (File.Exists(fullPath))
                File.Delete(fullPath);

            await _metadata.DeleteByDocumentIdAsync(doc.Id);

            var deleted = await _documents.DeleteAsync(doc.Id);
            if (!deleted)
                throw new NotFoundException("Document not found");

            try
            {
                await _indexing.RemoveDocumentAsync(doc.Id);
            }
            catch (Exception exception)
            {
                _logger.LogWarning(
                    exception,
                    "Document {DocumentId} was deleted, but search index cleanup failed.",
                    doc.Id);
            }

            try
            {
                await _audit.LogAsync(
                    userId,
                    role,
                    "DeleteDocument",
                    doc.Id,
                    $"User {userId} deleted document '{doc.Title}'");
            }
            catch (Exception exception)
            {
                _logger.LogWarning(
                    exception,
                    "Document {DocumentId} was deleted, but audit logging failed.",
                    doc.Id);
            }
        }

        private async Task TriggerOcrAsync(string documentId, string filePath)
        {
            try
            {
                var response = await _httpClient.PostAsJsonAsync(
                    $"{_config["OcrService:BaseUrl"]}/api/ocr/process",
                    new
                    {
                        documentId,
                        filePath,
                        callbackUrl = $"{_config["App:BaseUrl"]}/api/ocr/callback?documentId={documentId}"
                    });

                if (response.IsSuccessStatusCode)
                    return;

                var responseBody = await response.Content.ReadAsStringAsync();
                _logger.LogError(
                    "OCR request failed for document {DocumentId}. Status: {StatusCode}. Response: {ResponseBody}",
                    documentId,
                    response.StatusCode,
                    responseBody);

                _logger.LogWarning(
                    "OCR request failed for document {DocumentId}. The document remains saved and can be retried later.",
                    documentId);
                return;
            }
            catch (ApiException)
            {
                throw;
            }
            catch (Exception exception)
            {
                _logger.LogError(
                    exception,
                    "OCR request threw an exception for document {DocumentId}",
                    documentId);
                _logger.LogWarning(
                    "OCR service is unavailable for document {DocumentId}. The document remains saved and can be retried later.",
                    documentId);
            }
        }

        private async Task ExtractPdfTextAsync(string documentId, string filePath)
        {
            string? extractedText;

            try
            {
                extractedText = await _pdfTextExtractor.ExtractTextAsync(filePath);
            }
            catch (Exception exception)
            {
                await _documents.UpdateStatusAsync(documentId, DocumentStatus.Draft);
                _logger.LogError(exception, "PDF text extraction failed for document {DocumentId}", documentId);
                return;
            }

            // An empty text layer is expected for scanned PDFs; let the OCR service render and process it.
            if (string.IsNullOrWhiteSpace(extractedText))
            {
                await TriggerOcrAsync(documentId, filePath);
                return;
            }

            try
            {
                var cleanedText = _textPreprocessor.Clean(extractedText);
                await _documents.UpdateExtractedContentAsync(
                    documentId,
                    cleanedText,
                    extractedText,
                    extractedText);
                await _indexing.SyncDocumentAsync(documentId);
                await TryProcessAutomaticSegmentationAsync(documentId);
            }
            catch (Exception exception)
            {
                await _documents.UpdateStatusAsync(documentId, DocumentStatus.Draft);
                _logger.LogError(exception, "PDF text extraction failed for document {DocumentId}", documentId);
            }
        }

        private async Task TryProcessAutomaticSegmentationAsync(string documentId)
        {
            try
            {
                await _documentSegmentationService.ProcessStoredDocumentAsync(documentId);
            }
            catch (AraSegClientException exception)
            {
                _logger.LogWarning(
                    "Automatic segmentation failed for document {DocumentId} with error code {ErrorCode}",
                    documentId,
                    exception.ErrorCode ?? "ARASEG_ERROR");
            }
            catch (ApiException exception)
            {
                _logger.LogWarning(
                    "Automatic segmentation failed for document {DocumentId}: {Message}",
                    documentId,
                    exception.Message);
            }
            catch (Exception)
            {
                _logger.LogError(
                    "Automatic segmentation failed unexpectedly for document {DocumentId}",
                    documentId);
            }
        }

        private static bool IsPdf(string? contentType, string fileName) =>
            string.Equals(contentType, "application/pdf", StringComparison.OrdinalIgnoreCase) ||
            Path.GetExtension(fileName).Equals(".pdf", StringComparison.OrdinalIgnoreCase);

        private static bool IsImage(string? contentType, string fileName)
        {
            if (contentType?.StartsWith("image/", StringComparison.OrdinalIgnoreCase) == true)
                return true;

            return Path.GetExtension(fileName).ToLowerInvariant() is ".png" or ".jpg" or ".jpeg" or ".bmp" or ".tif" or ".tiff" or ".webp";
        }
    }
}
