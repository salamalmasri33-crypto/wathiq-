using System.Net;

namespace eArchiveSystem.Application.Exceptions;

public sealed class AraSegClientException : ApiException
{
    public AraSegClientException(string message, HttpStatusCode statusCode, string? errorCode = null)
        : base(message, statusCode)
    {
        ErrorCode = errorCode;
    }

    public string? ErrorCode { get; }
}
