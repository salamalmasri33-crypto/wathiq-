using eArchiveSystem.Application.Interfaces.Persistence;
using eArchiveSystem.Application.Interfaces.Security;
using eArchiveSystem.Application.Interfaces.Services;
using eArchiveSystem.Application.Services;
using eArchiveSystem.Infrastructure.Persistence.Data;
using eArchiveSystem.Infrastructure.Persistence.Repositories;
using eArchiveSystem.Infrastructure.Security;
using eArchiveSystem.Presentation.Middleware;
using Microsoft.AspNetCore.Authentication.JwtBearer;
using Microsoft.AspNetCore.DataProtection;
using Microsoft.AspNetCore.Http.Features;
using Microsoft.AspNetCore.Authorization.Policy;
using Microsoft.Extensions.Options;
using Microsoft.IdentityModel.Tokens;
using MongoDB.Driver;
using QuestPDF.Infrastructure;
using System.Text;
using eArchiveSystem.Application.Segmentation.Abstractions;
using eArchiveSystem.Application.Segmentation.Services;
using eArchiveSystem.Infrastructure.AI.Clients;
using eArchiveSystem.Infrastructure.AI.Segmentation;
using eArchiveSystem.Infrastructure.Configuration;
using eArchiveSystem.Infrastructure.Persistence.Migrations;

var builder = WebApplication.CreateBuilder(args);

builder.Configuration.AddJsonFile(
    "appsettings.Development.local.json",
    optional: true,
    reloadOnChange: true);

// Keep startup logging portable and avoid Windows Event Log permission issues
// during local development and CLI-based runs.
builder.Logging.ClearProviders();
builder.Logging.AddConsole();
builder.Logging.AddDebug();

var dataProtectionBuilder = builder.Services
    .AddDataProtection() 
    .SetApplicationName("eArchiveSystem");

if (builder.Environment.IsDevelopment())
{
    var localDataProtectionKeyPath = Path.Combine(
        builder.Environment.ContentRootPath,
        ".local",
        "data-protection-keys");

    Directory.CreateDirectory(localDataProtectionKeyPath);
    dataProtectionBuilder.PersistKeysToFileSystem(new DirectoryInfo(localDataProtectionKeyPath));
}

builder.Services.AddControllers();
builder.Services.AddEndpointsApiExplorer();
builder.Services.AddSwaggerGen();

builder.Services.Configure<FormOptions>(options =>
{
    options.MultipartBodyLengthLimit = long.MaxValue; 
    options.ValueLengthLimit = int.MaxValue;
    options.MultipartHeadersLengthLimit = int.MaxValue;
});

builder.Services.Configure<MongoDBSettings>(
    builder.Configuration.GetSection("MongoDB"));

builder.Services.Configure<ElasticsearchSettings>( 
    builder.Configuration.GetSection("Elasticsearch"));

builder.Services.AddSingleton<IMongoClient>(sp =>
{
    var settings = sp.GetRequiredService<IOptions<MongoDBSettings>>().Value;
    return new MongoClient(settings.ConnectionString);
});

builder.Services.AddScoped<IMongoDatabase>(sp =>
{
    var client = sp.GetRequiredService<IMongoClient>();
    var settings = sp.GetRequiredService<IOptions<MongoDBSettings>>().Value;
    return client.GetDatabase(settings.DatabaseName);
});

builder.Services.AddScoped<IUserRepository, UserRepository>();
builder.Services.AddScoped<IDocumentRepository, DocumentRepository>();
builder.Services.AddScoped<IDocumentSegmentationRepository, DocumentSegmentationRepository>();
builder.Services.AddScoped<IMetadataRepository, MetadataRepository>();
builder.Services.AddScoped<IAuditRepository, AuditRepository>();
builder.Services.AddScoped<INotificationRepository, NotificationRepository>();
builder.Services.AddScoped<IDepartmentRepository, DepartmentRepository>();
builder.Services.AddScoped<IInstitutionSettingsRepository, InstitutionSettingsRepository>();
builder.Services.AddScoped<RemoveLegacyMetadataCategoryMigration>();

// Register the search repository used by the indexing layer.
builder.Services.AddScoped<IDocumentSearchRepository, ElasticsearchDocumentSearchRepository>();

// Allow the Elasticsearch client to work with the local development certificate.
builder.Services.AddHttpClient("ElasticClient")
    .ConfigurePrimaryHttpMessageHandler(() =>
        new HttpClientHandler
        {
            ServerCertificateCustomValidationCallback =
                HttpClientHandler.DangerousAcceptAnyServerCertificateValidator
        });

builder.Services.AddScoped<IUserService, UserService>();
builder.Services.AddScoped<IDocumentService, DocumentService>();
builder.Services.AddScoped<IEmailService, EmailService>();
builder.Services.AddScoped<ISearchService, SearchService>();
builder.Services.AddScoped<IMetadataService, MetadataService>();
builder.Services.AddScoped<IMetadataPreviewService, MetadataPreviewService>();
builder.Services.AddScoped<IDepartmentService, DepartmentService>();
builder.Services.AddScoped<IInstitutionSettingsService, InstitutionSettingsService>();
builder.Services.AddScoped<IInstitutionScopeResolver, InstitutionScopeResolver>();
builder.Services.AddScoped<IInstitutionClassificationService, InstitutionClassificationService>();
builder.Services.AddScoped<IStorageService, LocalStorageService>();
builder.Services.AddScoped<IPdfTextExtractor, eArchiveSystem.Infrastructure.Documents.PdfTextExtractor>();

