using System.Reflection;
using System.Text.Json;
using eArchiveSystem.Application.DTOs;
using eArchiveSystem.Infrastructure.Persistence.Repositories;

namespace eArchiveSystem.Tests;

public sealed class ElasticsearchSentenceSearchTests
{
    [Fact]
    public void Index_definition_maps_sentence_texts_with_existing_arabic_analyzers()
    {
        using var definition = JsonDocument.Parse(JsonSerializer.Serialize(InvokePrivateStatic("BuildIndexDefinition")));
        var sentenceTexts = definition.RootElement
            .GetProperty("mappings")
            .GetProperty("properties")
            .GetProperty("sentenceTexts");

        Assert.Equal("text", sentenceTexts.GetProperty("type").GetString());
        Assert.Equal("document_index_analyzer", sentenceTexts.GetProperty("analyzer").GetString());
        Assert.Equal("document_search_analyzer", sentenceTexts.GetProperty("search_analyzer").GetString());
        Assert.Equal("document_simple_analyzer", sentenceTexts.GetProperty("fields").GetProperty("simple").GetProperty("analyzer").GetString());
    }

    [Fact]
    public void Search_payload_includes_sentence_texts_without_removing_existing_content_fields()
    {
        var payload = InvokePrivateStatic(
            "BuildSearchPayload",
            new SearchDocumentsDto { Query = "قرار", Page = 1, PageSize = 10 },
            new SearchAccessScope());
        var json = JsonSerializer.Serialize(payload);

        Assert.Contains("sentenceTexts^2", json, StringComparison.Ordinal);
        Assert.Contains("sentenceTexts.simple^3", json, StringComparison.Ordinal);
        Assert.Contains("content^2", json, StringComparison.Ordinal);
        Assert.Contains("title^5", json, StringComparison.Ordinal);
    }

    [Fact]
    public void Sentence_highlight_is_preferred_as_the_search_snippet()
    {
        using var hit = JsonDocument.Parse("""
        {
          "highlight": {
            "content": ["arbitrary <em>قرار</em> fragment"],
            "sentenceTexts": ["صدر <em>القرار</em> رقم 25 بتاريخ اليوم."]
          }
        }
        """);

        var snippet = Assert.IsType<string>(InvokePrivateStatic("ExtractSnippet", hit.RootElement));

        Assert.Equal("صدر <em>القرار</em> رقم 25 بتاريخ اليوم.", snippet);
    }

    private static object? InvokePrivateStatic(string name, params object[] arguments)
    {
        var method = typeof(ElasticsearchDocumentSearchRepository).GetMethod(
            name,
            BindingFlags.NonPublic | BindingFlags.Static)!;

        return method.Invoke(null, arguments);
    }
}
