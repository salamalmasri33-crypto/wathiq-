using System.Net;
using System.Text;
using System.Text.Json;
using eArchiveSystem.Application.DTOs;
using eArchiveSystem.Application.Interfaces.Persistence;
using eArchiveSystem.Infrastructure.Persistence.Data;
using Microsoft.Extensions.Options;

namespace eArchiveSystem.Infrastructure.Persistence.Repositories
{
    public class ElasticsearchDocumentSearchRepository : IDocumentSearchRepository
    {
        private static readonly JsonSerializerOptions JsonOptions = new(JsonSerializerDefaults.Web);
        private const string IndexAnalyzerName = "document_index_analyzer";
        private const string SearchAnalyzerName = "document_search_analyzer";
        private const string SimpleAnalyzerName = "document_simple_analyzer";

        private readonly IHttpClientFactory _httpClientFactory;
        private readonly ElasticsearchSettings _settings;

        public ElasticsearchDocumentSearchRepository(
            IHttpClientFactory httpClientFactory,
            IOptions<ElasticsearchSettings> settings)
        {
            _httpClientFactory = httpClientFactory;
            _settings = settings.Value;
        }

        public async Task IndexAsync(SearchDocumentIndex document)
        {
            using var client = CreateClient();
            await EnsureIndexExistsAsync(client);
            await EnsureSentenceTextsMappingAsync(client);
            using var request = CreateJsonRequest(
                HttpMethod.Put,
                $"{_settings.IndexName}/_doc/{document.Id}",
                document);

            using var response = await client.SendAsync(request);
            response.EnsureSuccessStatusCode();
        }

        public async Task DeleteAsync(string documentId)
        {
            using var client = CreateClient();
            using var response = await client.DeleteAsync($"{_settings.IndexName}/_doc/{documentId}");

            if (response.StatusCode != HttpStatusCode.NotFound)
                response.EnsureSuccessStatusCode();
        }

        public async Task EnsureIndexExistsAsync()
        {
            using var client = CreateClient();
            await EnsureIndexExistsAsync(client);
        }

        public async Task RecreateIndexAsync()
        {
            using var client = CreateClient();
            using var deleteResponse = await client.DeleteAsync(_settings.IndexName);

            if (deleteResponse.StatusCode != HttpStatusCode.NotFound)
                deleteResponse.EnsureSuccessStatusCode();

            using var createRequest = CreateJsonRequest(
                HttpMethod.Put,
                _settings.IndexName,
                BuildIndexDefinition());

            using var createResponse = await client.SendAsync(createRequest);
            createResponse.EnsureSuccessStatusCode();
        }

        public async Task<(IReadOnlyList<SearchDocumentHit> Hits, long Total)> SearchAsync(SearchDocumentsDto dto, SearchAccessScope scope)
        {
            using var client = CreateClient();
            await EnsureIndexExistsAsync(client);
            using var request = CreateJsonRequest(
                HttpMethod.Post,
                $"{_settings.IndexName}/_search",
                BuildSearchPayload(dto, scope));

            using var response = await client.SendAsync(request);

            if (response.StatusCode == HttpStatusCode.NotFound)
                return (Array.Empty<SearchDocumentHit>(), 0);

            response.EnsureSuccessStatusCode();

            await using var stream = await response.Content.ReadAsStreamAsync();
            using var document = await JsonDocument.ParseAsync(stream);

            if (!document.RootElement.TryGetProperty("hits", out var hitsNode) ||
                !hitsNode.TryGetProperty("hits", out var innerHits))
            {
                return (Array.Empty<SearchDocumentHit>(), 0);
            }

            long total = 0;
            if (hitsNode.TryGetProperty("total", out var totalNode) &&
                totalNode.TryGetProperty("value", out var totalValue))
            {
                total = totalValue.GetInt64();
            }

            var hits = innerHits
                .EnumerateArray()
                .Select(hit =>
                {
                    var id = hit.GetProperty("_id").GetString();
                    if (string.IsNullOrWhiteSpace(id))
                        return null;

                    return new SearchDocumentHit
                    {
                        Id = id,
                        Snippet = ExtractSnippet(hit)
                    };
                })
                .Where(hit => hit != null)
                .Cast<SearchDocumentHit>()
                .ToList();

            return (hits, total);
        }

