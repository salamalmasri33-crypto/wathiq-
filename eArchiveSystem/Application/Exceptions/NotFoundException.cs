using System.Net;

namespace eArchiveSystem.Application.Exceptions
{
    public class NotFoundException : ApiException
    {
        public NotFoundException(string message)
            : base(message, HttpStatusCode.NotFound)
        {
        }
    }
}
 