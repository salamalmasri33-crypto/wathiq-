import api from "@/config/api";

export async function getDocumentsByDepartmentReportRequest(): Promise<unknown> {
  const response = await api.get("/reports/documents-by-department");
  return response.data;
}

export async function getDocumentsByTypeReportRequest(): Promise<unknown> {
  const response = await api.get("/reports/documents-by-type");
  return response.data;
}

export async function getUserActivityReportRequest(): Promise<unknown> {
  const response = await api.get("/reports/user-activity");
  return response.data;
}

export async function getTimeReportRequest(): Promise<unknown> {
  const response = await api.get("/reports/time-report");
  return response.data;
}

export async function exportDepartmentExcelRequest(): Promise<Blob> {
  const response = await api.get("/reports/export/department/excel", { responseType: "blob" });
  return response.data;
}

export async function exportDepartmentPdfRequest(): Promise<Blob> {
  const response = await api.get("/reports/export/department/pdf", { responseType: "blob" });
  return response.data;
}

export async function exportTypeExcelRequest(): Promise<Blob> {
  const response = await api.get("/reports/export/type/excel", { responseType: "blob" });
  return response.data;
}

export async function exportTypePdfRequest(): Promise<Blob> {
  const response = await api.get("/reports/export/type/pdf", { responseType: "blob" });
  return response.data;
}

export async function exportUserActivityExcelRequest(): Promise<Blob> {
  const response = await api.get("/reports/export/user-activity/excel", { responseType: "blob" });
  return response.data;
}

export async function exportUserActivityPdfRequest(): Promise<Blob> {
  const response = await api.get("/reports/export/user-activity/pdf", { responseType: "blob" });
  return response.data;
}

export async function exportAllDocumentsExcelRequest(): Promise<Blob> {
  const response = await api.get("/reports/export/all-documents/excel", { responseType: "blob" });
  return response.data;
}
