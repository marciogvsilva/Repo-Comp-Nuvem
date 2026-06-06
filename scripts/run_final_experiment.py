#!/usr/bin/env python3
"""Run the final experiment end-to-end.

This script recreates the benchmark database, starts the FastAPI service locally,
monitors its CPU/RSS memory usage and runs the controlled benchmark.
"""

import argparse
import csv
import json
import os
import signal
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT_DIR = ROOT_DIR / "results" / "benchmark"


def run_command(args: list[str], cwd: Path | None = None, env: dict[str, str] | None = None) -> None:
    subprocess.run(args, cwd=cwd or ROOT_DIR, env=env, check=True)


def wait_for_api(base_url: str, timeout_seconds: float = 30.0) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            with urlopen(f"{base_url}/api/health", timeout=2) as response:
                if response.status == 200:
                    return
        except (URLError, TimeoutError, OSError):
            pass
        time.sleep(0.5)
    raise RuntimeError(f"API did not become ready at {base_url}")


def read_proc_ticks(pid: int) -> int:
    stat = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8")
    parts = stat.split()
    return int(parts[13]) + int(parts[14])


def read_rss_mb(pid: int) -> float:
    status = Path(f"/proc/{pid}/status").read_text(encoding="utf-8")
    for line in status.splitlines():
        if line.startswith("VmRSS:"):
            return int(line.split()[1]) / 1024
    return 0.0


def monitor_process(pid: int, stop_event: threading.Event, samples: list[dict], interval: float = 0.2) -> None:
    clock_ticks = os.sysconf(os.sysconf_names["SC_CLK_TCK"])
    last_ticks = read_proc_ticks(pid)
    last_wall = time.perf_counter()

    while not stop_event.wait(interval):
        try:
            current_ticks = read_proc_ticks(pid)
            current_wall = time.perf_counter()
            rss_mb = read_rss_mb(pid)
        except FileNotFoundError:
            break

        delta_cpu = (current_ticks - last_ticks) / clock_ticks
        delta_wall = current_wall - last_wall
        cpu_percent = (delta_cpu / delta_wall * 100) if delta_wall > 0 else 0.0
        samples.append(
            {
                "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "cpu_percent": cpu_percent,
                "rss_mb": rss_mb,
            }
        )
        last_ticks = current_ticks
        last_wall = current_wall


def summarize_resources(samples: list[dict]) -> dict:
    if not samples:
        return {
            "samples": 0,
            "cpu_avg_percent": 0.0,
            "cpu_max_percent": 0.0,
            "rss_avg_mb": 0.0,
            "rss_max_mb": 0.0,
        }

    cpu = [sample["cpu_percent"] for sample in samples]
    rss = [sample["rss_mb"] for sample in samples]
    return {
        "samples": len(samples),
        "cpu_avg_percent": sum(cpu) / len(cpu),
        "cpu_max_percent": max(cpu),
        "rss_avg_mb": sum(rss) / len(rss),
        "rss_max_mb": max(rss),
    }


def write_resource_files(output_dir: Path, samples: list[dict], summary: dict) -> None:
    (output_dir / "resource_usage.json").write_text(
        json.dumps({"summary": summary, "samples": samples}, indent=2),
        encoding="utf-8",
    )
    with (output_dir / "resource_usage.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["timestamp", "cpu_percent", "rss_mb"])
        writer.writeheader()
        writer.writerows(samples)

    latex_row = (
        "API & {samples} & {cpu_avg_percent:.2f} & {cpu_max_percent:.2f} & "
        "{rss_avg_mb:.2f} & {rss_max_mb:.2f} ".format(**summary)
        + r"\\"
        + "\n"
    )
    (output_dir / "table_resources.tex").write_text(latex_row, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8010)
    parser.add_argument("--products", type=int, default=10000)
    parser.add_argument("--repetitions", type=int, default=5)
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    db_path = output_dir / "products.db"
    if db_path.exists():
        db_path.unlink()

    run_command([sys.executable, str(ROOT_DIR / "scripts" / "populate_db.py"), str(db_path), str(args.products)])

    env = os.environ.copy()
    env["DB_PATH"] = str(db_path.resolve())
    server = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "api:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(args.port),
            "--log-level",
            "warning",
        ],
        cwd=ROOT_DIR / "src",
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    samples: list[dict] = []
    stop_event = threading.Event()
    monitor_thread = threading.Thread(target=monitor_process, args=(server.pid, stop_event, samples), daemon=True)
    monitor_thread.start()

    try:
        base_url = f"http://127.0.0.1:{args.port}"
        wait_for_api(base_url)
        run_command(
            [
                sys.executable,
                str(ROOT_DIR / "scripts" / "benchmark_api.py"),
                "--base-url",
                base_url,
                "--output-dir",
                str(output_dir),
                "--repetitions",
                str(args.repetitions),
                "--products",
                str(args.products),
            ]
        )
    finally:
        stop_event.set()
        monitor_thread.join(timeout=3)
        if server.poll() is None:
            server.send_signal(signal.SIGTERM)
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=5)

    resource_summary = summarize_resources(samples)
    resource_summary.update(
        {
            "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "products": args.products,
            "repetitions": args.repetitions,
        }
    )
    write_resource_files(output_dir, samples, resource_summary)
    print(json.dumps(resource_summary, indent=2))


if __name__ == "__main__":
    main()
