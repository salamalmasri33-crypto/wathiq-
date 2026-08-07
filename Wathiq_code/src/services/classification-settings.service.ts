import api from "@/config/api";
import axios from "axios";
import type { BroadCategory, ClassificationExample, ClassificationPayload, ClassificationStatus, DeletionImpact, InstitutionTaxonomyOptions } from "@/types/classification";

type ObjectMap = Record<string, unknown>;
const isObject = (value: unknown): value is ObjectMap => typeof value === "object" && value !== null && !Array.isArray(value);
const stringValue = (value: unknown, ...keys: string[]): string => {
  if (!isObject(value)) return "";
  for (const key of keys) if (typeof value[key] === "string") return value[key] as string;
  return "";
};
const boolValue = (value: unknown, fallback = true): boolean => isObject(value) && typeof value.isActive === "boolean" ? value.isActive : isObject(value) && typeof value.is_active === "boolean" ? value.is_active : fallback;
const arrayValue = (value: unknown, ...keys: string[]): unknown[] => {
  if (!isObject(value)) return [];
  for (const key of keys) if (Array.isArray(value[key])) return value[key] as unknown[];
  return [];
};
const query = (institutionId?: string) => institutionId ? { institutionId } : undefined;
const numberValue = (value: unknown, ...keys: string[]): number => {
  if (!isObject(value)) return 0;
  for (const key of keys) if (typeof value[key] === "number") return value[key] as number;
  return 0;
};

function emptyStatus(institutionId?: string): ClassificationStatus {
  return {
    institutionId: institutionId ?? "",
    indexReady: false,
    isRebuilding: false,
    statistics: { broadCategories: 0, specificTypes: 0, examples: 0, embeddings: 0 },
    lastUpdated: null,
    lastError: null,
  };
}

function statusFrom(value: unknown, institutionId?: string): ClassificationStatus {
  if (!isObject(value)) return emptyStatus(institutionId);
  const statistics = isObject(value.statistics) ? value.statistics : {};
  return {
    institutionId: stringValue(value, "institutionId", "institution_id") || institutionId || "",
    indexReady: boolValue({ isActive: value.indexReady ?? value.index_ready }, false),
    isRebuilding: boolValue({ isActive: value.isRebuilding ?? value.is_rebuilding }, false),
    statistics: {
      broadCategories: numberValue(statistics, "broadCategories", "broad_categories"),
      specificTypes: numberValue(statistics, "specificTypes", "specific_types"),
      examples: numberValue(statistics, "examples"),
      embeddings: numberValue(statistics, "embeddings"),
    },
    lastUpdated: stringValue(value, "lastUpdated", "last_updated") || null,
    lastError: stringValue(value, "lastError", "last_error") || null,
  };
}

function example(value: unknown, specificId: string): ClassificationExample {
  return { id: stringValue(value, "id", "exampleId", "example_id"), specificId, text: stringValue(value, "text", "example") };
}
function taxonomyFrom(value: unknown): BroadCategory[] {
  const root = isObject(value) && "data" in value ? value.data : value;
  const broadItems = Array.isArray(root) ? root : arrayValue(root, "broadCategories", "broad_categories", "broadGenres", "broad_genres", "items");
  return broadItems.map((b): BroadCategory => {
    const id = stringValue(b, "id", "broadGenre", "broad_genre", "broadCategory", "broad_category");
    const specifics = arrayValue(b, "specificTypes", "specific_types", "specificGenres", "specific_genres");
    return {
      id,
      nameAr: stringValue(b, "nameAr", "name_ar") || id,
      nameEn: stringValue(b, "nameEn", "name_en") || id,
      definitionAr: stringValue(b, "definitionAr", "definition_ar"),
      definitionEn: stringValue(b, "definitionEn", "definition_en"),
      isActive: boolValue(b),
      specificTypes: specifics.map((s) => {
        const specificId = stringValue(s, "id", "specificGenre", "specific_genre", "specificType", "specific_type");
        return { id: specificId, broadId: id, nameAr: stringValue(s, "nameAr", "name_ar") || specificId, nameEn: stringValue(s, "nameEn", "name_en") || specificId, definitionAr: stringValue(s, "definitionAr", "definition_ar"), definitionEn: stringValue(s, "definitionEn", "definition_en"), isActive: boolValue(s), examples: arrayValue(s, "examples").map((e) => example(e, specificId)) };
      }),
    };
  });
}

