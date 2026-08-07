using Microsoft.Extensions.Options;

namespace eArchiveSystem.Infrastructure.Configuration;

public sealed class AraSegOptionsValidator : IValidateOptions<AraSegOptions>
{
    private const int MaximumTimeoutSeconds = 600;

    public ValidateOptionsResult Validate(string? name, AraSegOptions options)
    {
        ArgumentNullException.ThrowIfNull(options);

        var failures = new List<string>();

        if (string.IsNullOrWhiteSpace(options.BaseUrl)
            || !Uri.TryCreate(options.BaseUrl, UriKind.Absolute, out var baseUri)
            || (baseUri.Scheme != Uri.UriSchemeHttp && baseUri.Scheme != Uri.UriSchemeHttps))
        {
            failures.Add("AraSeg:BaseUrl must be an absolute HTTP or HTTPS URI.");
        }

        if (string.IsNullOrWhiteSpace(options.SegmentTextPath))
        {
            failures.Add("AraSeg:SegmentTextPath is required.");
        }

        if (!string.Equals(options.Track, "PA", StringComparison.Ordinal))
        {
            failures.Add("AraSeg:Track must be 'PA' for this milestone.");
        }

        if (options.TimeoutSeconds <= 0 || options.TimeoutSeconds > MaximumTimeoutSeconds)
        {
            failures.Add($"AraSeg:TimeoutSeconds must be between 1 and {MaximumTimeoutSeconds}.");
        }

        return failures.Count == 0
            ? ValidateOptionsResult.Success
            : ValidateOptionsResult.Fail(failures);
    }
}
