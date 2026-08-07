import api from "@/config/api";
import type { AuditLog } from "@/types/platform";

export async function getAuditLogsRequest(): Promise<AuditLog[]> {
  const response = await api.get<AuditLog[]>("/audit");
  return response.data;
}
