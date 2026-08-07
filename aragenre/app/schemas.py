from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class SpecificDefinition(BaseModel):
    model_config = ConfigDict(extra="allow")

    specific_type: str = Field(min_length=1, max_length=150)
    name_ar: str = Field(min_length=1, max_length=250)
    name_en: str = Field(min_length=1, max_length=250)
    definition_ar: str = Field(min_length=5)
    definition_en: str = Field(min_length=5)
    is_active: bool = True


class BroadDefinition(BaseModel):
    model_config = ConfigDict(extra="allow")

    broad_category: str = Field(min_length=1, max_length=150)
    name_ar: str = Field(min_length=1, max_length=250)
    name_en: str = Field(min_length=1, max_length=250)
    definition_ar: str = Field(min_length=5)
    definition_en: str = Field(min_length=5)
    is_active: bool = True
    specific_types: list[SpecificDefinition] = Field(min_length=1)


class DefinitionsPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    schema_version: str = "1.0"
    project: str = "Wathiq"
    broad_categories: list[BroadDefinition] = Field(min_length=1)

    @field_validator("broad_categories")
    @classmethod
    def unique_categories(cls, values: list[BroadDefinition]) -> list[BroadDefinition]:
        broad_ids = [item.broad_category for item in values]
        if len(broad_ids) != len(set(broad_ids)):
            raise ValueError("Duplicate broad_category identifiers")

        specific_ids = [
            specific.specific_type
            for broad in values
            for specific in broad.specific_types
        ]
        if len(specific_ids) != len(set(specific_ids)):
            raise ValueError("Duplicate specific_type identifiers")
        return values


