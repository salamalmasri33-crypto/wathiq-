using System.Reflection;
using System.Security.Claims;
using eArchiveSystem.Application.DTOs;
using eArchiveSystem.Application.Segmentation.Abstractions;
using eArchiveSystem.Domain.Models;
using eArchiveSystem.Presentation.Controllers;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Mvc;

namespace eArchiveSystem.Tests;

public sealed class DocumentSegmentationControllerTests
{
    [Fact]
    public void Segmentation_endpoints_have_expected_authorize_roles_and_routes()
    {
        var getMethod = typeof(DocumentSegmentationController).GetMethod(nameof(DocumentSegmentationController.GetSegmentation))!;
        var startMethod = typeof(DocumentSegmentationController).GetMethod(nameof(DocumentSegmentationController.StartSegmentation))!;
        var retryMethod = typeof(DocumentSegmentationController).GetMethod(nameof(DocumentSegmentationController.RetrySegmentation))!;

        Assert.Equal("SystemAdmin,InstitutionAdmin,Manager,Employee", getMethod.GetCustomAttribute<AuthorizeAttribute>()!.Roles);
        Assert.Equal("Manager,Employee", startMethod.GetCustomAttribute<AuthorizeAttribute>()!.Roles);
        Assert.Equal("Manager,Employee", retryMethod.GetCustomAttribute<AuthorizeAttribute>()!.Roles);
        Assert.NotNull(getMethod.GetCustomAttribute<HttpGetAttribute>());
        Assert.NotNull(startMethod.GetCustomAttribute<HttpPostAttribute>());
        Assert.Equal("retry", retryMethod.GetCustomAttribute<HttpPostAttribute>()!.Template);
    }

    [Fact]
    public async Task GetSegmentation_returns_backend_owned_dto()
    {
        var dto = CreateDto();
        var controller = CreateController(new StubDocumentSegmentationService
        {
            GetResult = dto
        });

        var result = await controller.GetSegmentation("doc-123", CancellationToken.None);

        var ok = Assert.IsType<OkObjectResult>(result);
        Assert.Same(dto, ok.Value);
    }

    [Fact]
    public async Task StartSegmentation_returns_backend_owned_dto()
    {
        var dto = CreateDto();
        var controller = CreateController(new StubDocumentSegmentationService
        {
            StartResult = dto
        });

        var result = await controller.StartSegmentation("doc-123", CancellationToken.None);

        var ok = Assert.IsType<OkObjectResult>(result);
        Assert.Same(dto, ok.Value);
    }

    [Fact]
    public async Task RetrySegmentation_returns_backend_owned_dto()
    {
        var dto = CreateDto();
        var controller = CreateController(new StubDocumentSegmentationService
        {
            RetryResult = dto
        });

        var result = await controller.RetrySegmentation("doc-123", CancellationToken.None);

        var ok = Assert.IsType<OkObjectResult>(result);
        Assert.Same(dto, ok.Value);
    }

    [Fact]
    public async Task Missing_user_claim_returns_unauthorized()
    {
        var controller = new DocumentSegmentationController(new StubDocumentSegmentationService())
        {
            ControllerContext = new ControllerContext
            {
                HttpContext = new DefaultHttpContext()
            }
        };

        var result = await controller.StartSegmentation("doc-123", CancellationToken.None);

        Assert.IsType<UnauthorizedResult>(result);
    }

    private static DocumentSegmentationController CreateController(IDocumentSegmentationService service)
    {
        var controller = new DocumentSegmentationController(service);
        var identity = new ClaimsIdentity(
            new[]
            {
                new Claim(ClaimTypes.NameIdentifier, "user-1"),
                new Claim(ClaimTypes.Role, "Employee")
            },
            "TestAuth");

        controller.ControllerContext = new ControllerContext
        {
            HttpContext = new DefaultHttpContext
            {
                User = new ClaimsPrincipal(identity)
            }
        };

        return controller;
    }

    private static DocumentSegmentationDto CreateDto()
    {
        return new DocumentSegmentationDto
        {
            DocumentId = "doc-123",
            Status = SegmentationStatus.Completed,
            Provider = "AraSeg",
            Track = "PA",
            PipelineId = "pa-current-1",
            NormalizedText = "  النص\t\n",
            Sentences = new List<DocumentSentenceDto>
            {
                new()
                {
                    Index = 0,
                    Text = "  النص\t\n",
                    StartToken = 0,
                    EndToken = 5
                }
            }
        };
    }

    private sealed class StubDocumentSegmentationService : IDocumentSegmentationService
    {
        public DocumentSegmentationDto GetResult { get; set; } = CreateDto();
        public DocumentSegmentationDto StartResult { get; set; } = CreateDto();
        public DocumentSegmentationDto RetryResult { get; set; } = CreateDto();

        public Task<DocumentSegmentationDto> GetSegmentationAsync(string documentId, string userId, CancellationToken cancellationToken = default) =>
            Task.FromResult(GetResult);

        public Task<DocumentSegmentationDto> SegmentDocumentAsync(string documentId, string userId, CancellationToken cancellationToken = default) =>
            Task.FromResult(StartResult);

        public Task<DocumentSegmentationDto> RetrySegmentationAsync(string documentId, string userId, CancellationToken cancellationToken = default) =>
            Task.FromResult(RetryResult);

        public Task ProcessStoredDocumentAsync(string documentId, CancellationToken cancellationToken = default) =>
            Task.CompletedTask;
    }
}
