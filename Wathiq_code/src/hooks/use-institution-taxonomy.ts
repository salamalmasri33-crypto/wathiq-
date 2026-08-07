import { useEffect, useMemo, useState } from "react";
import { getTaxonomyOptions } from "@/services/classification-settings.service";
import type { InstitutionTaxonomyOptions } from "@/types/classification";

const cache = new Map<string, InstitutionTaxonomyOptions>();

export function useInstitutionTaxonomy(institutionId?: string, enabled = true) {
  const key = institutionId?.trim() || "self";
  const [taxonomy, setTaxonomy] = useState<InstitutionTaxonomyOptions | null>(() => cache.get(key) ?? null);
  const [loading, setLoading] = useState(!cache.has(key));
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let current = true;
    if (!enabled) { setTaxonomy(null); setLoading(false); setError(null); return () => { current = false; }; }
    setTaxonomy(cache.get(key) ?? null); setLoading(!cache.has(key)); setError(null);
    getTaxonomyOptions(institutionId?.trim() || undefined).then((value) => { cache.set(key, value); if (current) setTaxonomy(value); }).catch((reason: unknown) => { if (current) setError(reason instanceof Error ? reason.message : "Unable to load taxonomy"); }).finally(() => { if (current) setLoading(false); });
    return () => { current = false; };
  }, [enabled, institutionId, key]);
  const labels = useMemo(() => new Map(taxonomy?.broadCategories.flatMap((b) => [[b.id, { ar: b.nameAr, en: b.nameEn }] as const, ...b.specificTypes.map((s) => [s.id, { ar: s.nameAr, en: s.nameEn }] as const)]) ?? []), [taxonomy]);
  return { taxonomy, loading, error, label: (id?: string | null, language: "ar" | "en" = "ar") => id ? labels.get(id)?.[language] ?? id : "—" };
}