        private async Task EnsureIndexExistsAsync(HttpClient client)
        {
            using var existsResponse = await client.SendAsync(
                new HttpRequestMessage(HttpMethod.Head, _settings.IndexName));

            if (existsResponse.StatusCode == HttpStatusCode.OK)
                return;

            if (existsResponse.StatusCode != HttpStatusCode.NotFound)
                existsResponse.EnsureSuccessStatusCode();

            using var createRequest = CreateJsonRequest(
                HttpMethod.Put,
                _settings.IndexName,
                BuildIndexDefinition());

            using var createResponse = await client.SendAsync(createRequest);

            if (createResponse.StatusCode == HttpStatusCode.BadRequest)
            {
                var content = await createResponse.Content.ReadAsStringAsync();

                if (content.Contains("resource_already_exists_exception", StringComparison.OrdinalIgnoreCase))
                    return;
            }

            createResponse.EnsureSuccessStatusCode();
        }

        private HttpClient CreateClient()
        {
            var client = _httpClientFactory.CreateClient("ElasticClient");

            client.BaseAddress = new Uri(AppendTrailingSlash(_settings.Url));

            var byteArray = Encoding.ASCII.GetBytes($"{_settings.Username}:{_settings.Password}");
            client.DefaultRequestHeaders.Authorization =
                new System.Net.Http.Headers.AuthenticationHeaderValue(
                    "Basic",
                    Convert.ToBase64String(byteArray)
                );

            return client;
        }

        private static HttpRequestMessage CreateJsonRequest(HttpMethod method, string relativeUrl, object payload)
        {
            return new HttpRequestMessage(method, relativeUrl)
            {
                Content = new StringContent(
                    JsonSerializer.Serialize(payload, JsonOptions),
                    Encoding.UTF8,
                    "application/json")
            };
        }

