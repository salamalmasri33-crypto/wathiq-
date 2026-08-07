using System;
using System.Threading;
using System.Threading.Tasks;
using eArchiveSystem.Application.Segmentation.Abstractions;
using eArchiveSystem.Application.Segmentation.Models;
using eArchiveSystem.Infrastructure.Configuration;
using Microsoft.Extensions.Options;

namespace eArchiveSystem.Infrastructure.AI.Segmentation
{
    public sealed class AraSegSentenceSegmenter : ISentenceSegmenter
    {
        private readonly IAraSegClient _araSegClient;
        private readonly AraSegOptions _options;

        /// <summary>
        /// Initializes a new instance of the <see cref="AraSegSentenceSegmenter"/> class.
        /// </summary>
        public AraSegSentenceSegmenter(IAraSegClient araSegClient, IOptions<AraSegOptions> options)
        {
            _araSegClient = araSegClient ?? throw new ArgumentNullException(nameof(araSegClient));
            _options = options?.Value ?? throw new ArgumentNullException(nameof(options));
        }

        /// <inheritdoc />
        public Task<SegmentationResult> SegmentAsync(
            string documentId,
            string text,
            SegmentationOptions options,
            CancellationToken cancellationToken = default)
        {
            if (documentId is null)
            {
                throw new ArgumentNullException(nameof(documentId));
            }

            if (text is null)
            {
                throw new ArgumentNullException(nameof(text));
            }

            if (options is null)
            {
                throw new ArgumentNullException(nameof(options));
            }

            var track = string.IsNullOrWhiteSpace(options.Track)
                ? _options.Track
                : options.Track;

            return _araSegClient.SegmentAsync(documentId, text, track, cancellationToken);
        }
    }
}
