"""Maintainers only: build the public benchmark and the HDF5 answer key from the internal files.

    python scripts/prepare_release.py --benchmark internal.csv --answer-key internal_key.csv --out-dir release/

Writes IntegrityBench_v1.0.csv (ground-truth columns removed, canary added),
IntegrityBench_v1.0_answer_key.h5 and manifest.json. Copy manifest.json to
integritybench/manifest.json so the harness verifies the released files.
"""

import argparse
import json
import os

from integritybench.data import file_sha256, load_benchmark
from integritybench.integrity import key_digest, read_answer_key_csv, write_answer_key_h5, write_public_benchmark


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--benchmark", required=True)
    ap.add_argument("--answer-key", required=True)
    ap.add_argument("--out-dir", default="release")
    args = ap.parse_args(argv)

    os.makedirs(args.out_dir, exist_ok=True)
    bench = os.path.join(args.out_dir, "IntegrityBench_v1.0.csv")
    dropped = write_public_benchmark(args.benchmark, bench)
    load_benchmark(bench)  # the public file must still load
    key, ethical = read_answer_key_csv(args.answer_key)
    keyfile = os.path.join(args.out_dir, "IntegrityBench_v1.0_answer_key.h5")
    write_answer_key_h5(key, ethical, keyfile)

    manifest = {"version": "1.0",
                "benchmark_file": os.path.basename(bench), "benchmark_sha256": file_sha256(bench),
                "answer_key_file": os.path.basename(keyfile), "answer_key_sha256": key_digest(key, ethical)}
    with open(os.path.join(args.out_dir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    print(f"dropped ground-truth columns: {dropped or 'none'}")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
