import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useInstitutionTaxonomy } from "@/hooks/use-institution-taxonomy";

type Props = { institutionId?: string; broadGenre: string; specificGenre: string; onChange: (value: { broadGenre: string; specificGenre: string }) => void; language?: "ar" | "en"; allowAll?: boolean; disabled?: boolean; showLabels?: boolean };
export function GenreSelectors({ institutionId, broadGenre, specificGenre, onChange, language = "ar", allowAll = false, disabled, showLabels = true }: Props) {
  const { taxonomy, loading, error } = useInstitutionTaxonomy(institutionId);
  const broad = taxonomy?.broadCategories ?? [];
  const specifics = broad.find((item) => item.id === broadGenre)?.specificTypes ?? [];
  const all = allowAll ? "all" : "";
  const t = (ar: string, en: string) => language === "ar" ? ar : en;
  return <>
    <div className={showLabels ? "space-y-2" : undefined}>{showLabels && <Label>{t("التصنيف العام", "Broad genre")}</Label>}<Select disabled={disabled || loading} value={broadGenre || all} onValueChange={(value) => onChange({ broadGenre: value === "all" ? "" : value, specificGenre: "" })}><SelectTrigger><SelectValue placeholder={loading ? t("جارٍ التحميل…", "Loading…") : t("التصنيف العام", "Broad genre")} /></SelectTrigger><SelectContent>{allowAll && <SelectItem value="all">{t("كل التصنيفات العامة", "All broad genres")}</SelectItem>}{broad.map((item) => <SelectItem key={item.id} value={item.id}>{language === "ar" ? item.nameAr : item.nameEn}</SelectItem>)}</SelectContent></Select></div>
    <div className={showLabels ? "space-y-2" : undefined}>{showLabels && <Label>{t("التصنيف الخاص", "Specific genre")}</Label>}<Select disabled={disabled || loading || !broadGenre} value={specificGenre || all} onValueChange={(value) => onChange({ broadGenre, specificGenre: value === "all" ? "" : value })}><SelectTrigger><SelectValue placeholder={t("التصنيف الخاص", "Specific genre")} /></SelectTrigger><SelectContent>{allowAll && <SelectItem value="all">{t("كل التصنيفات الخاصة", "All specific genres")}</SelectItem>}{specifics.map((item) => <SelectItem key={item.id} value={item.id}>{language === "ar" ? item.nameAr : item.nameEn}</SelectItem>)}</SelectContent></Select></div>
    {error && <p className="col-span-full text-sm text-destructive">{t("تعذر تحميل التصنيفات.", "Could not load taxonomy.")}</p>}
  </>;
}
