export type ClassificationExample = { id: string; specificId: string; text: string };
export type SpecificType = { id: string; broadId: string; nameAr: string; nameEn: string; definitionAr: string; definitionEn: string; isActive: boolean; examples: ClassificationExample[] };
export type BroadCategory = { id: string; nameAr: string; nameEn: string; definitionAr: string; definitionEn: string; isActive: boolean; specificTypes: SpecificType[] };
export type ClassificationStatus = { institutionId: string; indexReady: boolean; isRebuilding: boolean; statistics: { broadCategories: number; specificTypes: number; examples: number; embeddings: number }; lastUpdated: string | null; lastError: string | null };
export type ClassificationPayload = { id: string; broadId?: string; nameAr: string; nameEn: string; definitionAr: string; definitionEn: string; isActive: boolean };
export type DeletionImpact = { entityType: "broad" | "specific" | "example"; entityId: string; requiresConfirmation: boolean; specificTypesCount: number; examplesCount: number; affectedSpecificTypes: Array<{ id: string; nameAr: string; nameEn: string }> };

export type SpecificTypeOption = { id: string; nameAr: string; nameEn: string; isActive?: boolean };
export type BroadCategoryOption = { id: string; nameAr: string; nameEn: string; isActive?: boolean; specificTypes: SpecificTypeOption[] };
export type InstitutionTaxonomyOptions = { institutionId: string; broadCategories: BroadCategoryOption[] };