        private static object BuildIndexDefinition()
        {
            return new
            {
                settings = new
                {
                    analysis = new
                    {
                        char_filter = new
                        {
                            arabic_char_mapping = new
                            {
                                type = "mapping",
                                mappings = new[]
                                {
                                    "\u0623 => \u0627",
                                    "\u0625 => \u0627",
                                    "\u0622 => \u0627",
                                    "\u0649 => \u064A",
                                    "\u0624 => \u0648",
                                    "\u0626 => \u064A",
                                    "\u0629 => \u0647"
                                }
                            }
                        },
                        filter = new
                        {
                            arabic_stop_custom = new
                            {
                                type = "stop",
                                stopwords = new[]
                                {
                                    "_arabic_",
                                    "\u0647\u0630\u0627",
                                    "\u0647\u0630\u0647",
                                    "\u0630\u0644\u0643",
                                    "\u062A\u0644\u0643",
                                    "\u0641\u064A",
                                    "\u0645\u0646",
                                    "\u0627\u0644\u0649",
                                    "\u0625\u0644\u0649",
                                    "\u0639\u0644\u0649",
                                    "\u0639\u0646",
                                    "\u062B\u0645",
                                    "\u0642\u062F"
                                }
                            },
                            english_stop_custom = new
                            {
                                type = "stop",
                                stopwords = "_english_"
                            },
                            english_stemmer = new
                            {
                                type = "stemmer",
                                language = "english"
                            },
                            arabic_stemmer = new
                            {
                                type = "stemmer",
                                language = "arabic"
                            }
                        },
                        analyzer = new
                        {
                            document_index_analyzer = new
                            {
                                type = "custom",
                                tokenizer = "standard",
                                char_filter = new[] { "arabic_char_mapping" },
                                filter = new[]
                                {
                                    "lowercase",
                                    "decimal_digit",
                                    "arabic_normalization",
                                    "arabic_stop_custom",
                                    "english_stop_custom",
                                    "arabic_stemmer",
                                    "english_stemmer"
                                }
                            },
                            document_search_analyzer = new
                            {
                                type = "custom",
                                tokenizer = "standard",
                                char_filter = new[] { "arabic_char_mapping" },
                                filter = new[]
                                {
                                    "lowercase",
                                    "decimal_digit",
                                    "arabic_normalization",
                                    "arabic_stop_custom",
                                    "english_stop_custom",
                                    "arabic_stemmer",
                                    "english_stemmer"
                                }
                            },
                            document_simple_analyzer = new
                            {
                                type = "custom",
                                tokenizer = "standard",
                                char_filter = new[] { "arabic_char_mapping" },
                                filter = new[]
                                {
                                    "lowercase",
                                    "decimal_digit",
                                    "arabic_normalization"
                                }
                            }
                        }
                    }
                },
                mappings = new
                {
                    properties = new
                    {
                        id = new { type = "keyword" },
                        title = new
                        {
                            type = "text",
                            analyzer = IndexAnalyzerName,
                            search_analyzer = SearchAnalyzerName,
                            fields = new
                            {
                                keyword = new
                                {
                                    type = "keyword",
                                    ignore_above = 256
                                },
                                simple = new
                                {
                                    type = "text",
                                    analyzer = SimpleAnalyzerName,
                                    search_analyzer = SimpleAnalyzerName
                                }
                            }
                        },
                        content = new
                        {
                            type = "text",
                            analyzer = IndexAnalyzerName,
                            search_analyzer = SearchAnalyzerName,
                            fields = new
                            {
                                simple = new
                                {
                                    type = "text",
                                    analyzer = SimpleAnalyzerName,
                                    search_analyzer = SimpleAnalyzerName
                                }
                            }
                        },
                        sentenceTexts = CreateSentenceTextsMapping(),
                        description = new
                        {
                            type = "text",
                            analyzer = IndexAnalyzerName,
                            search_analyzer = SearchAnalyzerName,
                            fields = new
                            {
                                simple = new
                                {
                                    type = "text",
                                    analyzer = SimpleAnalyzerName,
                                    search_analyzer = SimpleAnalyzerName
                                }
                            }
                        },
                        tags = new
                        {
                            type = "text",
                            analyzer = IndexAnalyzerName,
                            search_analyzer = SearchAnalyzerName,
                            fields = new
                            {
                                simple = new
                                {
                                    type = "text",
                                    analyzer = SimpleAnalyzerName,
                                    search_analyzer = SimpleAnalyzerName
                                }
                            }
                        },
                        broadGenre = new { type = "keyword" },
                        specificGenre = new { type = "keyword" },
                        documentType = new { type = "keyword" },
                        issuingEntity = new
                        {
                            type = "text",
                            analyzer = IndexAnalyzerName,
                            search_analyzer = SearchAnalyzerName,
                            fields = new
                            {
                                simple = new
                                {
                                    type = "text",
                                    analyzer = SimpleAnalyzerName,
                                    search_analyzer = SimpleAnalyzerName
                                }
                            }
                        },
                        referenceNumber = new { type = "keyword" },
                        status = new { type = "keyword" },
                        priority = new { type = "keyword" },
                        isSensitive = new { type = "boolean" },
                        institutionId = new { type = "keyword" },
                        departmentId = new { type = "keyword" },
                        department = new { type = "keyword" },
                        userId = new { type = "keyword" },
                        createdAt = new { type = "date" },
                        updatedAt = new { type = "date" }
                    }
                }
            };
        }

        private static object BuildSearchPayload(SearchDocumentsDto dto, SearchAccessScope scope)
        {
            var must = new List<object>();
            var should = new List<object>();
            var filter = new List<object>();
            var sort = BuildSort(dto);
            var from = Math.Max(0, (dto.Page - 1) * dto.PageSize);

            if (!string.IsNullOrWhiteSpace(dto.Query))
            {
                must.Add(new
                {
                    multi_match = new
                    {
                        query = dto.Query,
                        fields = new[]
                        {
                            "title^5",
                            "title.simple^7",
                            "description^4",
                            "description.simple^5",
                            "tags^3",
                            "tags.simple^4",
                            "content^2",
                            "content.simple^3",
                            "sentenceTexts^2",
                            "sentenceTexts.simple^3",
                            "issuingEntity^3",
                            "issuingEntity.simple^4",
                            "referenceNumber^4"
                        },
                        type = "best_fields",
                        fuzziness = "AUTO"
                    }
                });

                should.Add(new
                {
                    match_phrase = new
                    {
                        title = new
                        {
                            query = dto.Query,
                            boost = 8
                        }
                    }
                });

                should.Add(new
                {
                    match_phrase = new Dictionary<string, object>
                    {
                        ["title.simple"] = new
                        {
                            query = dto.Query,
                            boost = 10
                        }
                    }
                });

                should.Add(new
                {
                    match_phrase = new
                    {
                        content = new
                        {
                            query = dto.Query,
                            slop = 2,
                            boost = 4
                        }
                    }
                });

                should.Add(new
                {
                    match_phrase = new
                    {
                        description = new
                        {
                            query = dto.Query,
                            slop = 2,
                            boost = 5
                        }
                    }
                });

                should.Add(new
                {
                    match_phrase = new Dictionary<string, object>
                    {
                        ["description.simple"] = new
                        {
                            query = dto.Query,
                            slop = 2,
                            boost = 6
                        }
                    }
                });
            }

