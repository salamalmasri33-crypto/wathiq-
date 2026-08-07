using eArchiveSystem.Application.DTOs;
using eArchiveSystem.Application.Interfaces.Persistence;
using eArchiveSystem.Application.Interfaces.Services;
using System.Text.RegularExpressions;

namespace eArchiveSystem.Application.Services
{
    public class IndexingService : IIndexingService
    {
        private readonly IDocumentRepository _documents;
        private readonly IMetadataRepository _metadata;
        private readonly IUserRepository _users;
        private readonly IDocumentSegmentationRepository _segmentations;
        private readonly IDocumentSearchRepository _searchRepository;
        private readonly ILogger<IndexingService> _logger;

        public IndexingService(
            IDocumentRepository documents,
            IMetadataRepository metadata,
            IUserRepository users,
            IDocumentSegmentationRepository segmentations,
            IDocumentSearchRepository searchRepository,
            ILogger<IndexingService> logger)
        {
            _documents = documents;
            _metadata = metadata;
            _users = users;
            _segmentations = segmentations;
            _searchRepository = searchRepository;
            _logger = logger;
        }

        public async Task SyncDocumentAsync(string documentId)
        {
            var document = await _documents.GetByIdAsync(documentId);
            if (document == null)
                return;

            var indexedDocument = await BuildSearchDocumentAsync(document);
            try
            {
                await _searchRepository.IndexAsync(indexedDocument);
            }
            catch (Exception exception) when (IsSearchBackendUnavailable(exception))
            {
                _logger.LogWarning(
                    exception,
                    "Elasticsearch is unavailable. Document {DocumentId} was saved but not indexed.",
                    documentId);
            }
        }

        public async Task RemoveDocumentAsync(string documentId)
        {
            try
            {
                await _searchRepository.DeleteAsync(documentId);
            }
            catch (Exception exception) when (IsSearchBackendUnavailable(exception))
            {
                _logger.LogWarning(
                    exception,
                    "Elasticsearch is unavailable. Document {DocumentId} was deleted from MongoDB but not from the search index.",
                    documentId);
            }
        }

        public Task EnsureIndexReadyAsync()
        {
            return _searchRepository.EnsureIndexExistsAsync();
        }

        public async Task ReindexAllAsync(bool recreateIndex = false)
        {
            if (recreateIndex)
                await _searchRepository.RecreateIndexAsync();
            else
                await _searchRepository.EnsureIndexExistsAsync();

            var documents = await _documents.GetAllAsync();

            foreach (var document in documents)
            {
                var indexedDocument = await BuildSearchDocumentAsync(document);
                await _searchRepository.IndexAsync(indexedDocument);
            }
        }

        public async Task<(List<SearchDocumentIndex>, long)> SearchAsync(SearchDocumentsDto dto, SearchAccessScope scope)
        {
            IReadOnlyList<SearchDocumentHit> hits;
            long total;

            try
            {
                (hits, total) = await _searchRepository.SearchAsync(dto, scope);
            }
            catch (HttpRequestException exception)
            {
                _logger.LogWarning(
                    exception,
                    "Elasticsearch is unavailable. Falling back to MongoDB document search.");

                return await SearchFromMongoAsync(dto, scope);
            }
            catch (TaskCanceledException exception)
            {
                _logger.LogWarning(
                    exception,
                    "Elasticsearch search timed out. Falling back to MongoDB document search.");

                return await SearchFromMongoAsync(dto, scope);
            }

            var ids = hits.Select(hit => hit.Id).ToList();

            if (ids == null || ids.Count == 0)
                return await SearchFromMongoAsync(dto, scope);

            var documents = await _documents.GetByIdsAsync(ids);
            var lookup = documents.ToDictionary(d => d.Id);
            var hitLookup = hits.ToDictionary(hit => hit.Id);
            var results = new List<SearchDocumentIndex>();

            foreach (var id in ids)
            {
                if (!lookup.TryGetValue(id, out var document))
                    continue;

                var indexedDocument = await BuildSearchDocumentAsync(document);
                indexedDocument.Snippet = hitLookup.TryGetValue(id, out var hit)
                    ? hit.Snippet ?? BuildFallbackSnippet(indexedDocument, dto.Query)
                    : BuildFallbackSnippet(indexedDocument, dto.Query);

                results.Add(indexedDocument);
            }

            if (results.Count == 0)
                return await SearchFromMongoAsync(dto, scope);

            if (!string.IsNullOrWhiteSpace(dto.Query))
            {
                var mongoResult = await SearchFromMongoAsync(dto, scope);
                var resultIds = results.Select(document => document.Id).ToHashSet(StringComparer.OrdinalIgnoreCase);
                var mongoHasCurrentMatchesMissingFromIndex = mongoResult.Item1.Any(document => !resultIds.Contains(document.Id));

                if (mongoHasCurrentMatchesMissingFromIndex || mongoResult.Item2 != total)
                    return mongoResult;
            }

            return (results, total);
        }

