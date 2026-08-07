from __future__ import annotations

from pathlib import Path
import sys
import unittest

SERVICE_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = SERVICE_ROOT / "src"

if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from wathiq_araseg.segmentation import (  # noqa: E402
    AbstractSegmentationPipeline,
    DuplicatePipelineRegistrationError,
    FakeSegmentationPipeline,
    PipelineRegistry,
    UnsupportedTrackError,
)


class PipelineRegistryTests(unittest.TestCase):
    def test_registry_resolves_pa_through_abstract_type(self) -> None:
        registry = PipelineRegistry([FakeSegmentationPipeline()])

        pipeline = registry.resolve("PA")

        self.assertIsInstance(pipeline, AbstractSegmentationPipeline)
        self.assertEqual(pipeline.track, "PA")
        self.assertEqual(pipeline.pipeline_id, "fake-pa-single-segment")

    def test_unsupported_track_raises_controlled_exception(self) -> None:
        registry = PipelineRegistry([FakeSegmentationPipeline()])

        with self.assertRaises(UnsupportedTrackError):
            registry.resolve("NP")

    def test_duplicate_registration_raises_controlled_exception(self) -> None:
        registry = PipelineRegistry([FakeSegmentationPipeline()])

        with self.assertRaises(DuplicatePipelineRegistrationError):
            registry.register(FakeSegmentationPipeline())


if __name__ == "__main__":
    unittest.main()