class ExampleRecord(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str = Field(min_length=1, max_length=200)
    broad_category: str = Field(min_length=1, max_length=150)
    specific_type: str = Field(min_length=1, max_length=150)
    text: str = Field(min_length=10)
    language: str = "ar"
    source: str = "admin"
    length_group: str | None = None
    char_count: int | None = None

    @field_validator("text")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if len(normalized) < 10:
            raise ValueError("Example text is too short")
        return normalized


class ExamplesPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    schema_version: str = "1.0"
    project: str = "Wathiq"
    examples: list[ExampleRecord] = Field(min_length=1)

    @field_validator("examples")
    @classmethod
    def unique_examples(cls, values: list[ExampleRecord]) -> list[ExampleRecord]:
        ids = [item.id for item in values]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate example identifiers")
        return values


class SingleBroadUpsert(BaseModel):
    broad: BroadDefinition


class SingleSpecificUpsert(BaseModel):
    broad_category: str = Field(min_length=1)
    specific: SpecificDefinition


class ExamplesUpsert(BaseModel):
    examples: list[ExampleRecord] = Field(min_length=1)


class NonEmptyPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def require_change(self):
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided")
        return self


class BroadPatch(NonEmptyPatch):
    name_ar: str | None = Field(default=None, min_length=1, max_length=250)
    name_en: str | None = Field(default=None, min_length=1, max_length=250)
    definition_ar: str | None = Field(default=None, min_length=5)
    definition_en: str | None = Field(default=None, min_length=5)
    is_active: bool | None = None


class SpecificPatch(BroadPatch):
    broad_id: str | None = Field(default=None, min_length=1, max_length=150)


class ExamplePatch(NonEmptyPatch):
    text: str | None = Field(default=None, min_length=10)
    specific_id: str | None = Field(default=None, min_length=1, max_length=150)
    language: str | None = Field(default=None, min_length=1)
    source: str | None = Field(default=None, min_length=1)
    length_group: str | None = None

    @field_validator("text")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = " ".join(value.split())
        if len(normalized) < 10:
            raise ValueError("Example text is too short")
        return normalized


class MutationResponse(BaseModel):
    success: bool
    message: str
    entity_id: str
    index_ready: bool = False
    requires_rebuild: bool = True


class DeletionImpactResponse(BaseModel):
    institution_id: str
    entity_type: Literal["broad", "specific"]
    entity_id: str
    can_delete_directly: bool
    requires_confirmation: bool
    dependencies: dict[str, int]
    message_ar: str
    message_en: str


class DeleteResponse(BaseModel):
    success: bool
    deleted: bool
    requires_confirmation: bool = False
    dependencies: dict[str, int] = Field(default_factory=dict)
    deleted_counts: dict[str, int] = Field(default_factory=dict)
    index_ready: bool = False
    requires_rebuild: bool = False
    message_ar: str = ""
    message_en: str = ""


class ExampleDeleteResponse(BaseModel):
    success: bool
    deleted: bool
    example_id: str
    index_ready: bool = False
    requires_rebuild: bool = True


class ReplacementPreviewResponse(BaseModel):
    valid: bool = True
    current: dict[str, int] = Field(default_factory=dict)
    incoming: dict[str, int] = Field(default_factory=dict)
    will_replace: dict[str, int] = Field(default_factory=dict)
    will_delete: dict[str, int] = Field(default_factory=dict)
    will_add: dict[str, int] = Field(default_factory=dict)
    will_update: dict[str, int] = Field(default_factory=dict)
    unknown_specific_ids: list[str] = Field(default_factory=list)
    requires_confirmation: bool
    applied: bool = False
    index_ready: bool = False
    requires_rebuild: bool = False


class BroadRecordResponse(BaseModel):
    institution_id: str
    id: str
    name_ar: str
    name_en: str
    definition_ar: str
    definition_en: str
    is_active: bool
    sort_order: int
    updated_at: str
    specific_count: int | None = None
    example_count: int | None = None


class SpecificRecordResponse(BaseModel):
    institution_id: str
    id: str
    broad_id: str
    name_ar: str
    name_en: str
    definition_ar: str
    definition_en: str
    is_active: bool
    sort_order: int
    updated_at: str


class ExampleRecordResponse(BaseModel):
    institution_id: str
    id: str
    broad_id: str
    specific_id: str
    text: str
    language: str
    source: str
    length_group: str | None = None
    char_count: int | None = None
    text_hash: str
    updated_at: str


class BroadListResponse(BaseModel):
    broad_categories: list[BroadRecordResponse]


class SpecificListResponse(BaseModel):
    specific_types: list[SpecificRecordResponse]


class ExampleListResponse(BaseModel):
    examples: list[ExampleRecordResponse]


class ClassifyRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "id": "document_123",
                "text": "قرار إداري بتشكيل لجنة لمراجعة ملفات العقود ورفع تقرير خلال ثلاثين يوما",
            }
        },
    )

    id: str
    text: str

    @field_validator("id", "text")
    @classmethod
    def reject_blank_values(cls, value: str, info) -> str:
        if not value.strip():
            raise ValueError(f"{info.field_name} must not be empty")
        return value


class CandidateScore(BaseModel):
    id: str
    name_ar: str
    final_score: float
    sources: dict[str, float | int | None] = Field(default_factory=dict)


class ClassifyResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "document_123",
                "broad_genre": "AdministrativeAndOrganizational",
                "specific_genre": "AdministrativeDecision",
            }
        }
    )

    id: str
    broad_genre: str
    specific_genre: str


class DebugClassifyResponse(BaseModel):
    id: str
    broad_category: str
    broad_category_ar: str
    specific_type: str
    specific_type_ar: str
    model_pipeline: str = "V10 Broad + V18 Specific K20"
    debug: dict[str, Any]


class ImportResponse(BaseModel):
    status: Literal["ok"] = "ok"
    imported: dict[str, int]
    index_ready: bool
    warnings: list[str] = Field(default_factory=list)


class RebuildResponse(BaseModel):
    status: Literal["ok"] = "ok"
    success: bool = True
    institution_id: str | None = None
    index_ready: bool
    requires_rebuild: bool = False
    statistics: dict[str, Any]
    warnings: list[str] = Field(default_factory=list)
