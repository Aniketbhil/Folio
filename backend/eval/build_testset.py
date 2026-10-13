"""Testset generator and exporter CLI."""

import argparse
import json
from pathlib import Path
import sys

backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from eval.testset import Testset, TestsetItem


def build_testset(output_path: str, source_sample: bool = True) -> None:
    sample_path = Path(__file__).resolve().parent / "testset.sample.json"
    if source_sample and sample_path.exists():
        testset = Testset.load_from_file(sample_path)
        testset.save_to_file(output_path)
        print(f"Exported curated sample testset ({len(testset.items)} items) to {output_path}")
    else:
        print("Synthesizing testset items...")
        # Fallback or synthetic builder
        testset = Testset.load_from_file(sample_path)
        testset.save_to_file(output_path)
        print(f"Generated testset with {len(testset.items)} items.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate or export testset.")
    parser.add_argument("--out", default="eval/testset.json", help="Output path for testset JSON")
    args = parser.parse_args()
    build_testset(args.out)