        private static bool IsSearchBackendUnavailable(Exception exception)
        {
            return exception is HttpRequestException ||
                   exception is TaskCanceledException ||
                   exception.InnerException is HttpRequestException ||
                   exception.InnerException is TaskCanceledException;
        }

        private async Task<(List<SearchDocumentIndex>, long)> SearchFromMongoAsync(SearchDocumentsDto dto, SearchAccessScope scope)
        {
            var documents = await _documents.GetAllAsync();
            var indexedDocuments = new List<SearchDocumentIndex>();

            foreach (var document in documents)
            {
                indexedDocuments.Add(await BuildSearchDocumentAsync(document));
            }

            var filtered = indexedDocuments
                .Where(document => MatchesScope(document, scope))
                .Where(document => MatchesFilters(document, dto))
                .ToList();

            var total = filtered.Count;
            var ordered = ApplySort(filtered, dto);
            var page = dto.Page <= 0 ? 1 : dto.Page;
            var pageSize = dto.PageSize <= 0 ? 10 : Math.Min(dto.PageSize, 50);
            var results = ordered
                .Skip(Math.Max(0, (page - 1) * pageSize))
                .Take(pageSize)
                .Select(document =>
                {
                    document.Snippet = BuildFallbackSnippet(document, dto.Query);
                    return document;
                })
                .ToList();

            return (results, total);
        }

        private static bool MatchesScope(SearchDocumentIndex document, SearchAccessScope scope)
        {
            if (!string.IsNullOrWhiteSpace(scope.OwnerUserId) &&
                !string.Equals(document.UserId, scope.OwnerUserId, StringComparison.OrdinalIgnoreCase))
            {
                return false;
            }

            if (!string.IsNullOrWhiteSpace(scope.InstitutionId) &&
                !string.Equals(document.InstitutionId, scope.InstitutionId, StringComparison.OrdinalIgnoreCase))
            {
                return false;
            }

            if (!string.IsNullOrWhiteSpace(scope.DepartmentId) &&
                !string.Equals(document.DepartmentId, scope.DepartmentId, StringComparison.OrdinalIgnoreCase))
            {
                return false;
            }

            return true;
        }

