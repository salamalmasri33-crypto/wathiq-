from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    service_name: str = os.getenv("SERVICE_NAME", "Wathiq Classifier Service")
    database_path: Path = Path(os.getenv("DATABASE_PATH", "./storage/wathiq_classifier.db"))
    default_institution_id: str = os.getenv(
        "DEFAULT_INSTITUTION_ID", "default-institution"
    )

    e5_model: str = os.getenv("E5_MODEL", "intfloat/multilingual-e5-base")
    arabic_model: str = os.getenv(
        "ARABIC_MODEL",
        "Omartificial-Intelligence-Space/Arabic-Triplet-Matryoshka-V2",
    )
    device: str = os.getenv("MODEL_DEVICE", "auto")

    e5_max_length: int = int(os.getenv("E5_MAX_LENGTH", "256"))
    arabic_max_length: int = int(os.getenv("ARABIC_MAX_LENGTH", "512"))
    e5_batch_size: int = int(os.getenv("E5_BATCH_SIZE", "16"))
    arabic_batch_size: int = int(os.getenv("ARABIC_BATCH_SIZE", "8"))

    # Exact core configuration from the V10 Broad + V18 Specific K=20 pipeline.
    broad_top_m: int = int(os.getenv("BROAD_TOP_M", "5"))
    semantic_e5_weight: float = float(os.getenv("SEMANTIC_E5_WEIGHT", "0.30"))
    semantic_arabic_weight: float = float(os.getenv("SEMANTIC_ARABIC_WEIGHT", "0.50"))
    bm25_weight: float = float(os.getenv("BM25_WEIGHT", "0.20"))
    broad_example_weight: float = float(os.getenv("BROAD_EXAMPLE_WEIGHT", "0.85"))
    broad_definition_weight: float = float(os.getenv("BROAD_DEFINITION_WEIGHT", "0.15"))
    broad_definition_e5_weight: float = float(
        os.getenv("BROAD_DEFINITION_E5_WEIGHT", "0.40")
    )
    broad_definition_arabic_weight: float = float(
        os.getenv("BROAD_DEFINITION_ARABIC_WEIGHT", "0.60")
    )
    softmax_temperature: float = float(os.getenv("SOFTMAX_TEMPERATURE", "0.50"))

    specific_examples_per_label: int = int(
        os.getenv("SPECIFIC_EXAMPLES_PER_LABEL", "3")
    )
    specific_k: int = int(os.getenv("SPECIFIC_K", "20"))
    rrf_e5_weight: float = float(os.getenv("RRF_E5_WEIGHT", "0.30"))
    rrf_arabic_weight: float = float(os.getenv("RRF_ARABIC_WEIGHT", "0.50"))
    rrf_bm25_weight: float = float(os.getenv("RRF_BM25_WEIGHT", "0.20"))
    rrf_constant: int = int(os.getenv("RRF_CONSTANT", "10"))

    max_input_chars: int = int(os.getenv("MAX_INPUT_CHARS", "100000"))

    def validate(self) -> None:
        if abs(
            self.semantic_e5_weight
            + self.semantic_arabic_weight
            + self.bm25_weight
            - 1.0
        ) > 1e-9:
            raise ValueError("Broad source weights must sum to 1.0")
        if abs(self.broad_example_weight + self.broad_definition_weight - 1.0) > 1e-9:
            raise ValueError("Broad example/definition weights must sum to 1.0")
        if abs(
            self.broad_definition_e5_weight
            + self.broad_definition_arabic_weight
            - 1.0
        ) > 1e-9:
            raise ValueError("Broad definition weights must sum to 1.0")
        if abs(
            self.rrf_e5_weight
            + self.rrf_arabic_weight
            + self.rrf_bm25_weight
            - 1.0
        ) > 1e-9:
            raise ValueError("Specific RRF weights must sum to 1.0")


settings = Settings()
settings.validate()
