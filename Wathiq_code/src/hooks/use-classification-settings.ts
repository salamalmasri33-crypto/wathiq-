import { useCallback, useEffect, useState } from "react";
import * as api from "@/services/classification-settings.service";
import type { BroadCategory, ClassificationStatus } from "@/types/classification";
export function useClassificationSettings(institutionId:string){
 const [taxonomy,setTaxonomy]=useState<BroadCategory[]>([]),[status,setStatus]=useState<ClassificationStatus|null>(null),[loading,setLoading]=useState(true),[error,setError]=useState<string|null>(null);
 const reload=useCallback(async()=>{if(!institutionId){setTaxonomy([]);setStatus(null);setLoading(false);return}setLoading(true);setError(null);try{const [t,s]=await Promise.all([api.getClassificationTaxonomy(institutionId),api.getClassificationStatus(institutionId)]);setTaxonomy(t);setStatus(s)}catch{setError("load")}finally{setLoading(false)}},[institutionId]);
 useEffect(()=>{void reload()},[reload]); return {taxonomy,status,loading,error,reload};
}