export async function getClassificationStatus(institutionId?: string): Promise<ClassificationStatus> {
  try {
    return statusFrom((await api.get("/institution-classification/status", { params: query(institutionId) })).data, institutionId);
  } catch (error) {
    if (axios.isAxiosError(error) && error.response?.status === 404) return emptyStatus(institutionId);
    throw error;
  }
}
export async function getClassificationTaxonomy(institutionId?: string): Promise<BroadCategory[]> {
  const [taxonomyResponse, examplesResponse] = await Promise.all([
    api.get("/institution-classification/taxonomy", { params: query(institutionId) }),
    api.get("/institution-classification/examples", { params: query(institutionId) }),
  ]);
  const taxonomy = taxonomyFrom(taxonomyResponse.data);
  const examples = arrayValue(examplesResponse.data, "examples").map((value) => ({
    id: stringValue(value, "id", "exampleId", "example_id"),
    specificId: stringValue(value, "specificId", "specific_id"),
    text: stringValue(value, "text", "example"),
  }));
  const bySpecific = new Map<string, ClassificationExample[]>();
  for (const item of examples) bySpecific.set(item.specificId, [...(bySpecific.get(item.specificId) ?? []), item]);
  return taxonomy.map((broad) => ({
    ...broad,
    specificTypes: broad.specificTypes.map((specific) => ({ ...specific, examples: bySpecific.get(specific.id) ?? [] })),
  }));
}
export async function getTaxonomyOptions(institutionId?: string): Promise<InstitutionTaxonomyOptions> {
  const response = await api.get("/institution-classification/taxonomy-options", { params: query(institutionId) });
  const broadCategories = taxonomyFrom(response.data).filter((b) => b.isActive).map((b) => ({ id: b.id, nameAr: b.nameAr, nameEn: b.nameEn, isActive: b.isActive, specificTypes: b.specificTypes.filter((s) => s.isActive).map(({ id, nameAr, nameEn, isActive }) => ({ id, nameAr, nameEn, isActive })) }));
  return { institutionId: stringValue(response.data, "institutionId", "institution_id") || institutionId || "", broadCategories };
}
export async function saveBroadCategory(id: string, p: ClassificationPayload, originalId?: string) { const body = { id: p.id, name_ar: p.nameAr, name_en: p.nameEn, definition_ar: p.definitionAr, definition_en: p.definitionEn, is_active: p.isActive }; await (originalId ? api.patch(`/institution-classification/broad/${encodeURIComponent(originalId)}`, body, { params: query(id) }) : api.post("/institution-classification/broad", body, { params: query(id) })); }
export async function saveSpecificType(id: string, p: ClassificationPayload, originalId?: string) { const body = { id: p.id, broad_id: p.broadId, name_ar: p.nameAr, name_en: p.nameEn, definition_ar: p.definitionAr, definition_en: p.definitionEn, is_active: p.isActive }; await (originalId ? api.patch(`/institution-classification/specific/${encodeURIComponent(originalId)}`, body, { params: query(id) }) : api.post("/institution-classification/specific", body, { params: query(id) })); }
export async function setClassificationActive(id: string, type: "broad" | "specific", entityId: string, active: boolean) { await api.patch(`/institution-classification/${type}/${encodeURIComponent(entityId)}`, { is_active: active }, { params: query(id) }); }
export async function getDeletionImpact(id: string, type: "broad" | "specific", entityId: string): Promise<DeletionImpact> { return (await api.get(`/institution-classification/${type}/${encodeURIComponent(entityId)}/deletion-impact`, { params: query(id) })).data; }
export async function deleteClassification(id: string, type: "broad" | "specific" | "example", entityId: string) { const path = type === "example" ? "examples" : type; await api.delete(`/institution-classification/${path}/${encodeURIComponent(entityId)}`, { params: { ...query(id), ...(type === "example" ? {} : { cascade: true }) } }); }
export async function saveClassificationExample(id: string, specificId: string, text: string, exampleId?: string) { const body = { specific_id: specificId, text }; await (exampleId ? api.patch(`/institution-classification/examples/${encodeURIComponent(exampleId)}`, body, { params: query(id) }) : api.post("/institution-classification/examples", body, { params: query(id) })); }
export async function replaceTaxonomyMock(id: string, data: unknown) { await api.put("/institution-classification/taxonomy", data, { params: query(id) }); }
export async function rebuildClassifierMock(id: string): Promise<ClassificationStatus> { await api.post("/institution-classification/rebuild-index", {}, { params: query(id) }); return getClassificationStatus(id); }
