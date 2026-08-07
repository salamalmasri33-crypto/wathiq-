using eArchiveSystem.Application.Interfaces.Services;
using Microsoft.AspNetCore.Authorization.Policy;
using Microsoft.AspNetCore.Authorization;
using Microsoft.Extensions.DependencyInjection;
using System.Security.Claims;

namespace eArchiveSystem.Presentation.Middleware
{
    public class AuthorizationAuditResultHandler : Microsoft.AspNetCore.Authorization.IAuthorizationMiddlewareResultHandler
    {
        private readonly AuthorizationMiddlewareResultHandler _defaultHandler = new();
        private readonly ILogger<AuthorizationAuditResultHandler> _logger;

        public AuthorizationAuditResultHandler(ILogger<AuthorizationAuditResultHandler> logger)
        {
            _logger = logger;
        }

        public async Task HandleAsync(
            RequestDelegate next,
            HttpContext context,
            AuthorizationPolicy policy,
            PolicyAuthorizationResult authorizeResult)
        {
            if (authorizeResult.Forbidden || authorizeResult.Challenged)
            {
                await LogAuthorizationFailureAsync(context, authorizeResult);
            }

            await _defaultHandler.HandleAsync(next, context, policy, authorizeResult);
        }

        private async Task LogAuthorizationFailureAsync(HttpContext context, PolicyAuthorizationResult authorizeResult)
        {
            try
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

                var action = authorizeResult.Forbidden
                    ? "UnauthorizedAccessAttempt"
                    : "AuthenticationRequired";

                var description = authorizeResult.Forbidden
                    ? $"Forbidden access attempt to {context.Request.Method} {context.Request.Path}"
                    : $"Unauthenticated access attempt to {context.Request.Method} {context.Request.Path}";

                await audit.LogAsync(userId, role, action, documentId, description);
            }
            catch (Exception exception)
            {
                _logger.LogWarning(
                    exception,
                    "Failed to audit authorization failure for request {Method} {Path}",
                    context.Request.Method,
                    context.Request.Path);
            }
        }
    }
}
