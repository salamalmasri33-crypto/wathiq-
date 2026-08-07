using System.Security.Claims;
using System.Text.Json.Nodes;
using eArchiveSystem.Application.Classification.Models;
using eArchiveSystem.Application.Exceptions;
using eArchiveSystem.Application.Interfaces.Services;
using eArchiveSystem.Infrastructure.Configuration;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.Extensions.Options;

namespace eArchiveSystem.Presentation.Controllers;

[ApiController]
[Route("api/institution-classification")]
[Authorize]
[Produces("application/json")]
[ProducesResponseType(StatusCodes.Status400BadRequest)]
[ProducesResponseType(StatusCodes.Status401Unauthorized)]
[ProducesResponseType(StatusCodes.Status403Forbidden)]
[ProducesResponseType(StatusCodes.Status404NotFound)]
[ProducesResponseType(StatusCodes.Status409Conflict)]
[ProducesResponseType(StatusCodes.Status502BadGateway)]
public sealed class InstitutionClassificationController : ControllerBase
{
    private const string AdminRoles = "SystemAdmin,InstitutionAdmin";
    private const string MemberRoles = "SystemAdmin,InstitutionAdmin,Manager,Employee";
    private readonly IInstitutionClassificationService _service;
    private readonly AraGenreOptions _options;

    public InstitutionClassificationController(IInstitutionClassificationService service, IOptions<AraGenreOptions> options)
    {
        _service = service;
        _options = options.Value;
    }

    [HttpGet("status"), Authorize(Roles = AdminRoles), Tags("Institution Classification")]
    [ProducesResponseType(typeof(JsonNode), StatusCodes.Status200OK)]
    public async Task<IActionResult> Status([FromQuery] string? institutionId, CancellationToken ct) => Ok(await _service.GetStatusAsync(UserId(), institutionId, ct));

    [HttpGet("taxonomy"), Authorize(Roles = AdminRoles), Tags("Classification Taxonomy")]
    [ProducesResponseType(typeof(JsonNode), StatusCodes.Status200OK)]
    public async Task<IActionResult> Taxonomy([FromQuery] string? institutionId, CancellationToken ct) => Ok(await _service.GetTaxonomyAsync(UserId(), institutionId, ct));

    [HttpGet("taxonomy-options"), Authorize(Roles = MemberRoles), Tags("Classification Taxonomy")]
    [ProducesResponseType(typeof(JsonNode), StatusCodes.Status200OK)]
    public async Task<IActionResult> TaxonomyOptions([FromQuery] string? institutionId, CancellationToken ct) =>
        Ok(await _service.GetTaxonomyOptionsAsync(UserId(), institutionId, ct));

    [HttpPost("classify-test"), Authorize(Roles = MemberRoles), Tags("Classification Testing")]
    [ProducesResponseType(typeof(ClassifyTextResultDto), StatusCodes.Status200OK)]
    public async Task<IActionResult> ClassifyTest([FromBody] ClassifyTextDto dto, CancellationToken ct) => Ok(await _service.ClassifyTextAsync(UserId(), dto, ct));

