import api from "@/config/api";

export async function reindexAllDocumentsRequest(recreateIndex = false): Promise<unknown> {
  const response = await api.post("/indexing/reindex", null, {
    params: { recreateIndex },
  });
  return response.data;
}
