import api from "@/config/api";

export async function getDashboardTotalsRequest(): Promise<unknown> {
  const response = await api.get("/dashboard/totals");
  return response.data;
}

export async function getDashboardDocumentsByDepartmentRequest(): Promise<unknown> {
  const response = await api.get("/dashboard/documents-by-department");
  return response.data;
}

export async function getDashboardDocumentsByTypeRequest(): Promise<unknown> {
  const response = await api.get("/dashboard/documents-by-type");
  return response.data;
}