            if (!string.IsNullOrWhiteSpace(scope.OwnerUserId))
            {
                filter.Add(new { term = new { userId = scope.OwnerUserId } });
            }

            if (!string.IsNullOrWhiteSpace(scope.InstitutionId))
            {
                filter.Add(new { term = new { institutionId = scope.InstitutionId } });
            }

            if (!string.IsNullOrWhiteSpace(dto.InstitutionId))
            {
                filter.Add(new { term = new { institutionId = dto.InstitutionId } });
            }

            if (!string.IsNullOrWhiteSpace(scope.DepartmentId))
            {
                filter.Add(new { term = new { departmentId = scope.DepartmentId } });
            }

            if (!string.IsNullOrWhiteSpace(dto.BroadGenre))
                filter.Add(new { term = new { broadGenre = dto.BroadGenre } });

            if (!string.IsNullOrWhiteSpace(dto.SpecificGenre))
                filter.Add(new { term = new { specificGenre = dto.SpecificGenre } });

            var departmentFilter = string.IsNullOrWhiteSpace(dto.DepartmentId) ? dto.Department : dto.DepartmentId;
            if (!string.IsNullOrWhiteSpace(departmentFilter))
            {
                filter.Add(new { term = new { departmentId = departmentFilter } });
            }

            if (dto.FromDate.HasValue || dto.ToDate.HasValue)
            {
                filter.Add(new
                {
                    range = new
                    {
                        createdAt = new
                        {
                            gte = dto.FromDate?.ToString("O"),
                            lte = dto.ToDate?.ToString("O")
                        }
                    }
                });
            }

            if (dto.Status.HasValue)
            {
                filter.Add(new { term = new { status = dto.Status.Value.ToString() } });
            }

            if (dto.Priority.HasValue)
            {
                filter.Add(new { term = new { priority = dto.Priority.Value.ToString() } });
            }

            var boolQuery = new
            {
                @bool = new
                {
                    must = must.Count > 0
                        ? must
                        : new List<object> { new { match_all = new { } } },
                    should,
                    filter
                }
            };

            var queryObject = new
            {
                function_score = new
                {
                    query = boolQuery,
                    boost_mode = "sum",
                    score_mode = "sum",
                    functions = new object[]
                    {
                        new
                        {
                            gauss = new
                            {
                                createdAt = new
                                {
                                    scale = "30d",
                                    decay = 0.7
                                }
                            },
                            weight = 1.5
                        }
                    }
                }
            };

            var highlight = BuildHighlight(dto);

            if (sort is null && highlight is null)
            {
                return new
                {
                    from,
                    size = dto.PageSize,
                    track_total_hits = true,
                    query = queryObject
                };
            }

            if (sort is null)
            {
                return new
                {
                    from,
                    size = dto.PageSize,
                    track_total_hits = true,
                    highlight,
                    query = queryObject
                };
            }

            if (highlight is null)
            {
                return new
                {
                    from,
                    size = dto.PageSize,
                    track_total_hits = true,
                    sort,
                    query = queryObject
                };
            }

            return new
            {
                from,
                size = dto.PageSize,
                track_total_hits = true,
                sort,
                highlight,
                query = queryObject
            };

        }

        private static object[]? BuildSort(SearchDocumentsDto dto)
        {
            if (!string.IsNullOrWhiteSpace(dto.SortBy))
            {
                return dto.SortBy switch
                {
                    "Title" => new object[]
                    {
                        new Dictionary<string, object>
                        {
                            ["title.keyword"] = new
                            {
                                unmapped_type = "keyword",
                                missing = "_last",
                                order = dto.Desc ? "desc" : "asc"
                            }
                        }
                    },
                    "CreatedAt" => new object[]
                    {
                        new
                        {
                            createdAt = new
                            {
                                order = dto.Desc ? "desc" : "asc"
                            }
                        }
                    },
                    "Priority" => new object[]
                    {
                        new
                        {
                            priority = new
                            {
                                order = dto.Desc ? "desc" : "asc"
                            }
                        }
                    },
                    _ => null
                };
            }