    [HttpGet("broad"), Authorize(Roles = AdminRoles), Tags("Classification Taxonomy")]
    public async Task<IActionResult> Broad([FromQuery] string? institutionId, CancellationToken ct) => Ok(await _service.GetBroadAsync(UserId(), institutionId, null, ForwardedQuery(), ct));
    [HttpGet("broad/{broadId}"), Authorize(Roles = AdminRoles), Tags("Classification Taxonomy")]
    public async Task<IActionResult> BroadById(string broadId, [FromQuery] string? institutionId, CancellationToken ct) => Ok(await _service.GetBroadAsync(UserId(), institutionId, broadId, ForwardedQuery(), ct));
    [HttpPost("broad"), Authorize(Roles = AdminRoles), Tags("Classification Taxonomy")]
    public async Task<IActionResult> CreateBroad([FromQuery] string? institutionId, [FromBody] JsonNode body, CancellationToken ct) => Ok(await _service.CreateBroadAsync(UserId(), institutionId, body, ct));
    [HttpPatch("broad/{broadId}"), Authorize(Roles = AdminRoles), Tags("Classification Taxonomy")]
    public async Task<IActionResult> UpdateBroad(string broadId, [FromQuery] string? institutionId, [FromBody] JsonNode body, CancellationToken ct) => Ok(await _service.UpdateBroadAsync(UserId(), institutionId, broadId, body, ct));
    [HttpGet("broad/{broadId}/deletion-impact"), Authorize(Roles = AdminRoles), Tags("Classification Taxonomy")]
    public async Task<IActionResult> BroadImpact(string broadId, [FromQuery] string? institutionId, CancellationToken ct) => Ok(await _service.GetBroadDeletionImpactAsync(UserId(), institutionId, broadId, ct));
    [HttpDelete("broad/{broadId}"), Authorize(Roles = AdminRoles), Tags("Classification Taxonomy")]
    public async Task<IActionResult> DeleteBroad(string broadId, [FromQuery] string? institutionId, [FromQuery] bool cascade, CancellationToken ct) => Ok(await _service.DeleteBroadAsync(UserId(), institutionId, broadId, cascade, ct));

    [HttpGet("specific"), Authorize(Roles = AdminRoles), Tags("Classification Taxonomy")]
    public async Task<IActionResult> Specific([FromQuery] string? institutionId, CancellationToken ct) => Ok(await _service.GetSpecificAsync(UserId(), institutionId, null, ForwardedQuery(), ct));
    [HttpGet("specific/{specificId}"), Authorize(Roles = AdminRoles), Tags("Classification Taxonomy")]
    public async Task<IActionResult> SpecificById(string specificId, [FromQuery] string? institutionId, CancellationToken ct) => Ok(await _service.GetSpecificAsync(UserId(), institutionId, specificId, ForwardedQuery(), ct));
    [HttpPost("specific"), Authorize(Roles = AdminRoles), Tags("Classification Taxonomy")]
    public async Task<IActionResult> CreateSpecific([FromQuery] string? institutionId, [FromBody] JsonNode body, CancellationToken ct) => Ok(await _service.CreateSpecificAsync(UserId(), institutionId, body, ct));
    [HttpPatch("specific/{specificId}"), Authorize(Roles = AdminRoles), Tags("Classification Taxonomy")]
    public async Task<IActionResult> UpdateSpecific(string specificId, [FromQuery] string? institutionId, [FromBody] JsonNode body, CancellationToken ct) => Ok(await _service.UpdateSpecificAsync(UserId(), institutionId, specificId, body, ct));
    [HttpGet("specific/{specificId}/deletion-impact"), Authorize(Roles = AdminRoles), Tags("Classification Taxonomy")]
    public async Task<IActionResult> SpecificImpact(string specificId, [FromQuery] string? institutionId, CancellationToken ct) => Ok(await _service.GetSpecificDeletionImpactAsync(UserId(), institutionId, specificId, ct));
    [HttpDelete("specific/{specificId}"), Authorize(Roles = AdminRoles), Tags("Classification Taxonomy")]
    public async Task<IActionResult> DeleteSpecific(string specificId, [FromQuery] string? institutionId, [FromQuery] bool cascade, CancellationToken ct) => Ok(await _service.DeleteSpecificAsync(UserId(), institutionId, specificId, cascade, ct));

