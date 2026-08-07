using eArchiveSystem.Application.Interfaces.Services;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;

namespace eArchiveSystem.Presentation.Controllers
{
    [ApiController]
    [Route("api/indexing")]
    [Authorize(Roles = "SystemAdmin")]
    public class IndexingController : ControllerBase
    {
        private readonly IIndexingService _indexingService;

        public IndexingController(IIndexingService indexingService)
        {
            _indexingService = indexingService;
        }

        [HttpPost("reindex")]
        public async Task<IActionResult> ReindexAll([FromQuery] bool recreateIndex = false)
        {
            await _indexingService.ReindexAllAsync(recreateIndex);

            return Ok(new
            {
                message = recreateIndex
                    ? "Index recreated and all documents reindexed successfully."
                    : "All documents reindexed successfully."
            });
        }
    }
}
