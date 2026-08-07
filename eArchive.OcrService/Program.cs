using eArchive.OcrService.Configuration;
using eArchive.OcrService.OCR;
using eArchive.OcrService.Services;
using MongoDB.Driver;

AppDomain.CurrentDomain.UnhandledException += (_, eventArgs) =>
{
    Console.ForegroundColor = ConsoleColor.Red;
    Console.WriteLine(" FATAL ERROR:");
    Console.WriteLine(eventArgs.ExceptionObject);
    Console.ResetColor();
};

var builder = WebApplication.CreateBuilder(args);

builder.Configuration.AddJsonFile("appsettings.Development.local.json", optional: true, reloadOnChange: true);

builder.Services.AddControllers();
builder.Services.AddEndpointsApiExplorer();
builder.Services.AddSwaggerGen();

builder.Services.Configure<GroqOptions>(builder.Configuration.GetSection("Groq"));
builder.Services.Configure<ImagePreprocessingOptions>(builder.Configuration.GetSection("ImagePreprocessing"));

builder.Services
    .AddHttpClient("callback")
    .ConfigurePrimaryHttpMessageHandler(() =>
        new HttpClientHandler
        {
            ServerCertificateCustomValidationCallback =
                HttpClientHandler.DangerousAcceptAnyServerCertificateValidator
        });

builder.Services.AddHttpClient("groq");

builder.Services.AddScoped<GroqVisionOcrStrategy>();
builder.Services.AddScoped<IGroqOcrPromptBuilder, GroqOcrPromptBuilder>();
builder.Services.AddScoped<IOcrStrategy, GroqVisionOcrStrategy>();
builder.Services.AddScoped<IWorkingFilePreparationService, SafeWorkingFilePreparationService>();
builder.Services.AddScoped<IPdfTextExtractionService, PdfTextExtractionService>();
builder.Services.AddScoped<IPdfToImageService, PdfToImageService>();
builder.Services.AddScoped<IDocumentImageResolver, DocumentImageResolver>();
builder.Services.AddScoped<IImagePreprocessingService, DenoiseImagePreprocessingService>();
builder.Services.AddScoped<INumericValidationService, NumericValidationService>();
builder.Services.AddScoped<OcrProcessor>();

builder.Services.AddSingleton<IMongoClient>(_ =>
{
    var connectionString = builder.Configuration["Mongo:ConnectionString"];
    return new MongoClient(connectionString);
});

builder.Services.AddSingleton<IMongoDatabase>(serviceProvider =>
{
    var client = serviceProvider.GetRequiredService<IMongoClient>();
    return client.GetDatabase("eArchive");
});

var app = builder.Build();

if (app.Environment.IsDevelopment())
{
    app.UseSwagger();
    app.UseSwaggerUI();
}

var enableHttpsRedirection = !app.Environment.IsDevelopment()
    || builder.Configuration.GetValue<bool>("UseHttpsRedirection");

if (enableHttpsRedirection)
{
    app.UseHttpsRedirection();
}

app.UseAuthorization();
app.MapControllers();

Console.WriteLine("✅ OCR SERVICE STARTED AND LISTENING...");

app.Run();