        private static bool MatchesFilters(SearchDocumentIndex document, SearchDocumentsDto dto)
        {
            if (!string.IsNullOrWhiteSpace(dto.InstitutionId) &&
                !string.Equals(document.InstitutionId, dto.InstitutionId, StringComparison.OrdinalIgnoreCase))
            {
                return false;
            }

            if (!string.IsNullOrWhiteSpace(dto.Query) && !ContainsQuery(document, dto.Query))
                return false;

            if (!string.IsNullOrWhiteSpace(dto.BroadGenre) &&
                !string.Equals(document.BroadGenre, dto.BroadGenre, StringComparison.OrdinalIgnoreCase))
            {
                return false;
            }

            if (!string.IsNullOrWhiteSpace(dto.SpecificGenre) &&
                !string.Equals(document.SpecificGenre, dto.SpecificGenre, StringComparison.OrdinalIgnoreCase))
                return false;

            var departmentFilter = string.IsNullOrWhiteSpace(dto.DepartmentId) ? dto.Department : dto.DepartmentId;
            if (!string.IsNullOrWhiteSpace(departmentFilter) &&
                !string.Equals(document.DepartmentId, departmentFilter, StringComparison.OrdinalIgnoreCase))
            {
                return false;
            }

            if (dto.FromDate.HasValue && document.CreatedAt < dto.FromDate.Value)
                return false;

            if (dto.ToDate.HasValue && document.CreatedAt > dto.ToDate.Value)
                return false;

            if (dto.Status.HasValue && document.Status != dto.Status.Value)
                return false;

            if (dto.Priority.HasValue && document.Priority != dto.Priority.Value)
                return false;

            return true;
        }

        private static bool ContainsQuery(SearchDocumentIndex document, string query)
        {
            var searchableValues = new[]
            {
                document.Title,
                document.Content,
                document.Description,
                document.BroadGenre,
                document.SpecificGenre,
                document.DocumentType,
                document.IssuingEntity,
                document.ReferenceNumber,
                document.Department
            };

            var normalizedQuery = NormalizeSearchText(query);
            if (string.IsNullOrWhiteSpace(normalizedQuery))
            {
                return searchableValues.Any(value =>
                           !string.IsNullOrWhiteSpace(value) &&
                           value.Contains(query, StringComparison.OrdinalIgnoreCase)) ||
                       document.Tags.Any(tag => tag.Contains(query, StringComparison.OrdinalIgnoreCase));
            }

            if (searchableValues.Any(value => TextContains(value, query, normalizedQuery)) ||
                document.SentenceTexts.Any(sentence => TextContains(sentence, query, normalizedQuery)))
            {
                return true;
            }

            return document.Tags.Any(tag => TextContains(tag, query, normalizedQuery));
        }

        private static IEnumerable<SearchDocumentIndex> ApplySort(List<SearchDocumentIndex> documents, SearchDocumentsDto dto)
        {
            return dto.SortBy switch
            {
                "Title" => dto.Desc
                    ? documents.OrderByDescending(document => document.Title)
                    : documents.OrderBy(document => document.Title),
                "Priority" => dto.Desc
                    ? documents.OrderByDescending(document => document.Priority)
                    : documents.OrderBy(document => document.Priority),
                _ => dto.Desc
                    ? documents.OrderByDescending(document => document.CreatedAt)
                    : documents.OrderBy(document => document.CreatedAt)
            };
        }

        private async Task<SearchDocumentIndex> BuildSearchDocumentAsync(Domain.Models.Document document)
        {
            var metadata = document.Metadata ?? await _metadata.GetByDocumentIdAsync(document.Id);
            var owner = await _users.GetByIdAsync(document.UserId);
            var segmentation = await _segmentations.GetByDocumentIdAsync(document.Id);

            return new SearchDocumentIndex
            {
                Id = document.Id,
                Title = document.Title,
                Content = BuildSearchableContent(document, metadata),
                SentenceTexts = segmentation?.Status == Domain.Models.SegmentationStatus.Completed
                    ? segmentation.Sentences?.Select(sentence => sentence.Text).ToList() ?? new List<string>()
                    : new List<string>(),
                Description = metadata?.Description,
                InstitutionId = document.InstitutionId ?? owner?.InstitutionId ?? string.Empty,
                DepartmentId = document.DepartmentId ?? metadata?.DepartmentId ?? document.Department ?? owner?.DepartmentId ?? owner?.Department ?? string.Empty,
                Department = document.Department,
                UserId = document.UserId,
                IsSensitive = document.IsSensitive,
                BroadGenre = metadata?.BroadGenre,
                SpecificGenre = metadata?.SpecificGenre,
                DocumentType = metadata?.DocumentType,
                IssuingEntity = metadata?.IssuingEntity,
                ReferenceNumber = metadata?.ReferenceNumber,
                Status = document.Status,
                Priority = document.Priority,
                Tags = metadata?.Tags ?? new List<string>(),
                CreatedAt = document.CreatedAt,
                UpdatedAt = document.UpdatedAt
            };
        }

