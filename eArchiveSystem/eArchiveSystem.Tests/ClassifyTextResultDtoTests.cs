using System.Text.Json;
using eArchiveSystem.Application.Classification.Models;

namespace eArchiveSystem.Tests;

public sealed class ClassifyTextResultDtoTests
{
    [Fact]
    public void Wathiq_response_uses_camel_case()
    {
        var result = new ClassifyTextResultDto
        {
            Id = "document_123",
            BroadGenre = "AdministrativeAndOrganizational",
            SpecificGenre = "AdministrativeDecision"
        };

        var json = JsonSerializer.Serialize(result, new JsonSerializerOptions(JsonSerializerDefaults.Web));

        Assert.Contains("\"broadGenre\"", json);
        Assert.Contains("\"specificGenre\"", json);
        Assert.DoesNotContain("broad_genre", json);
    }
}
