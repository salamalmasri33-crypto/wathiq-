import api from "@/config/api";
import type { Department, DepartmentTreeNode } from "@/types/platform";

export type AddDepartmentDto = {
  name: string;
  institutionId?: string | null;
  parentDepartmentId?: string | null;
};

export type UpdateDepartmentDto = {
  name: string;
  parentDepartmentId?: string | null;
};

export async function getDepartmentsRequest(institutionId?: string): Promise<Department[]> {
  const response = await api.get<Department[]>("/departments", {
    params: { institutionId },
  });
  return response.data;
}

export async function getDepartmentTreeRequest(institutionId?: string): Promise<DepartmentTreeNode[]> {
  const response = await api.get<DepartmentTreeNode[]>("/departments/tree", {
    params: { institutionId },
  });
  return response.data;
}

export async function getDepartmentByIdRequest(departmentId: string): Promise<Department> {
  const response = await api.get<Department>(`/departments/${departmentId}`);
  return response.data;
}

export async function addDepartmentRequest(payload: AddDepartmentDto): Promise<unknown> {
  const response = await api.post("/departments", payload);
  return response.data;
}

export async function updateDepartmentRequest(
  departmentId: string,
  payload: UpdateDepartmentDto,
): Promise<unknown> {
  const response = await api.put(`/departments/${departmentId}`, payload);
  return response.data;
}

export async function deleteDepartmentRequest(departmentId: string): Promise<unknown> {
  const response = await api.delete(`/departments/${departmentId}`);
  return response.data;
}