    [HttpGet("examples"), Authorize(Roles = AdminRoles), Tags("Classification Examples")]
    public async Task<IActionResult> Examples([FromQuery] string? institutionId, CancellationToken ct) => Ok(await _service.GetExamplesAsync(UserId(), institutionId, null, ForwardedQuery(), ct));
    [HttpGet("examples/{exampleId}"), Authorize(Roles = AdminRoles), Tags("Classification Examples")]
    public async Task<IActionResult> ExampleById(string exampleId, [FromQuery] string? institutionId, CancellationToken ct) => Ok(await _service.GetExamplesAsync(UserId(), institutionId, exampleId, ForwardedQuery(), ct));
    [HttpPost("examples"), Authorize(Roles = AdminRoles), Tags("Classification Examples")]
    public async Task<IActionResult> CreateExample([FromQuery] string? institutionId, [FromBody] JsonNode body, CancellationToken ct) => Ok(await _service.CreateExampleAsync(UserId(), institutionId, body, ct));
    [HttpPatch("examples/{exampleId}"), Authorize(Roles = AdminRoles), Tags("Classification Examples")]
    public async Task<IActionResult> UpdateExample(string exampleId, [FromQuery] string? institutionId, [FromBody] JsonNode body, CancellationToken ct) => Ok(await _service.UpdateExampleAsync(UserId(), institutionId, exampleId, body, ct));
    [HttpDelete("examples/{exampleId}"), Authorize(Roles = AdminRoles), Tags("Classification Examples")]
    public async Task<IActionResult> DeleteExample(string exampleId, [FromQuery] string? institutionId, CancellationToken ct) => Ok(await _service.DeleteExampleAsync(UserId(), institutionId, exampleId, ct));

    [HttpPut("taxonomy"), Authorize(Roles = AdminRoles), Tags("Classification Taxonomy")]
    public async Task<IActionResult> ReplaceTaxonomy([FromQuery] string? institutionId, [FromBody] JsonNode body, CancellationToken ct) => Ok(await _service.ReplaceTaxonomyAsync(UserId(), institutionId, body, ForwardedQuery(), ct));
    [HttpPut("examples"), Authorize(Roles = AdminRoles), Tags("Classification Examples")]
    public async Task<IActionResult> ReplaceExamples([FromQuery] string? institutionId, [FromBody] JsonNode body, CancellationToken ct) => Ok(await _service.ReplaceExamplesAsync(UserId(), institutionId, body, ForwardedQuery(), ct));
    [HttpPost("rebuild-index"), Authorize(Roles = AdminRoles), Tags("Institution Classification")]
    public async Task<IActionResult> RebuildIndex([FromQuery] string? institutionId, [FromBody] JsonNode? body, CancellationToken ct) => Ok(await _service.RebuildIndexAsync(UserId(), institutionId, body, ForwardedQuery(), ct));

    [HttpPost("import-definitions-file"), Authorize(Roles = AdminRoles), Tags("Classification Import")]
    [Consumes("multipart/form-data")]
    public Task<IActionResult> ImportDefinitions([FromQuery] string? institutionId, IFormFile file, CancellationToken ct) => Import(institutionId, file, "import-definitions-file", ct);
    [HttpPost("import-examples-file"), Authorize(Roles = AdminRoles), Tags("Classification Import")]
    [Consumes("multipart/form-data")]
    public Task<IActionResult> ImportExamples([FromQuery] string? institutionId, IFormFile file, CancellationToken ct) => Import(institutionId, file, "import-examples-file", ct);

    private async Task<IActionResult> Import(string? institutionId, IFormFile? file, string endpoint, CancellationToken ct)
    {
        if (file is null || file.Length == 0) throw new ValidationException("A non-empty JSON file is required");
        if (!string.Equals(Path.GetExtension(file.FileName), ".json", StringComparison.OrdinalIgnoreCase)) throw new ValidationException("Only .json files are accepted");
        if (file.Length > _options.MaxImportFileBytes) throw new ValidationException($"File exceeds the maximum size of {_options.MaxImportFileBytes} bytes");
        await using var stream = file.OpenReadStream();
        return Ok(await _service.ImportFileAsync(UserId(), institutionId, endpoint, stream, Path.GetFileName(file.FileName), ForwardedQuery(), ct));
    }

    private string UserId() => User.FindFirst(ClaimTypes.NameIdentifier)?.Value ?? User.FindFirst("sub")?.Value ?? throw new UnauthorizedActionException("Authenticated user identifier is missing");

    private string? ForwardedQuery()
    {
        var values = Request.Query
            .Where(x => !string.Equals(x.Key, "institutionId", StringComparison.OrdinalIgnoreCase))
            .SelectMany(x => x.Value.Select(v => new KeyValuePair<string, string?>(x.Key, v)));
        var query = QueryString.Create(values).Value;
        return string.IsNullOrEmpty(query) ? null : query[1..];
    }
}
