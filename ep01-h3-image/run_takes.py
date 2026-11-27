#!/usr/bin/env python3
"""Runs the prompts of Weights & Watts episode 1, or your own, on MiniMax H3-Image or P-H3-Image through ComfyUI, and
writes one CSV row per take: the time, the card's and the system's memory at their highest, the card's average and
highest watts, and its watt-hours, measured the way the episode measured them.

  python run_takes.py --list
  python run_takes.py --model h3-image --prompt c-size-4mp
  python run_takes.py --model p-h3-image --prompt b-navy-coat --picture face=my-face.png
  python run_takes.py --model h3-image --text "A studio portrait of ..." --size 2048x2048
  python run_takes.py --model h3-image --poster poster-2 --picture face=my-face.png --picture body=my-body.png

Run it with the Python that runs ComfyUI (the one setup.sh makes, or Colab's). It needs nothing outside the standard
library. See README.md for the setup and for what each column means.
"""
import argparse, csv, hashlib, json, os, random, shutil, signal, subprocess, sys, threading, time, urllib.error, urllib.parse, urllib.request, uuid
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
COLUMNS = ["made_at", "prompt", "test", "step", "take", "model", "card", "place", "mode", "pictures_in", "width", "height", "megapixels", "steps", "seed",
           "seconds", "card_gb_peak", "system_gb_peak", "watts_avg", "watts_peak", "watt_hours", "card_temp_c", "colab_units", "cost_usd", "units_estimated",
           "card_gb_before", "system_gb_before", "samples", "picture", "error"]
BOX_FLAGS = "--fast-disk --preview-method auto --preview-size 1024"


def load(name):
    with open(os.path.join(HERE, name), encoding="utf-8") as f:
        return json.load(f)


def gb(mib):
    """MiB as the episode's ledger shows them: GiB, to one decimal, called GB."""
    return None if mib is None else round(mib / 102.4) / 10


# ---------------------------------------------------------------- measuring

class Sampler:
    """Reads the card (nvidia-smi) and the system's memory (/proc/meminfo) about once a second, all the time the script
    runs, as the episode's monitor did. A take's numbers come from the samples between one second before it was sent
    and one second after it finished."""

    def __init__(self, gpu, every):
        self.gpu, self.every = str(gpu), every
        self.samples = []  # (time, card MiB used, watts, °C, system MiB used)
        self.lock = threading.Lock()
        self.stop_flag = threading.Event()
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()

    @staticmethod
    def system_mib():
        try:
            with open("/proc/meminfo") as f:
                kb = {line.split(":")[0]: int(line.split()[1]) for line in f if line.split(":")[0] in ("MemTotal", "MemAvailable")}
            return (kb["MemTotal"] - kb["MemAvailable"]) // 1024
        except Exception:
            try:
                import psutil
                vm = psutil.virtual_memory()
                return (vm.total - vm.available) // 2**20
            except Exception:
                return None

    def card(self):
        try:
            out = subprocess.run(["nvidia-smi", "-i", self.gpu, "--query-gpu=memory.used,power.draw,temperature.gpu", "--format=csv,noheader,nounits"],
                                 capture_output=True, text=True, timeout=10).stdout.strip().splitlines()[0]
        except Exception:
            return None, None, None

        def num(s):
            try:
                return float(s)
            except ValueError:
                return None
        used, watts, temp = (num(x.strip()) for x in out.split(","))
        return used, watts, temp

    def run(self):
        while not self.stop_flag.is_set():
            t0 = time.time()
            used, watts, temp = self.card()
            ram = self.system_mib()
            with self.lock:
                self.samples.append((t0, used, watts, temp, ram))
            self.stop_flag.wait(max(0.0, self.every - (time.time() - t0)))

    def window(self, start, end):
        """The take's numbers, worked out as the episode's ledger worked them out."""
        with self.lock:
            s = [x for x in self.samples if start - 1 <= x[0] <= end + 1]
            before = [x for x in self.samples if x[0] < start - 1]
        top = lambda i: max((x[i] for x in s if x[i] is not None), default=None)
        watts = [(x[0], x[2]) for x in s if x[2] is not None]
        energy_wh = avg_w = None
        if len(watts) >= 2:
            joules = sum(w0 * (t1 - t0) for (t0, w0), (t1, _) in zip(watts, watts[1:]))
            span = watts[-1][0] - watts[0][0]
            energy_wh = round(joules / 3600, 2)
            avg_w = round(joules / span, 1) if span > 0 else None
        peak_w = top(2)
        temp = top(3)
        b = before[-1] if before else None
        return {"card_gb_peak": gb(top(1)), "system_gb_peak": gb(top(4)), "watts_avg": avg_w, "watts_peak": None if peak_w is None else round(peak_w, 1),
                "watt_hours": energy_wh, "card_temp_c": None if temp is None else int(temp), "samples": len(s),
                "card_gb_before": gb(b[1]) if b else None, "system_gb_before": gb(b[4]) if b else None}

    def close(self):
        self.stop_flag.set()
        self.thread.join(timeout=15)


