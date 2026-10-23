"""Recorded sd.cpp run on Windows; Python standard library, no torch import."""
import argparse
import ctypes
from ctypes import wintypes as wt
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import threading
import time
if not getattr(sys,'frozen',False):sys.path.insert(0,str(Path(__file__).resolve().parent))
from process_env import external_dll_search

ROOT = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[1]))
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def configured(config, key):
    p = Path(config[key])
    return p if p.is_absolute() else ROOT / p


def command(config, case, prompt, image):
    return [str(configured(config, "sd_cli")), "--diffusion-model", str(configured(config, "diffusion_model")),
            "--llm", str(configured(config, "llm")), "--vae", str(configured(config, "vae")),
            "--prompt-file", str(prompt), "--steps", str(case.get("steps",16)), "--cfg-scale", str(case.get("cfg_scale",1.0)),
            "--sampling-method", "euler", "--scheduler", "discrete", "-W", str(case["width"]),
            "-H", str(case["height"]), "-s", str(case["seed"]), "--flash-attn", "off,diffusion=on",
            "--max-vram", str(config.get("max_vram_gib", 6)), "--mmap", "--offload-to-cpu",
            "-o", str(image), "-v"]


def portable_command(config, case, prompt, image):
    c = command(config, case, prompt, image)
    for key, replacement in [("sd_cli", "runtime/sd-cli.exe"), ("diffusion_model", "models/flux3-image-klein-Q4_0.gguf"),
                             ("llm", "models/Qwen3VL-4B-Instruct-Q4_K_M.gguf"), ("vae", "models/flux2-vae.safetensors")]:
        c[c.index(str(configured(config, key)))] = replacement
    for path in [prompt,image]:
        try: alias=path.relative_to(ROOT).as_posix()
        except ValueError: alias='outputs/'+image.parent.name+'/'+path.name
        c[c.index(str(path))]=alias
    return c


class Memory(ctypes.Structure):
    _fields_ = [("length", wt.DWORD), ("load", wt.DWORD)] + [(x, ctypes.c_ulonglong) for x in
                ["total", "available", "commit_limit", "commit_available", "vtotal", "vavailable", "extended"]]


class ProcessMemory(ctypes.Structure):
    _fields_ = [("cb", wt.DWORD), ("faults", wt.DWORD)] + [(x, ctypes.c_size_t) for x in
                ["peak_working_set", "working_set", "quota_peak_paged", "quota_paged", "quota_peak_nonpaged",
                 "quota_nonpaged", "pagefile", "peak_pagefile", "private"]]


def memory(child):
    m = Memory()
    m.length = ctypes.sizeof(m)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)):
        raise ctypes.WinError()
    pm = ProcessMemory()
    pm.cb = ctypes.sizeof(pm)
    get_mem = ctypes.windll.psapi.GetProcessMemoryInfo
    get_mem.argtypes = [wt.HANDLE, ctypes.c_void_p, wt.DWORD]
    ok = get_mem(wt.HANDLE(int(child._handle)), ctypes.byref(pm), pm.cb)
    return {"available_mib": round(m.available / 2**20),
            "system_commit_percent": round(100 * (1 - m.commit_available / m.commit_limit), 2),
            "engine_private_mib": round(pm.private / 2**20) if ok else None,
            "engine_peak_working_set_mib": round(pm.peak_working_set / 2**20) if ok else None}


def gpu_memory():
    with external_dll_search():
        r = subprocess.run(["nvidia-smi", "--query-gpu=memory.used,memory.free", "--format=csv,noheader,nounits"],
                           capture_output=True, text=True, timeout=10, creationflags=CREATE_NO_WINDOW)
    parts = r.stdout.strip().split(",")
    if r.returncode or len(parts) != 2:
        raise RuntimeError("nvidia-smi memory query failed")
    return int(parts[0]), int(parts[1])


def redact(text, config):
    replacements = [(str(configured(config, k)), v) for k, v in
                    [("sd_cli", "runtime/sd-cli.exe"), ("diffusion_model", "models/flux3-image-klein-Q4_0.gguf"),
                     ("llm", "models/Qwen3VL-4B-Instruct-Q4_K_M.gguf"), ("vae", "models/flux2-vae.safetensors")]]
    replacements += [(str(configured(config, "sd_cli").parent), "runtime"), (str(ROOT), ".")]
    if config.get("output_root"):
        replacements.append((str(Path(config["output_root"])),"outputs"))
    for old, new in sorted(replacements, key=lambda x: -len(x[0])):
        for spelling in {old, old.replace("\\", "/"), old.replace("/", "\\")}:
            text = text.replace(spelling, new)
    return text


