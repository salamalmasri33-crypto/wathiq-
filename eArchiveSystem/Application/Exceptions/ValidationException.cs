using System.Net;

namespace eArchiveSystem.Application.Exceptions
{
    public class ValidationException : ApiException
    {
        public ValidationException(string message)
            : base(message, HttpStatusCode.BadRequest)
        {
        }
    }
}