def card_label(gpu):
    try:
        out = subprocess.run(["nvidia-smi", "-i", str(gpu), "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=10).stdout.strip().splitlines()[0]
        name, mib = (x.strip() for x in out.rsplit(",", 1))
        return f"{name} {round(float(mib) / 1024)} GB"
    except Exception:
        return "unknown card"


# ---------------------------------------------------------------- ComfyUI

class Comfy:
    def __init__(self, url):
        self.url = url.rstrip("/")
        self.proc = None
        self.client = uuid.uuid4().hex

    def get(self, path, timeout=30):
        with urllib.request.urlopen(self.url + path, timeout=timeout) as r:
            return r.read()

    def get_json(self, path, timeout=30):
        return json.loads(self.get(path, timeout))

    def post_json(self, path, body):
        req = urllib.request.Request(self.url + path, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"ComfyUI refused the workflow: {e.read().decode(errors='replace')[:1500]}")

    def start(self, comfy_dir, python, port, flags, out, model_dirs, log_path):
        args = [python, "-u", "main.py", "--listen", "127.0.0.1", "--port", str(port),
                "--output-directory", os.path.join(out, "comfy-output"), "--input-directory", os.path.join(out, "comfy-input")]
        if model_dirs:
            yaml = os.path.join(out, "extra_model_paths.yaml")
            with open(yaml, "w") as f:
                for i, d in enumerate(model_dirs):
                    d = os.path.abspath(os.path.expanduser(d))
                    f.write(f"models_{i}:\n    base_path: {d}/\n    diffusion_models: diffusion_models/\n    text_encoders: text_encoders/\n    vae: vae/\n")
            args += ["--extra-model-paths-config", yaml]
        args += flags.split()
        os.makedirs(os.path.join(out, "comfy-input"), exist_ok=True)
        self.log = open(log_path, "a")
        print(f"Starting ComfyUI in {comfy_dir} on port {port} (log: {log_path})", flush=True)
        self.proc = subprocess.Popen(args, cwd=comfy_dir, stdout=self.log, stderr=subprocess.STDOUT, start_new_session=True)
        t = time.time()
        while time.time() - t < 900:
            if self.proc.poll() is not None:
                raise SystemExit(f"ComfyUI stopped while starting. The end of its log, {log_path}, says why.")
            try:
                self.get("/system_stats", timeout=3)
                print(f"ComfyUI is up after {time.time() - t:.0f} s.", flush=True)
                return
            except Exception:
                time.sleep(1)
        raise SystemExit("ComfyUI did not come up within 15 minutes.")

    def stop(self):
        if self.proc and self.proc.poll() is None:
            try:
                os.killpg(self.proc.pid, signal.SIGTERM)
                self.proc.wait(timeout=30)
            except Exception:
                try:
                    os.killpg(self.proc.pid, signal.SIGKILL)
                except Exception:
                    pass

    def alive(self):
        return self.proc is None or self.proc.poll() is None

    def has_files(self, files):
        """The model files ComfyUI can't see, by its own lists of each folder."""
        missing = []
        for f in files:
            folder, name = f["file"].split("/", 1)
            try:
                if name not in self.get_json(f"/models/{folder}"):
                    missing.append(f["file"])
            except Exception:
                return []  # an older ComfyUI without this list: let the take say what is missing
        return missing

    def upload(self, path):
        """Sends a picture to ComfyUI's input folder, named by what is in it, so a picture it has read before is not read again."""
        with open(path, "rb") as f:
            data = f.read()
        name = hashlib.sha256(data).hexdigest()[:20] + (os.path.splitext(path)[1].lower() or ".png")
        b = uuid.uuid4().hex
        body = (f"--{b}\r\nContent-Disposition: form-data; name=\"image\"; filename=\"{name}\"\r\nContent-Type: application/octet-stream\r\n\r\n".encode()
                + data + f"\r\n--{b}\r\nContent-Disposition: form-data; name=\"overwrite\"\r\n\r\ntrue\r\n--{b}--\r\n".encode())
        req = urllib.request.Request(self.url + "/upload/image", data=body, headers={"Content-Type": f"multipart/form-data; boundary={b}"})
        with urllib.request.urlopen(req, timeout=300) as r:
            return json.loads(r.read())["name"]

    def run(self, workflow):
        """Queues one workflow and waits for it. Returns ComfyUI's record of it, and the time it was sent."""
        sent = time.time()
        pid = self.post_json("/prompt", {"prompt": workflow, "client_id": self.client})["prompt_id"]
        while True:
            time.sleep(0.25)
            if not self.alive():
                raise RuntimeError("ComfyUI stopped while making the take (often: out of memory). Its log says more.")
            try:
                h = self.get_json(f"/history/{pid}")
            except Exception:
                continue
            if pid in h and h[pid].get("status", {}).get("completed") is not None:
                if h[pid]["status"].get("status_str") in ("success", "error"):
                    return h[pid], sent


def timing(record):
    """Seconds from ComfyUI starting the take to finishing it, by ComfyUI's own clock: what the episode's ledger counts."""
    msgs = {m[0]: m[1] for m in record.get("status", {}).get("messages", [])}
    if "execution_start" in msgs and "execution_success" in msgs:
        start, end = msgs["execution_start"]["timestamp"] / 1000, msgs["execution_success"]["timestamp"] / 1000
        return round(end - start, 2), start, end
    return None, None, None


def failure(record):
    for m in record.get("status", {}).get("messages", []):
        if m[0] == "execution_error":
            d = m[1]
            return f"{d.get('node_type', '')}: {d.get('exception_message', '')}".strip()[:600]
    return "ComfyUI did not finish the take."


# ---------------------------------------------------------------- workflows

def put(wf, where, value):
    node, field = where.split(".", 1)
    wf[node]["inputs"][field] = value


def workflow_for(model, text, width, height, seed, pictures, prefix):
    m = MODELS[model]
    n = len(pictures)
    if n > len(m["wire"]["pictures"]):
        raise SystemExit(f"{m['name']} takes at most {len(m['wire']['pictures'])} pictures in these workflows.")
    wf = load(m["workflows"]["pictures" if n else "words"])
    w = m["wire"]
    put(wf, w["prompt"], text)
    put(wf, w["width"], width)
    put(wf, w["height"], height)
    if "steps" in w:
        put(wf, w["steps"], m["steps"])
    put(wf, w["seed"], seed)
    put(wf, w["save"], prefix)
    for where, name in zip(w["pictures"], pictures):
        put(wf, where, name)
    fewer = m["fewer"].get(str(n)) if n else None
    if fewer:
        for where, src in fewer.get("link", {}).items():
            node, slot = src.split(":")
            put(wf, where, [node, int(slot)])
        for where in fewer.get("unset", []):
            node, field = where.split(".", 1)
            wf[node]["inputs"].pop(field, None)
        for node in fewer.get("drop", []):
            wf.pop(node, None)
    return wf


# ---------------------------------------------------------------- the prompts

def all_prompts():
    tests, posters = load("prompts/tests.json"), load("prompts/posters.json")
    return {**tests["prompts"], **posters["prompts"]}, posters["builds"]


def spec_for(name, model):
    p = PROMPTS.get(name)
    if not p:
        raise SystemExit(f"There is no prompt called {name!r}. `python run_takes.py --list` shows them all.")
    m = p["models"].get(model)
    if not m:
        raise SystemExit(f"{name!r} was only run on {', '.join(MODELS[k]['name'] for k in p['models'])} in the episode, so it has no prompt for {MODELS[model]['name']}.")
    return {"name": name, "test": p["test"], "title": p["title"], "text": m["prompt"], "pictures": m["pictures"],
            "size": m.get("size", p.get("size")), "seed": m.get("seed", p.get("seed")), "takes": m.get("takes", p.get("takes", 2))}


def list_prompts():
    print("Prompts (name, test, size, the models it has a prompt for, the pictures it needs):\n")
    for name, p in PROMPTS.items():
        size = p.get("size") or next(iter(p["models"].values())).get("size")
        pics = list(dict.fromkeys(x.partition("@")[0] for m in p["models"].values() for x in m["pictures"]))
        print(f"  {name:31} {p['test']:9} {size[0]}x{size[1]:<5} {', '.join(p['models']):21} {', '.join(pics) or '-'}")
    print("\nPosters (--poster NAME), the order each model built them in:\n")
    for b, spec in BUILDS.items():
        print(f"  {b}: {spec['title']}")
        for model, steps in spec["routes"].items():
            print(f"    {model}: {' > '.join(steps)}")
    print("\n'face' and 'body' are pictures of your own: --picture face=PATH --picture body=PATH. Any other name is the first take "
          "of that prompt, made earlier into the same --out folder (by the same model, unless it says @model).")


# ---------------------------------------------------------------- one take

def find_take(out, model, name):
    folder = os.path.join(out, model, name)
    found = sorted((os.path.join(folder, f) for f in os.listdir(folder) if f.endswith(".png") and "-take1-" in f), key=os.path.getmtime) if os.path.isdir(folder) else []
    return found[-1] if found else None


def resolve(ref, model, a, made):
    """The file for one picture a prompt asks for."""
    name, _, other = ref.partition("@")
    if ref in a.pictures:
        return a.pictures[ref]
    if name in a.pictures:
        return a.pictures[name]
    if name in ("face", "body"):
        raise SystemExit(f"This prompt needs a {name} picture of your own: add --picture {name}=PATH. README.md says what the episode used.")
    src = model if (not other or a.own_model) else other
    path = made.get((src, name)) or find_take(a.out, src, name)
    if path:
        return path
    hint = f"--model {src} --prompt {name}" if src != model or name not in BUILD_STEPS else "the poster's earlier steps"
    raise SystemExit(f"This prompt needs the first take of {name!r} by {MODELS[src]['name']}, and there isn't one in {a.out}. Make it first ({hint}), "
                     f"pass it with --picture {name}=PATH" + (", or add --own-model to use this model's own take." if src != model else "."))


def write_row(path, row):
    new = not os.path.exists(path) or os.path.getsize(path) == 0
    with open(path, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        if new:
            w.writeheader()
        w.writerow({k: ("" if row.get(k) is None else row.get(k)) for k in COLUMNS})


def make_takes(spec, model, a, comfy, sampler, made):
    m = MODELS[model]
    width, height = a.size or spec["size"]
    if width % 32 or height % 32:
        print(f"  Note: {width}x{height} is not a multiple of 32; both models work in 32-pixel squares.")
    takes = a.takes or spec["takes"]
    paths = [resolve(r, model, a, made) for r in spec["pictures"]]
    names = [comfy.upload(p) for p in paths]
    mode = "words" if not paths else ("one" if len(paths) == 1 else "several")
    folder = os.path.join(a.out, model, spec["name"])
    os.makedirs(folder, exist_ok=True)
    first = None
    for k in range(1, takes + 1):
        if k == 1:
            seed = a.seed if a.seed is not None else spec["seed"] if spec["seed"] is not None else random.randrange(2_147_483_647)
        else:
            seed = random.randrange(2_147_483_647)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        base = f"{stamp}-take{k}-seed{seed}"
        wf = workflow_for(model, spec["text"], width, height, seed, names, f"ww/{spec['name']}-{base}")
        print(f"  take {k} of {takes}: {spec['name']} on {m['name']}, {width}x{height}, seed {seed}, {len(paths)} picture(s) in ...", flush=True)
        row = {"prompt": spec["name"], "test": spec["test"], "step": spec["title"], "take": k, "model": m["name"], "card": a.card, "place": a.place,
               "mode": mode, "pictures_in": len(paths), "width": width, "height": height, "megapixels": round(width * height / 1e6, 2),
               "steps": m["steps"], "seed": seed}
        try:
            record, sent = comfy.run(wf)
            seconds, start, end = timing(record)
            row["made_at"] = datetime.fromtimestamp(start or sent, timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
            if record["status"].get("status_str") != "success" or seconds is None:
                raise RuntimeError(failure(record))
            time.sleep(a.sample_every + 1.2)  # so the samples reach a second past the end
            row.update(sampler.window(sent, end))
            row["seconds"] = seconds
            if a.units_per_hour:
                row["colab_units"] = round(seconds / 3600 * a.units_per_hour, 4)
                row["units_estimated"] = True
                if a.dollars_per_unit:
                    row["cost_usd"] = round(row["colab_units"] * a.dollars_per_unit, 4)
            images = [im for o in (record.get("outputs") or {}).values() for im in o.get("images", []) if im.get("type") == "output"]
            if not images:
                raise RuntimeError("ComfyUI finished without a picture.")
            im = images[0]
            q = urllib.parse.urlencode({"filename": im["filename"], "subfolder": im.get("subfolder", ""), "type": "output"})
            pic = os.path.join(folder, base + ".png")
            with open(pic, "wb") as f:
                f.write(comfy.get(f"/view?{q}", timeout=300))
            row["picture"] = os.path.relpath(pic, a.out)
            with open(os.path.join(folder, base + ".json"), "w") as f:
                json.dump({"row": row, "workflow_sent": wf, "comfy_status": record.get("status")}, f, indent=1)
            first = first or pic
            print(f"    {seconds:.1f} s | card {row['card_gb_peak']} GB | system {row['system_gb_peak']} GB | "
                  f"{row['watts_avg']} W average, {row['watts_peak']} W at most | {row['watt_hours']} Wh"
                  + (f" | {row['colab_units']} units" if row.get("colab_units") is not None else ""), flush=True)
        except (RuntimeError, urllib.error.URLError) as e:
            row["error"] = str(e)
            row.setdefault("made_at", datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"))
            print(f"    failed: {e}", flush=True)
        write_row(a.csv, row)
    if first:
        made[(model, spec["name"])] = first
    return first


# ---------------------------------------------------------------- main

def parse():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--list", action="store_true", help="list the episode's prompts and posters")
    ap.add_argument("--model", choices=sorted(MODELS), help="h3-image (MiniMax) or p-h3-image (Pruna)")
    ap.add_argument("--prompt", action="append", default=[], help="an episode prompt by name; give it more than once for several")
    ap.add_argument("--text", help="your own prompt, run with this model's episode settings")
    ap.add_argument("--poster", help="build one of the episode's posters, step by step: poster-1, poster-2 or poster-3")
    ap.add_argument("--also-tried", action="store_true", help="with --poster, also run the steps that were tried and did not carry on")
    ap.add_argument("--picture", action="append", default=[], help="NAME=PATH for a picture a prompt asks for (face, body, or a step's name); with --text, just PATH, in order")
    ap.add_argument("--own-model", action="store_true", help="where the episode used the other model's take as a picture, use this model's own")
    ap.add_argument("--takes", type=int, help="takes per prompt (the episode: 2, the first on a fixed seed)")
    ap.add_argument("--seed", type=int, help="seed of the first take (later takes always draw a new one)")
    ap.add_argument("--size", help="WIDTHxHEIGHT instead of the prompt's own size, e.g. 2048x2048")
    ap.add_argument("--out", default="runs", help="folder for pictures, records and the CSV (default: runs)")
    ap.add_argument("--csv", help="the CSV to add rows to (default: OUT/takes.csv)")
    ap.add_argument("--comfy", help="start ComfyUI from this folder for the run, and stop it after")
    ap.add_argument("--comfy-url", default=None, help="use a ComfyUI that is already running on this computer, e.g. http://127.0.0.1:8188")
    ap.add_argument("--comfy-python", default=sys.executable, help="the Python that starts ComfyUI (default: this one)")
    ap.add_argument("--port", type=int, default=8188)
    ap.add_argument("--comfy-flags", default=BOX_FLAGS, help=f"flags ComfyUI is started with (default, as on our RTX 3060: {BOX_FLAGS!r})")
    ap.add_argument("--models-dir", action="append", default=[], help="a folder holding diffusion_models/, text_encoders/ and vae/ with the files, if they are not in ComfyUI's own models folder")
    ap.add_argument("--gpu", default="0", help="which card nvidia-smi should read (default 0)")
    ap.add_argument("--sample-every", type=float, default=1.0, help="seconds between readings of the card and memory (default 1, as in the episode)")
    ap.add_argument("--units-per-hour", type=float, help="on Colab: the compute units an hour shown in Colab's Resources panel, to log units per take")
    ap.add_argument("--dollars-per-unit", type=float, help="on Colab: what one compute unit cost you, to log a cost per take")
    ap.add_argument("--card", help="a name for the card in the CSV (default: what nvidia-smi says)")
    ap.add_argument("--place", default="colab" if os.environ.get("COLAB_RELEASE_TAG") else "home", help="a word for where it ran (default: home, or colab on Colab)")
    a = ap.parse_args()
    pics, loose = {}, []
    for p in a.picture:
        k, sep, v = p.partition("=")
        if sep and not os.path.exists(p):
            pics[k] = os.path.abspath(os.path.expanduser(v))
        else:
            loose.append(os.path.abspath(os.path.expanduser(p)))
    for p in list(pics.values()) + loose:
        if not os.path.isfile(p):
            ap.error(f"no such picture: {p}")
    a.pictures, a.loose = pics, loose
    if a.size:
        try:
            a.size = tuple(int(x) for x in a.size.lower().split("x"))
            assert len(a.size) == 2
        except Exception:
            ap.error("--size is WIDTHxHEIGHT, e.g. 2048x2048")
    a.out = os.path.abspath(os.path.expanduser(a.out))
    a.csv = os.path.abspath(os.path.expanduser(a.csv)) if a.csv else os.path.join(a.out, "takes.csv")
    if not a.list:
        if not a.model:
            ap.error("--model is needed: h3-image or p-h3-image")
        if not (a.prompt or a.text or a.poster):
            ap.error("say what to run: --prompt NAME, --text \"...\" or --poster NAME (--list shows the names)")
        if a.poster and a.poster not in BUILDS:
            ap.error(f"--poster is one of {', '.join(BUILDS)}")
        if a.comfy and a.comfy_url:
            ap.error("give --comfy (start one) or --comfy-url (use a running one), not both")
        if a.loose and not a.text:
            ap.error("for an episode prompt, name each picture: --picture face=PATH (--list shows what each prompt needs)")
    return a


def main():
    a = parse()
    if a.list:
        return list_prompts()
    os.makedirs(a.out, exist_ok=True)
    jobs = [spec_for(n, a.model) for n in a.prompt]
    if a.text:
        n = len(a.loose)
        size = a.size or (2048, 2048)
        jobs.append({"name": "own-prompt", "test": "own", "title": a.text[:80], "text": a.text, "pictures": [f"picture-{i + 1}" for i in range(n)],
                     "size": size, "seed": None, "takes": 2})
        a.pictures.update({f"picture-{i + 1}": p for i, p in enumerate(a.loose)})
    if a.poster:
        spec = BUILDS[a.poster]
        steps = spec["routes"][a.model] + (spec.get("also_tried", {}).get(a.model, []) if a.also_tried else [])
        print(f"{a.poster}: {spec['title']}\n  steps for {MODELS[a.model]['name']}: {' > '.join(steps)}")
        for s in steps:
            name, _, other = s.partition("@")
            if other and other != a.model:
                continue  # made by the other model in the episode; its take is looked for when a later step needs it
            jobs.append(spec_for(name, a.model))
    comfy = Comfy(a.comfy_url or f"http://127.0.0.1:{a.port}")
    host = urllib.parse.urlparse(comfy.url).hostname
    if host not in ("127.0.0.1", "localhost", "::1"):
        print("Note: ComfyUI is on another computer, so the card and memory readings here are of this one, not that one.")
    a.card = a.card or card_label(a.gpu)
    sampler = Sampler(a.gpu, a.sample_every)
    began = time.time()
    try:
        if a.comfy:
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            comfy.start(os.path.abspath(os.path.expanduser(a.comfy)), a.comfy_python, a.port, a.comfy_flags, a.out, a.models_dir, os.path.join(a.out, f"comfyui-{stamp}.log"))
        missing = comfy.has_files(MODELS[a.model]["files"])
        if missing:
            raise SystemExit(f"ComfyUI can't find {', '.join(missing)}. Run `python get_models.py {a.model}` first, or point --models-dir at the files.")
        print(f"Card: {a.card}. Rows go to {a.csv}")
        made = {}
        for job in jobs:
            make_takes(job, a.model, a, comfy, sampler, made)
    finally:
        comfy.stop()
        sampler.close()
    if a.units_per_hour:
        spent = (time.time() - began) / 3600 * a.units_per_hour
        print(f"This run was on the machine for {(time.time() - began) / 60:.1f} min: about {spent:.2f} units at {a.units_per_hour} an hour, start-up included.")


MODELS = load("models.json")["models"]
PROMPTS, BUILDS = all_prompts()
BUILD_STEPS = {s.partition("@")[0] for b in BUILDS.values() for r in b["routes"].values() for s in r}

if __name__ == "__main__":
    main()
