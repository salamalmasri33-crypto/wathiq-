# Wathiq Backend deployment notes

The backend runs the idempotent MongoDB migration
`20260804_replace_metadata_category_with_genres_v1` during startup. It removes
the legacy document-classification field without changing existing
`BroadGenre` or `SpecificGenre` values. A migration failure stops startup.

After deployment, a SystemAdmin must recreate the Elasticsearch index once:

```http
POST /api/indexing/reindex?recreateIndex=true
```

This creates `broadGenre` and `specificGenre` as `keyword` fields and reindexes
all MongoDB documents. Elasticsearch recreation is intentionally not performed
at startup.
