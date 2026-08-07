import numpy as np

from app.database import SQLiteStore
from app.schemas import DefinitionsPayload, ExamplesPayload
from app.settings import Settings
from app.tenant_manager import InstitutionClassifierManager


class FakeModels:
    device = "cpu"
    def _encode(self, texts):
        vectors=[]
        for text in texts:
            value=sum(ord(char) for char in text)
            vectors.append([1.0+(value%7)/10, 1.0+(value%11)/10, 1.0+(value%13)/10])
        array=np.asarray(vectors,dtype=np.float32)
        return array/np.linalg.norm(array,axis=1,keepdims=True)
    def encode_e5(self,texts,role): return self._encode(texts)
    def encode_arabic(self,texts): return self._encode(texts)


def payloads(prefix,broad,specific):
    definitions=DefinitionsPayload.model_validate({"broad_categories":[{"broad_category":broad,"name_ar":"تصنيف","name_en":broad,"definition_ar":"تعريف عربي واضح للتصنيف المؤسسي","definition_en":f"Definition for {broad}","specific_types":[{"specific_type":specific,"name_ar":"نوع","name_en":specific,"definition_ar":"تعريف عربي واضح للنوع المحدد","definition_en":f"Definition for {specific}"}]}]})
    examples=ExamplesPayload.model_validate({"examples":[{"id":f"{prefix}_{i}","broad_category":broad,"specific_type":specific,"text":f"هذا مثال تصنيف مؤسسي واضح رقم {i} ويحتوي نصا كافيا"} for i in range(1,6)]})
    return definitions,examples


def test_indexes_and_classification_are_isolated_per_institution(tmp_path):
    store=SQLiteStore(tmp_path/"indexes.db")
    da,ea=payloads("a","BroadA","SpecificA")
    db,eb=payloads("b","BroadB","SpecificB")
    store.replace_definitions("a",da); store.replace_examples("a",ea)
    store.replace_definitions("b",db); store.replace_examples("b",eb)
    manager=InstitutionClassifierManager(store,FakeModels(),Settings(database_path=tmp_path/"indexes.db"))
    manager.rebuild("a"); manager.rebuild("b")
    classifier_b=manager.get("b")
    index_b=classifier_b._index
    assert manager.get("a").classify("وثيقة للاختبار")["broad_category"]=="BroadA"
    assert classifier_b.classify("وثيقة للاختبار")["broad_category"]=="BroadB"
    store.replace_examples("a",ea)
    manager.rebuild("a")
    assert manager.get("b") is classifier_b
    assert classifier_b._index is index_b
    assert classifier_b.statistics()["examples"]==5
    store.close()