builder.Services.AddAraSegSegmentation(builder.Configuration);

builder.Services.Configure<AraGenreOptions>(
    builder.Configuration.GetSection("AraGenre"));
builder.Services.AddHttpClient<eArchiveSystem.Application.Classification.Abstractions.IAraGenreClient, AraGenreHttpClient>((sp, client) =>
{
    var options = sp.GetRequiredService<IOptions<AraGenreOptions>>().Value;
    client.BaseAddress = new Uri(options.BaseUrl.TrimEnd('/') + "/");
    client.Timeout = TimeSpan.FromSeconds(options.TimeoutSeconds > 0 ? options.TimeoutSeconds : 120);
});

builder.Services.AddScoped<IDocumentWatermarkService, DocumentWatermarkService>();
builder.Services.AddScoped<IAuditService, AuditService>();
builder.Services.AddScoped<INotificationService, NotificationService>();
builder.Services.AddScoped<IReportService, ReportService>();
builder.Services.AddScoped<IDashboardService, DashboardService>();
builder.Services.AddScoped<IRuleBasedAnalyzer, RuleBasedAnalyzer>();
builder.Services.AddScoped<ITextPreprocessorService, TextPreprocessorService>();
builder.Services.AddScoped<IOcrExtractionAssessmentService, OcrExtractionAssessmentService>();
builder.Services.AddScoped<IIndexingService, IndexingService>();
builder.Services.AddScoped<IDocumentAuthorizationService, DocumentAuthorizationService>();
builder.Services.AddScoped<IDocumentTimelineService, DocumentTimelineService>();
builder.Services.AddScoped<IPermissionReviewService, PermissionReviewService>();
builder.Services.AddScoped<IDocumentWorkflowService, DocumentWorkflowService>();
builder.Services.AddScoped<IAnalyticsScopeService, AnalyticsScopeService>();
builder.Services.AddSingleton<
    Microsoft.AspNetCore.Authorization.IAuthorizationMiddlewareResultHandler,
    AuthorizationAuditResultHandler>();

QuestPDF.Settings.License = LicenseType.Community;

builder.Services.AddScoped<IPasswordHasher, BCryptPasswordHasher>();
builder.Services.AddScoped<IFileHashCalculator, Sha256FileHashCalculator>();
builder.Services.AddScoped<ITokenService, JwtTokenService>();

var jwtKey = builder.Configuration["Jwt:Key"];
var issuer = builder.Configuration["Jwt:Issuer"];
var audience = builder.Configuration["Jwt:Audience"];

if (string.IsNullOrWhiteSpace(jwtKey))
{
    // Keep the API alive even when local config is incomplete.
    jwtKey = Environment.GetEnvironmentVariable("JWT__KEY");
}

if (string.IsNullOrWhiteSpace(jwtKey))
{
    jwtKey = "Wathiq_Local_Development_Key_Change_Me_2026";
}

issuer = string.IsNullOrWhiteSpace(issuer) ? "eArchiveSystem" : issuer;
audience = string.IsNullOrWhiteSpace(audience) ? "eArchiveSystemUsers" : audience;

builder.Services
    .AddAuthentication(JwtBearerDefaults.AuthenticationScheme)
    .AddJwtBearer(options =>
    {
        options.TokenValidationParameters = new TokenValidationParameters
        {
            ValidateIssuer = true,
            ValidateAudience = true,
            ValidateLifetime = true,
            ValidateIssuerSigningKey = true,
            ValidIssuer = issuer,
            ValidAudience = audience,
            IssuerSigningKey = new SymmetricSecurityKey(
                Encoding.UTF8.GetBytes(jwtKey))
        };
    });

builder.Services.AddCors(options =>
{
    options.AddPolicy("AllowFrontend", policy =>
    {
        policy.WithOrigins("http://localhost:8080")
              .AllowAnyHeader()
              .AllowAnyMethod();
    });
});

var app = builder.Build();

using (var scope = app.Services.CreateScope())
{
    var categoryMigration = scope.ServiceProvider.GetRequiredService<RemoveLegacyMetadataCategoryMigration>();
    await categoryMigration.RunAsync();

    try
    {
        var userService = scope.ServiceProvider.GetRequiredService<IUserService>();
        await userService.CreateBootstrapAdminIfNotExists();
    }
    catch (Exception ex)
    {
        app.Logger.LogWarning(ex, "Bootstrap admin seeding failed at startup. Continuing without stopping the API.");
    }
}

if (app.Environment.IsDevelopment())
{
    app.UseSwagger();
    app.UseSwaggerUI();
}

app.UseMiddleware<GlobalExceptionHandlingMiddleware>();

var enableHttpsRedirection = !app.Environment.IsDevelopment()
    || builder.Configuration.GetValue<bool>("UseHttpsRedirection");

if (enableHttpsRedirection)
{
    app.UseHttpsRedirection();
}

app.UseCors("AllowFrontend");
app.UseAuthentication();
app.UseAuthorization();

app.MapControllers();

await app.RunAsync();
