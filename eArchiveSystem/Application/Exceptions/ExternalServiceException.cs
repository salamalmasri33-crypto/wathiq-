using System.Net;

namespace eArchiveSystem.Application.Exceptions
{
    public class ExternalServiceException : ApiException
    {
        public ExternalServiceException(string message)
            : base(message, HttpStatusCode.BadGateway)
        {
        }
    }
}
