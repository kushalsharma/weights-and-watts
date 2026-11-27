#!/usr/bin/env python3
"""Downloads the files episode 1 ran, at the same revisions, into ComfyUI's models folder, and checks them.

  python get_models.py h3-image            # MiniMax H3-Image: 29.4 GB
  python get_models.py p-h3-image          # P-H3-Image: 26.8 GB
  python get_models.py both --to ComfyUI/models
  python get_models.py both --check        # only check what is there (add --sha256 to hash every file)

Uses huggingface_hub when it is installed (pip install huggingface_hub), and a plain download that can resume when not.
"""
import argparse, hashlib, json, os, shutil, sys, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
MODELS = json.load(open(os.path.join(HERE, "models.json")))["models"]


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 22), b""):
            h.update(block)
    return h.hexdigest()


def plain_download(f, dest):
    url = f"https://huggingface.co/{f['repo']}/resolve/{f['revision']}/{f['file']}"
    part = dest + ".part"
    have = os.path.getsize(part) if os.path.exists(part) else 0
    req = urllib.request.Request(url, headers={"Range": f"bytes={have}-"} if have else {})
    with urllib.request.urlopen(req, timeout=60) as r, open(part, "ab" if have and r.status == 206 else "wb") as out:
        done, last = (have if r.status == 206 else 0), 0
        while True:
            block = r.read(1 << 22)
            if not block:
                break
            out.write(block)
            done += len(block)
            if done - last > 1 << 30:
                last = done
                print(f"    {done / 1e9:.1f} of {f['bytes'] / 1e9:.1f} GB", flush=True)
    os.replace(part, dest)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("model", choices=sorted(MODELS) + ["both"])
    ap.add_argument("--to", default="ComfyUI/models", help="ComfyUI's models folder, or any folder to pass to run_takes.py as --models-dir (default: ComfyUI/models)")
    ap.add_argument("--check", action="store_true", help="download nothing; say what is there and what is missing")
    ap.add_argument("--sha256", action="store_true", help="also check every file's checksum (slow: about a minute per 10 GB)")
    a = ap.parse_args()
    files = [f for k in (MODELS if a.model == "both" else [a.model]) for f in MODELS[k]["files"]]
    root = os.path.abspath(os.path.expanduser(a.to))
    todo = []
    for f in files:
        dest = os.path.join(root, f["file"])
        ok = os.path.exists(dest) and os.path.getsize(dest) == f["bytes"]
        if ok and a.sha256:
            ok = sha256(dest) == f["sha256"]
            print(f"{'checksum matches' if ok else 'CHECKSUM DIFFERS'}: {f['file']}")
        elif ok:
            print(f"have {f['file']} ({f['bytes'] / 1e9:.2f} GB)")
        if not ok:
            todo.append((f, dest))
    need = sum(f["bytes"] for f, _ in todo)
    if not todo:
        print("All files are there.")
        return
    probe = root
    while not os.path.exists(probe):
        probe = os.path.dirname(probe)
    free = shutil.disk_usage(probe).free
    print(f"To download: {need / 1e9:.1f} GB. Free here: {free / 1e9:.1f} GB.")
    if a.check:
        for f, _ in todo:
            print(f"missing {f['file']}")
        sys.exit(1)
    if need + 2e9 > free:
        sys.exit("Not enough free disk (this keeps 2 GB spare).")
    os.makedirs(root, exist_ok=True)
    try:
        from huggingface_hub import hf_hub_download
    except ImportError:
        hf_hub_download = None
    for f, dest in todo:
        print(f"getting {f['repo']} / {f['file']} ({f['bytes'] / 1e9:.2f} GB)", flush=True)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        if hf_hub_download:
            hf_hub_download(repo_id=f["repo"], filename=f["file"], revision=f["revision"], local_dir=root)
        else:
            plain_download(f, dest)
        if os.path.getsize(dest) != f["bytes"]:
            sys.exit(f"{f['file']} did not come down whole.")
        if a.sha256 and sha256(dest) != f["sha256"]:
            sys.exit(f"{f['file']} has the wrong checksum.")
    print("Done.")


if __name__ == "__main__":
    main()