            if (string.IsNullOrWhiteSpace(dto.Query))
            {
                return new object[]
                {
                    new
                    {
                        createdAt = new
                        {
                            order = "desc"
                        }
                    }
                };
            }

            return null;
        }

        private static string AppendTrailingSlash(string url)
        {
            return url.EndsWith("/", StringComparison.Ordinal) ? url : $"{url}/";
        }

        private static object? BuildHighlight(SearchDocumentsDto dto)
        {
            if (string.IsNullOrWhiteSpace(dto.Query))
                return null;

            return new
            {
                pre_tags = new[] { "<em>" },
                post_tags = new[] { "</em>" },
                require_field_match = false,
                fields = new Dictionary<string, object>
                {
                    ["title"] = new
                    {
                        number_of_fragments = 1
                    },
                    ["title.simple"] = new
                    {
                        number_of_fragments = 1
                    },
                    ["description"] = new
                    {
                        fragment_size = 180,
                        number_of_fragments = 2
                    },
                    ["description.simple"] = new
                    {
                        fragment_size = 180,
                        number_of_fragments = 2
                    },
                    ["content"] = new
                    {
                        fragment_size = 180,
                        number_of_fragments = 2
                    },
                    ["content.simple"] = new
                    {
                        fragment_size = 180,
                        number_of_fragments = 2
                    },
                    ["sentenceTexts"] = new
                    {
                        number_of_fragments = 0
                    },
                    ["sentenceTexts.simple"] = new
                    {
                        number_of_fragments = 0
                    },
                    ["tags"] = new
                    {
                        number_of_fragments = 1
                    },
                    ["tags.simple"] = new
                    {
                        number_of_fragments = 1
                    },
                    ["issuingEntity"] = new
                    {
                        number_of_fragments = 1
                    },
                    ["issuingEntity.simple"] = new
                    {
                        number_of_fragments = 1
                    }
                }
            };
        }

        private static string? ExtractSnippet(JsonElement hit)
        {
            if (!hit.TryGetProperty("highlight", out var highlight))
                return null;

            foreach (var fieldName in new[] { "sentenceTexts", "sentenceTexts.simple", "title", "title.simple", "description", "description.simple", "content", "content.simple", "tags", "tags.simple", "issuingEntity", "issuingEntity.simple" })
            {
                if (!highlight.TryGetProperty(fieldName, out var fragments) || fragments.ValueKind != JsonValueKind.Array)
                    continue;

                var values = fragments
                    .EnumerateArray()
                    .Select(fragment => fragment.GetString())
                    .Where(fragment => !string.IsNullOrWhiteSpace(fragment))
                    .ToList();

                if (values.Count > 0)
                    return string.Join(" ... ", values);
            }

            return null;
        }

        private async Task EnsureSentenceTextsMappingAsync(HttpClient client)
        {
            using var mappingResponse = await client.GetAsync(
                $"{_settings.IndexName}/_mapping/field/sentenceTexts");

            if (mappingResponse.StatusCode == HttpStatusCode.OK)
                return;

            if (mappingResponse.StatusCode != HttpStatusCode.NotFound)
                mappingResponse.EnsureSuccessStatusCode();

            using var mappingRequest = CreateJsonRequest(
                HttpMethod.Put,
                $"{_settings.IndexName}/_mapping",
                new
                {
                    properties = new
                    {
                        sentenceTexts = CreateSentenceTextsMapping()
                    }
                });

            using var updateResponse = await client.SendAsync(mappingRequest);
            updateResponse.EnsureSuccessStatusCode();
        }

        private static object CreateSentenceTextsMapping()
        {
            return new
            {
                type = "text",
                analyzer = IndexAnalyzerName,
                search_analyzer = SearchAnalyzerName,
                fields = new
                {
                    simple = new
                    {
                        type = "text",
                        analyzer = SimpleAnalyzerName,
                        search_analyzer = SimpleAnalyzerName
                    }
                }
            };
        }
    }
}
