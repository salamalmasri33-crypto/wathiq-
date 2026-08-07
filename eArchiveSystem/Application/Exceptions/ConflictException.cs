using System.Net;

namespace eArchiveSystem.Application.Exceptions
{
    public class ConflictException : ApiException
    {
        public ConflictException(string message)
            : base(message, HttpStatusCode.Conflict)
        {
        }
    }
}
