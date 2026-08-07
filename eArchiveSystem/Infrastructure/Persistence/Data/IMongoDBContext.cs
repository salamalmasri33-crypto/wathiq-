using MongoDB.Driver;

namespace eArchiveSystem.Infrastructure.Persistence.Data
{
    public interface IMongoDBContext
    {
        IMongoDatabase GetDatabase();
    }
}

