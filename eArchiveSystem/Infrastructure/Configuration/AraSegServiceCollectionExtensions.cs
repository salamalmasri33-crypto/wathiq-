using eArchiveSystem.Application.Segmentation.Abstractions;
using eArchiveSystem.Application.Segmentation.Services;
using eArchiveSystem.Infrastructure.AI.Clients;
using eArchiveSystem.Infrastructure.AI.Segmentation;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Options;

namespace eArchiveSystem.Infrastructure.Configuration;

public static class AraSegServiceCollectionExtensions
{
    public static IServiceCollection AddAraSegSegmentation(this IServiceCollection services, IConfiguration configuration)
    {
        ArgumentNullException.ThrowIfNull(services);
        ArgumentNullException.ThrowIfNull(configuration);

        services.AddSingleton<IValidateOptions<AraSegOptions>, AraSegOptionsValidator>();
        services.AddOptions<AraSegOptions>()
            .Bind(configuration.GetSection("AraSeg"))
            .ValidateOnStart();

        services.AddScoped<IDocumentSegmentationService, DocumentSegmentationService>();
        services.AddScoped<ISentenceSegmenter, AraSegSentenceSegmenter>();
        services.AddHttpClient<IAraSegClient, AraSegHttpClient>((sp, client) =>
        {
            var options = sp.GetRequiredService<IOptions<AraSegOptions>>().Value;
            client.BaseAddress = new Uri(options.BaseUrl.TrimEnd('/') + "/", UriKind.Absolute);
            client.Timeout = TimeSpan.FromSeconds(options.TimeoutSeconds);
        });

        return services;
    }
}
