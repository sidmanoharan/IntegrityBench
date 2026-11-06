"""Download the benchmark and answer key from Hugging Face and verify them against manifest.json.

Both files sit behind a terms-of-use agreement. Accept it on the dataset page, then create an access
token at https://huggingface.co/settings/tokens and export it as HF_TOKEN.
"""

import os
import sys

from .data import file_sha256
from .integrity import load_answer_key, load_manifest

HF_URL = "https://huggingface.co/datasets/{repo}/resolve/{revision}/{filename}"


def fetch(repo, filename, dest, token=None, revision="main", timeout=120):
    import requests
    url = HF_URL.format(repo=repo, revision=revision, filename=filename)
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    with requests.get(url, headers=headers, stream=True, timeout=timeout) as r:
        if r.status_code in (401, 403):
            raise SystemExit(f"access denied for {repo}/{filename}: accept the terms of use on the dataset "
                             "page and set HF_TOKEN to a token from https://huggingface.co/settings/tokens")
        if r.status_code == 404:
            raise SystemExit(f"{filename} not found in {repo} (revision {revision})")
        r.raise_for_status()
        tmp = dest + ".part"
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(1 << 16):
                f.write(chunk)
    os.replace(tmp, dest)
    return dest


def download(out_dir="data", answer_key=True, token=None, revision=None, log=sys.stderr):
    """Fetch the official v1.0 files into `out_dir`; returns their local paths."""
    m = load_manifest()
    revision = revision or m.get("hf_revision", "main")
    token = token or os.environ.get("HF_TOKEN")
    os.makedirs(out_dir, exist_ok=True)
    paths = {}

    bench = os.path.join(out_dir, m["benchmark_file"])
    print(f"downloading {m['benchmark_file']} from {m['hf_dataset']}", file=log)
    fetch(m["hf_dataset"], m["benchmark_file"], bench, token, revision)
    if m.get("benchmark_sha256") and file_sha256(bench) != m["benchmark_sha256"]:
        os.remove(bench)
        raise SystemExit("the downloaded benchmark does not match the official v1.0 checksum")
    paths["benchmark"] = bench

    if answer_key:
        repo = m.get("hf_answer_key_repo") or m["hf_dataset"]
        key = os.path.join(out_dir, m["answer_key_file"])
        print(f"downloading {m['answer_key_file']} from {repo}", file=log)
        fetch(repo, m["answer_key_file"], key, token, revision)
        load_answer_key(key, log=log)  # verifies the contents against the manifest
        paths["answer_key"] = key

    for name, p in paths.items():
        print(f"  {name}: {p} (verified)", file=log)
    return paths
