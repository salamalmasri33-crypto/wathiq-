using eArchiveSystem.Application.DTOs;
using eArchiveSystem.Application.Segmentation.Models;
using eArchiveSystem.Domain.Models;

namespace eArchiveSystem.Application.Segmentation.Mappers
{
    public static class DocumentSegmentationMapper
    {
        public static DocumentSegmentationDto ToDto(DocumentSegmentation segmentation)
        {
            ArgumentNullException.ThrowIfNull(segmentation);

            var sentences = new List<DocumentSentenceDto>();
            if (segmentation.Sentences != null)
            {
                foreach (var sentence in segmentation.Sentences)
                {
                    sentences.Add(new DocumentSentenceDto
                    {
                        Index = sentence.Index,
                        Text = sentence.Text,
                        StartToken = sentence.StartToken,
                        EndToken = sentence.EndToken
                    });
                }
            }

            return new DocumentSegmentationDto
            {
                DocumentId = segmentation.DocumentId,
                Status = segmentation.Status,
                Provider = segmentation.Provider,
                Track = segmentation.Track,
                PipelineId = segmentation.PipelineId,
                NormalizedText = segmentation.NormalizedText,
                Sentences = sentences,
                ErrorCode = segmentation.ErrorCode,
                ErrorMessage = segmentation.ErrorMessage,
                CreatedAt = EnsureUtc(segmentation.CreatedAt),
                UpdatedAt = EnsureUtc(segmentation.UpdatedAt),
                CompletedAt = segmentation.CompletedAt.HasValue
                    ? EnsureUtc(segmentation.CompletedAt.Value)
                    : null
            };
        }

        public static DocumentSegmentation ToCompleted(
            SegmentationResult result,
            DateTime completedAtUtc)
        {
            ArgumentNullException.ThrowIfNull(result);
            ArgumentException.ThrowIfNullOrWhiteSpace(result.DocumentId);
            ArgumentException.ThrowIfNullOrWhiteSpace(result.Provider);
            ArgumentException.ThrowIfNullOrWhiteSpace(result.Track);
            ArgumentException.ThrowIfNullOrWhiteSpace(result.PipelineId);

            if (!string.Equals(result.Status, "completed", StringComparison.OrdinalIgnoreCase))
            {
                throw new ArgumentException(
                    "Segmentation result status must be completed.",
                    nameof(result));
            }

            var timestamp = EnsureUtc(completedAtUtc);
            var sentences = new List<DocumentSentence>(result.Sentences.Count);

            foreach (var sentence in result.Sentences)
            {
                sentences.Add(new DocumentSentence
                {
                    Index = sentence.Index,
                    Text = sentence.Text,
                    StartToken = sentence.StartToken,
                    EndToken = sentence.EndToken
                });
            }

            return new DocumentSegmentation
            {
                DocumentId = result.DocumentId,
                Status = SegmentationStatus.Completed,
                Provider = result.Provider,
                Track = result.Track,
                PipelineId = result.PipelineId,
                NormalizedText = result.NormalizedText,
                Sentences = sentences,
                ErrorCode = null,
                ErrorMessage = null,
                CreatedAt = timestamp,
                UpdatedAt = timestamp,
                CompletedAt = timestamp
            };
        }

        private static DateTime EnsureUtc(DateTime value)
        {
            return value.Kind switch
            {
                DateTimeKind.Utc => value,
                DateTimeKind.Local => value.ToUniversalTime(),
                _ => DateTime.SpecifyKind(value, DateTimeKind.Utc)
            };
        }
    }
}
