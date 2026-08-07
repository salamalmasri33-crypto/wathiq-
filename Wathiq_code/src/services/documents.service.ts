import axios from "axios";
import api from "@/config/api";
import type {
  Document,
  DocumentOcrText,
  DocumentSegmentation,
  DocumentTimelineEntry,
  Metadata,
  OcrProcessingResponse,
} from "@/types/document";
import type { AddDocumentForm, SearchDocumentsDto, UpdateDocumentForm, UpsertMetadataDto } from "@/types/dto";

export async function searchDocumentsRequest(payload: SearchDocumentsDto): Promise<unknown> {
  const response = await api.post("/documents/search", payload);
  return response.data;
}

export async function addDocumentRequest(form: AddDocumentForm): Promise<unknown> {
  const data = new FormData();
  data.append("File", form.file);

  if (form.title) data.append("Title", form.title);
  if (form.targetUserId) data.append("TargetUserId", form.targetUserId);
  if (typeof form.enableOcr === "boolean") data.append("EnableOcr", String(form.enableOcr));
  if (form.priority !== undefined && form.priority !== null) data.append("Priority", String(form.priority));
  if (typeof form.isSensitive === "boolean") data.append("IsSensitive", String(form.isSensitive));

  const response = await api.post("/documents/Add", data, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return response.data;
}

export async function updateDocumentRequest(
  documentId: string,
  form: UpdateDocumentForm,
): Promise<unknown> {
  const data = new FormData();

  if (form.title) data.append("Title", form.title);
  if (form.file) data.append("File", form.file);
  if (form.priority !== undefined && form.priority !== null) data.append("Priority", String(form.priority));
  if (typeof form.isSensitive === "boolean") data.append("IsSensitive", String(form.isSensitive));

  const response = await api.put(`/documents/${documentId}`, data, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return response.data;
}

export async function getDocumentViewRequest(documentId: string): Promise<Document> {
  const response = await api.get<Document>(`/documents/${documentId}/view`);
  return response.data;
}

export async function getDocumentMetadataRequest(documentId: string): Promise<Metadata | unknown> {
  const response = await api.get<Metadata | unknown>(`/documents/${documentId}/metadata`);
  return response.data;
}

export async function getDocumentTimelineRequest(documentId: string): Promise<DocumentTimelineEntry[]> {
  const response = await api.get<DocumentTimelineEntry[]>(`/documents/${documentId}/timeline`);
  return response.data;
}

export async function addDocumentMetadataRequest(
  documentId: string,
  payload: UpsertMetadataDto,
): Promise<unknown> {
  const response = await api.post(`/documents/${documentId}/metadata`, payload);
  return response.data;
}

export async function updateDocumentMetadataRequest(
  documentId: string,
  payload: UpsertMetadataDto,
): Promise<unknown> {
  const response = await api.put(`/documents/${documentId}/metadata`, payload);
  return response.data;
}

export async function getDocumentOcrTextRequest(documentId: string): Promise<DocumentOcrText | OcrProcessingResponse> {
  const response = await api.get<DocumentOcrText | OcrProcessingResponse>(`/documents/${documentId}/ocr-text`, {
    validateStatus: (status) => status >= 200 && status < 500,
  });
  return response.data;
}

export async function deleteDocumentRequest(documentId: string): Promise<unknown> {
  const response = await api.delete(`/documents/${documentId}`, {
    validateStatus: (status) => (status >= 200 && status < 300) || status === 404,
  });
  return response.data;
}

export async function downloadDocumentRequest(documentId: string): Promise<Blob> {
  const response = await api.get(`/documents/${documentId}/download`, {
    responseType: "blob",
  });
  return response.data;
}

// M6: AraSeg sentence segmentation. Calls the .NET API only
// (DocumentSegmentationController -> DocumentSegmentationService -> AraSeg).
// React never talks to the Python AraSeg service directly.

export async function getDocumentSegmentationRequest(documentId: string): Promise<DocumentSegmentation | null> {
  try {
    const response = await api.get<DocumentSegmentation>(`/documents/${documentId}/segmentation`);
    return response.data;
  } catch (error) {
    // The backend returns 404 when segmentation has never been run for this
    // document. That is a legitimate "no segmentation yet" state, not a
    // fatal error, so it is normalized to null instead of being thrown.
    if (axios.isAxiosError(error) && error.response?.status === 404) {
      return null;
    }
    throw error;
  }
}

export async function startDocumentSegmentationRequest(documentId: string): Promise<DocumentSegmentation> {
  const response = await api.post<DocumentSegmentation>(`/documents/${documentId}/segmentation`);
  return response.data;
}

export async function retryDocumentSegmentationRequest(documentId: string): Promise<DocumentSegmentation> {
  const response = await api.post<DocumentSegmentation>(`/documents/${documentId}/segmentation/retry`);
  return response.data;
}
