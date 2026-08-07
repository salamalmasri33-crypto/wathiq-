import api from "@/config/api";
import type { ReviewDecisionDto, TransferDocumentDto } from "@/types/dto";

export async function submitDocumentRequest(documentId: string): Promise<unknown> {
  const response = await api.post(`/documents/${documentId}/workflow/submit`);
  return response.data;
}

export async function startReviewRequest(documentId: string): Promise<unknown> {
  const response = await api.post(`/documents/${documentId}/workflow/start-review`);
  return response.data;
}

export async function approveDocumentRequest(
  documentId: string,
  payload?: ReviewDecisionDto,
): Promise<unknown> {
  const response = await api.post(`/documents/${documentId}/workflow/approve`, payload ?? {});
  return response.data;
}

export async function rejectDocumentRequest(
  documentId: string,
  payload: ReviewDecisionDto,
): Promise<unknown> {
  const response = await api.post(`/documents/${documentId}/workflow/reject`, payload);
  return response.data;
}

export async function publishDocumentRequest(documentId: string): Promise<unknown> {
  const response = await api.post(`/documents/${documentId}/workflow/publish`);
  return response.data;
}

export async function archiveDocumentRequest(documentId: string): Promise<unknown> {
  const response = await api.post(`/documents/${documentId}/workflow/archive`);
  return response.data;
}

export async function transferDocumentRequest(
  documentId: string,
  payload: TransferDocumentDto,
): Promise<unknown> {
  const response = await api.post(`/documents/${documentId}/workflow/transfer`, payload);
  return response.data;
}
