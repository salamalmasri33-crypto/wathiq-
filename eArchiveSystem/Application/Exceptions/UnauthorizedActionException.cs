using System.Net;

namespace eArchiveSystem.Application.Exceptions
{
    public class UnauthorizedActionException : ApiException
    {
        public UnauthorizedActionException(string message)
            : base(message, HttpStatusCode.Forbidden)
        {
        }
    }
}
