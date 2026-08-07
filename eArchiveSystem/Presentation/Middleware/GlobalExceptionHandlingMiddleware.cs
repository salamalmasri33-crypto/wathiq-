using System.Net;
using System.Text.Json;
using eArchiveSystem.Application.Exceptions;
using eArchiveSystem.Application.Interfaces.Services;
using Microsoft.Extensions.DependencyInjection;
using System.Security.Claims;

namespace eArchiveSystem.Presentation.Middleware
{
    public class GlobalExceptionHandlingMiddleware
    {
        private static readonly JsonSerializerOptions JsonOptions = new(JsonSerializerDefaults.Web);

        private readonly RequestDelegate _next;
        private readonly ILogger<GlobalExceptionHandlingMiddleware> _logger; 

        public GlobalExceptionHandlingMiddleware(
            RequestDelegate next,
            ILogger<GlobalExceptionHandlingMiddleware> logger)
        {
            _next = next;
            _logger = logger;
        }

        public async Task InvokeAsync(HttpContext context)
        {
            try
            {
                await _next(context);
            }
            catch (Exception exception)
            {
                await HandleExceptionAsync(context, exception);
            }
        }

        private async Task HandleExceptionAsync(HttpContext context, Exception exception)
        {
            if (exception is UnauthorizedActionException unauthorizedActionException)
            {
                await LogUnauthorizedAttemptAsync(context, unauthorizedActionException);
                _logger.LogWarning(
                    unauthorizedActionException,
                    "Unauthorized action blocked for request {Path}",
                    context.Request.Path);
            }
            else
            {
            _logger.LogError(exception, "Unhandled exception while processing request {Path}", context.Request.Path);
            }

            var statusCode = exception switch
            {
                ApiException apiException => (int)apiException.StatusCode,
                _ => (int)HttpStatusCode.InternalServerError
            };

            var response = new
            {
                message = exception is ApiException ? exception.Message : "An unexpected error occurred.",
                statusCode,
                traceId = context.TraceIdentifier
            };

            context.Response.StatusCode = statusCode;
            context.Response.ContentType = "application/json";

            await context.Response.WriteAsync(JsonSerializer.Serialize(response, JsonOptions));
        }

        private static async Task LogUnauthorizedAttemptAsync(HttpContext context, UnauthorizedActionException exception)
        {
            var audit = context.RequestServices.GetService<IAuditService>();
            if (audit == null)
                return;

            var userId = context.User.FindFirst(ClaimTypes.NameIdentifier)?.Value
                ?? context.User.FindFirst("sub")?.Value
                ?? "ANONYMOUS";

            var role = context.User.FindFirst(ClaimTypes.Role)?.Value
                ?? "Anonymous";

            var documentId = context.Request.RouteValues.TryGetValue("id", out var idValue)
                ? idValue?.ToString()
                : context.Request.RouteValues.TryGetValue("documentId", out var documentIdValue)
                    ? documentIdValue?.ToString()
                    : null;

            await audit.LogAsync(
                userId,
                role,
                "UnauthorizedAccessAttempt",
                documentId,
                $"Blocked action on {context.Request.Method} {context.Request.Path}: {exception.Message}");
        }
    }
}
