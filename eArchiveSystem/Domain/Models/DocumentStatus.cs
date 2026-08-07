namespace eArchiveSystem.Domain.Models
{
    public enum DocumentStatus
    {
        Draft,        // Editable by the owner.
        Processing,   // Waiting for OCR or background processing.
        Submitted,    // Submitted for review.
        UnderReview,  // Review has started.
        Approved,     // Approved and ready to publish.
        Rejected,     // Rejected and can be edited again.
        Published,    // Published for general access.
        Archived      // Archived for long-term storage.
    }
}