        private static string BuildSearchableContent(Domain.Models.Document document, Domain.Models.Metadata? metadata)
        {
            var values = new List<string?>
            {
                document.Content,
                document.NormalizedOcrText,
                document.RawOcrText,
                metadata?.Description,
                metadata?.BroadGenre,
                metadata?.SpecificGenre,
                metadata?.RawExtractionJson
            };

            if (metadata?.Insights != null)
                values.AddRange(metadata.Insights);

            if (metadata?.Tags != null)
                values.AddRange(metadata.Tags);

            var content = string.Join(
                " ",
                values.Where(value => !string.IsNullOrWhiteSpace(value))
                    .Select(value => value!.Trim()));

            return string.IsNullOrWhiteSpace(content)
                ? document.Title
                : content;
        }

        private static bool TextContains(string? value, string query, string normalizedQuery)
        {
            if (string.IsNullOrWhiteSpace(value))
                return false;

            if (value.Contains(query, StringComparison.OrdinalIgnoreCase))
                return true;

            return NormalizeSearchText(value).Contains(normalizedQuery, StringComparison.OrdinalIgnoreCase);
        }

        private static string NormalizeSearchText(string value)
        {
            if (string.IsNullOrWhiteSpace(value))
                return string.Empty;

            var normalized = Regex.Replace(value, "[\u064B-\u065F\u0670]", string.Empty)
                .Replace("\u0623", "\u0627")
                .Replace("\u0625", "\u0627")
                .Replace("\u0622", "\u0627")
                .Replace("\u0649", "\u064A")
                .Replace("\u0624", "\u0648")
                .Replace("\u0626", "\u064A")
                .Replace("\u0629", "\u0647")
                .ToLowerInvariant();

            normalized = Regex.Replace(normalized, @"[^\p{L}\p{N}\s]", " ");
            return Regex.Replace(normalized, @"\s+", " ").Trim();
        }

        private static string? BuildFallbackSnippet(SearchDocumentIndex document, string? query)
        {
            if (string.IsNullOrWhiteSpace(query))
                return null;

            var normalizedQuery = NormalizeSearchText(query);
            var matchingSentence = document.SentenceTexts.FirstOrDefault(
                sentence => TextContains(sentence, query, normalizedQuery));
            if (matchingSentence != null)
                return matchingSentence;

            var source = string.Join(
                " ",
                new[]
                {
                    document.Title,
                    document.Description,
                    document.Content
                }.Where(value => !string.IsNullOrWhiteSpace(value)));

            return BuildFallbackSnippet(source, query);
        }

        private static string? BuildFallbackSnippet(Domain.Models.Document document, string? query)
        {
            if (string.IsNullOrWhiteSpace(query))
                return null;

            var source = string.Join(
                " ",
                new[]
                {
                    document.Title,
                    document.Metadata?.Description,
                    document.Content
                }.Where(value => !string.IsNullOrWhiteSpace(value)));

            if (string.IsNullOrWhiteSpace(source))
                return null;

            return BuildFallbackSnippet(source, query);
        }

        private static string? BuildFallbackSnippet(string source, string query)
        {
            if (string.IsNullOrWhiteSpace(source))
                return null;

            var index = source.IndexOf(query, StringComparison.OrdinalIgnoreCase);
            if (index < 0)
            {
                return source.Length <= 180
                    ? source
                    : $"{source[..180]}...";
            }

            var start = Math.Max(0, index - 60);
            var length = Math.Min(source.Length - start, 180);
            var snippet = source.Substring(start, length).Trim();

            if (start > 0)
                snippet = $"...{snippet}";

            if (start + length < source.Length)
                snippet = $"{snippet}...";

            return snippet;
        }
    }
}
