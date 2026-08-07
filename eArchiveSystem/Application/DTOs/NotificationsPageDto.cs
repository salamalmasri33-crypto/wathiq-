namespace eArchiveSystem.Application.DTOs
{
    public class NotificationsPageDto
    {
        public long Total { get; set; }
        public long UnreadCount { get; set; }
        public int Page { get; set; }
        public int PageSize { get; set; }
        public List<NotificationDto> Data { get; set; } = new();
    }
}
