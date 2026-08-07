import api from "@/config/api";
import type { InstitutionSettings, UpdateInstitutionSettingsDto } from "@/types/platform";

export async function getInstitutionSettingsRequest(
  institutionId?: string,
): Promise<InstitutionSettings> {
  const response = await api.get<InstitutionSettings>("/institution-settings", {
    params: { institutionId },
  });
  return response.data;
}

export async function updateInstitutionSettingsRequest(
  payload: UpdateInstitutionSettingsDto,
): Promise<unknown> {
  const response = await api.put("/institution-settings", payload);
  return response.data;
}