def run(config, case, run_id):
    if os.name != "nt":
        raise SystemExit("This measured profile supports Windows only")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,79}", run_id):
        raise SystemExit("Use a new lowercase ASCII run id")
    subdir=config.get("results_subdir","results")
    if subdir not in {"results","outputs"}:
        raise ValueError("Unsupported output directory")
    base=Path(config["output_root"]) if config.get("output_root") else ROOT / subdir
    output = base / run_id
    output.mkdir(parents=True, exist_ok=False)
    image = output / "image.png"
    prompt = Path(case["prompt_file"])
    if not prompt.is_absolute():prompt=ROOT/prompt
    cmd = command(config, case, prompt, image)
    env = os.environ.copy()
    env["PATH"] = ";".join(str(configured(config, k)) for k in ["cuda_runtime_dir", "cuda_bin"] if config.get(k)) + ";" + env.get("PATH", "")
    env["OMP_NUM_THREADS"] = "8"
    record = {"schema": 1, "run_id": run_id, "case_id": case["id"], "title_ru": case["title_ru"],
              "category": case["category"], "width": case["width"], "height": case["height"], "seed": case["seed"],
              "steps": case.get("steps",16), "cfg_scale": case.get("cfg_scale",1.0), "sampler": "euler", "scheduler": "discrete",
              "flash_attention": "off,diffusion=on", "max_vram_gib": config.get("max_vram_gib", 6),
              "parameter_storage": "cpu", "mmap": True, "prompt_file": portable_command(config,case,prompt,image)[portable_command(config,case,prompt,image).index("--prompt-file")+1],
              "omp_num_threads": 8,
              "prompt_sha256": digest(prompt), "expected_text": case.get("expected_text", []),
              "command": portable_command(config, case, prompt, image),
              "started_at": dt.datetime.now(dt.timezone.utc).isoformat(), "status": "RUNNING",
              "gpu_peak_scope": "whole GPU including desktop, sampled every ~1 second",
              "timing_scope": "new sd-cli process through its exit, includes loading and PNG save; excludes queue and launcher",
              "file_cache": "OS cache not flushed; fresh process does not mean cold files"}
    save(output / "record.json", record)
    raw_lines = []
    start = time.perf_counter()
    child = None
    failure = None
    bad_since = None
    samples = []
    exited = {}
    try:
        with external_dll_search():
            child = subprocess.Popen(cmd, cwd=ROOT, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                     stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace",
                                     creationflags=CREATE_NO_WINDOW)
        def clock_exit():
            child.wait()
            exited["seconds"] = time.perf_counter() - start
        exit_watcher = threading.Thread(target=clock_exit, daemon=True)
        exit_watcher.start()
        def drain():
            with (output / "live.log").open("w",encoding="utf-8",newline="\n") as live:
                for line in child.stdout:
                    raw_lines.append(line)
                    live.write(redact(line,config));live.flush()
        reader = threading.Thread(target=drain, daemon=True)
        reader.start()
        with (output / "sensors.jsonl").open("w", encoding="utf-8") as sensors:
            while child.poll() is None:
                sample = memory(child)
                sample["gpu_used_mib"], sample["gpu_free_mib"] = gpu_memory()
                sample["elapsed_seconds"] = round(time.perf_counter() - start, 3)
                samples.append(sample)
                sensors.write(json.dumps(sample) + "\n")
                sensors.flush()
                bad = sample["available_mib"] < 3072 or sample["system_commit_percent"] >= 93 or sample["gpu_used_mib"] > 7680
                bad_since = (bad_since or time.perf_counter()) if bad else None
                if bad_since and time.perf_counter() - bad_since >= 5:
                    failure = "MEMORY_GUARD"
                    break
                if time.perf_counter() - start > config.get("timeout_seconds", 900):
                    failure = "TIMEOUT"
                    break
                time.sleep(0.8)
        if failure and child.poll() is None:
            child.kill()  # sd-cli is the direct owned process, not a shared server
        child.wait(timeout=30)
        exit_watcher.join(timeout=5)
        process_seconds = exited.get("seconds", time.perf_counter() - start)
        reader.join(timeout=10)
        record["returncode"] = child.returncode
        record["seconds"] = round(process_seconds, 4)
        record["status"] = "PASS" if child.returncode == 0 and image.is_file() and not failure else "FAIL"
    except BaseException as error:
        failure = type(error).__name__
        record["error"] = redact(str(error), config)
        record["status"] = "ERROR"
    finally:
        if child is not None and child.poll() is None:
            child.kill()
            child.wait(timeout=30)
        log = redact("".join(raw_lines), config)
        log = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", log)
        (output / "engine.log").write_text(log, encoding="utf-8")
        for key, pattern in {"sampling_seconds": r"sampling completed, taking ([\d.]+)s",
                             "engine_generate_seconds": r"generate_image completed in ([\d.]+)s",
                             "vae_seconds": r"decode_first_stage completed, taking ([\d.]+)s"}.items():
            matches = re.findall(pattern, log)
            record[key] = float(matches[-1]) if matches else None
        record.update({"ended_at": dt.datetime.now(dt.timezone.utc).isoformat(), "stop_reason": failure,
                       "peak_gpu_used_mib": max((s["gpu_used_mib"] for s in samples), default=None),
                       "minimum_available_mib": min((s["available_mib"] for s in samples), default=None),
                       "peak_engine_private_mib": max((s["engine_private_mib"] or 0 for s in samples), default=None),
                       "peak_system_commit_percent": max((s["system_commit_percent"] for s in samples), default=None),
                       "sample_count": len(samples)})
        if image.exists():
            record["image_sha256"] = digest(image)
            record["image_bytes"] = image.stat().st_size
        save(output / "record.json", record)
    print(json.dumps({k: record.get(k) for k in ["run_id", "status", "seconds", "peak_gpu_used_mib", "stop_reason"]}), flush=True)
    return 0 if record["status"] == "PASS" else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", default="config.local.json")
    ap.add_argument("--case", required=True)
    ap.add_argument("--cases-file", default=str(ROOT / "cases.json"))
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    config = json.loads(Path(args.config).read_text(encoding="utf-8-sig"))
    cases = json.loads(Path(args.cases_file).read_text(encoding="utf-8"))["cases"]
    case = next(c for c in cases if c["id"] == args.case)
    if args.dry_run:
        image = ROOT / "results" / args.run_id / "image.png"
        print(json.dumps(portable_command(config, case, ROOT / case["prompt_file"], image), ensure_ascii=False, indent=2))
        return 0
    return run(config, case, args.run_id)


if __name__ == "__main__":
    raise SystemExit(main())
