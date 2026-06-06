#!/usr/bin/env python3
"""Run controlled HTTP benchmarks and generate summarized results.

The script expects the API to be running and reachable through BASE_URL.
It writes raw measurements, CSV summaries and LaTeX table fragments to results/.
"""

import argparse
import asyncio
import csv
import json
import math
import statistics
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import httpx


@dataclass(frozen=True)
class Scenario:
    key: str
    label: str
    users: int
    requests_per_user: int


@dataclass(frozen=True)
class Target:
    key: str
    group: str
    label: str
    method: str
    path: str
    headers: dict[str, str]


SCENARIOS = [
    Scenario("C1", "Baixa", 10, 8),
    Scenario("C2", "Media", 50, 6),
    Scenario("C3", "Alta", 100, 4),
]

TARGETS = [
    Target("offset_deep", "pagination", "Offset", "GET", "/v1/produtos?limit=50&offset=9000", {}),
    Target("cursor_deep", "pagination", "Cursor", "GET", "/v1/produtos/cursor?limit=50&cursor=9000", {}),
    Target("uri_v2", "versioning", "URI v2", "GET", "/v2/produtos?limit=50&offset=0", {}),
    Target(
        "header_v2",
        "versioning",
        "Header v2",
        "GET",
        "/produtos?limit=50&offset=0",
        {"Accept": "application/vnd.api.v2+json"},
    ),
]


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * pct
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[int(position)]
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def mean(values: Iterable[float]) -> float:
    values = list(values)
    return statistics.mean(values) if values else 0.0


def stdev(values: Iterable[float]) -> float:
    values = list(values)
    return statistics.stdev(values) if len(values) >= 2 else 0.0


def ci95(values: Iterable[float]) -> float:
    values = list(values)
    if len(values) < 2:
        return 0.0
    # t critical for df=4 is 2.776. Use normal approximation for larger samples.
    t_critical = 2.776 if len(values) == 5 else 1.96
    return t_critical * statistics.stdev(values) / math.sqrt(len(values))


async def wait_for_api(base_url: str, timeout_seconds: float = 30.0) -> None:
    deadline = time.perf_counter() + timeout_seconds
    async with httpx.AsyncClient(timeout=2.0) as client:
        while time.perf_counter() < deadline:
            try:
                response = await client.get(f"{base_url}/api/health")
                if response.status_code == 200:
                    return
            except httpx.HTTPError:
                pass
            await asyncio.sleep(0.5)
    raise RuntimeError(f"API did not become ready at {base_url}")


async def single_request(client: httpx.AsyncClient, base_url: str, target: Target) -> dict:
    start = time.perf_counter()
    status_code = 0
    ok = False
    error = None
    try:
        response = await client.request(target.method, f"{base_url}{target.path}", headers=target.headers)
        status_code = response.status_code
        ok = 200 <= status_code < 400
        # Force JSON parsing to catch malformed responses during the benchmark.
        response.json()
    except Exception as exc:  # noqa: BLE001 - benchmark records all failures.
        error = type(exc).__name__
    latency_ms = (time.perf_counter() - start) * 1000
    return {
        "latency_ms": latency_ms,
        "status_code": status_code,
        "ok": ok,
        "error": error,
    }


async def run_once(base_url: str, scenario: Scenario, target: Target, repetition: int) -> dict:
    limits = httpx.Limits(max_connections=scenario.users, max_keepalive_connections=scenario.users)
    timeout = httpx.Timeout(15.0)
    start = time.perf_counter()

    async with httpx.AsyncClient(timeout=timeout, limits=limits) as client:
        tasks = []
        for _ in range(scenario.users):
            for _ in range(scenario.requests_per_user):
                tasks.append(single_request(client, base_url, target))
        results = await asyncio.gather(*tasks)

    elapsed = time.perf_counter() - start
    latencies = [item["latency_ms"] for item in results if item["ok"]]
    total = len(results)
    success = sum(1 for item in results if item["ok"])
    errors = total - success

    return {
        "scenario": scenario.key,
        "load_label": scenario.label,
        "users": scenario.users,
        "requests_per_user": scenario.requests_per_user,
        "target": target.key,
        "target_label": target.label,
        "group": target.group,
        "path": target.path,
        "repetition": repetition,
        "total_requests": total,
        "success_requests": success,
        "error_requests": errors,
        "error_rate_pct": (errors / total * 100) if total else 0.0,
        "elapsed_seconds": elapsed,
        "rps": total / elapsed if elapsed else 0.0,
        "latency_avg_ms": mean(latencies),
        "latency_min_ms": min(latencies) if latencies else 0.0,
        "latency_max_ms": max(latencies) if latencies else 0.0,
        "latency_p90_ms": percentile(latencies, 0.90),
        "latency_p95_ms": percentile(latencies, 0.95),
        "latency_p99_ms": percentile(latencies, 0.99),
    }


def summarize(raw_rows: list[dict]) -> list[dict]:
    grouped: dict[tuple[str, str], list[dict]] = {}
    scenario_order = {scenario.key: index for index, scenario in enumerate(SCENARIOS)}
    target_order = {target.key: index for index, target in enumerate(TARGETS)}

    for row in raw_rows:
        grouped.setdefault((row["scenario"], row["target"]), []).append(row)

    ordered_groups = sorted(
        grouped.items(),
        key=lambda item: (scenario_order.get(item[0][0], 99), target_order.get(item[0][1], 99)),
    )

    summary = []
    for (scenario, target), rows in ordered_groups:
        first = rows[0]
        avg_values = [row["latency_avg_ms"] for row in rows]
        p95_values = [row["latency_p95_ms"] for row in rows]
        p99_values = [row["latency_p99_ms"] for row in rows]
        rps_values = [row["rps"] for row in rows]
        error_values = [row["error_rate_pct"] for row in rows]
        summary.append(
            {
                "scenario": scenario,
                "load_label": first["load_label"],
                "users": first["users"],
                "target": target,
                "target_label": first["target_label"],
                "group": first["group"],
                "path": first["path"],
                "repetitions": len(rows),
                "requests_per_repetition": first["total_requests"],
                "latency_avg_mean_ms": mean(avg_values),
                "latency_avg_sd_ms": stdev(avg_values),
                "latency_avg_ci95_ms": ci95(avg_values),
                "latency_p95_mean_ms": mean(p95_values),
                "latency_p99_mean_ms": mean(p99_values),
                "rps_mean": mean(rps_values),
                "rps_sd": stdev(rps_values),
                "error_rate_mean_pct": mean(error_values),
            }
        )
    return summary


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def fmt(value: float) -> str:
    return f"{value:.2f}"


def write_latex_tables(output_dir: Path, summary: list[dict]) -> None:
    pagination_rows = [row for row in summary if row["group"] == "pagination"]
    versioning_rows = [row for row in summary if row["group"] == "versioning"]

    def table_rows(rows: list[dict]) -> str:
        lines = []
        for row in rows:
            lines.append(
                "{} & {} & {} & {} & {} & {} & {} & {} \\\\".format(
                    row["scenario"],
                    row["target_label"],
                    fmt(row["latency_avg_mean_ms"]),
                    fmt(row["latency_avg_sd_ms"]),
                    fmt(row["latency_avg_ci95_ms"]),
                    fmt(row["latency_p95_mean_ms"]),
                    fmt(row["rps_mean"]),
                    fmt(row["error_rate_mean_pct"]),
                )
            )
        return "\n".join(lines)

    (output_dir / "table_pagination.tex").write_text(table_rows(pagination_rows) + "\n", encoding="utf-8")
    (output_dir / "table_versioning.tex").write_text(table_rows(versioning_rows) + "\n", encoding="utf-8")


def write_svg_chart(output_dir: Path, summary: list[dict]) -> None:
    width = 1100
    height = 680
    margin_left = 95
    margin_bottom = 130
    margin_top = 45
    plot_width = width - margin_left - 35
    plot_height = height - margin_top - margin_bottom
    max_value = max(row["latency_avg_mean_ms"] for row in summary) * 1.12
    bar_gap = 8
    bar_width = (plot_width - bar_gap * (len(summary) - 1)) / len(summary)
    colors = {
        "offset_deep": "#3b82f6",
        "cursor_deep": "#10b981",
        "uri_v2": "#f59e0b",
        "header_v2": "#ef4444",
    }

    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<text x="550" y="28" text-anchor="middle" font-family="Arial" font-size="20" font-weight="700">Latência média por cenário e estratégia</text>',
        f'<line x1="{margin_left}" y1="{margin_top}" x2="{margin_left}" y2="{margin_top + plot_height}" stroke="#334155"/>',
        f'<line x1="{margin_left}" y1="{margin_top + plot_height}" x2="{margin_left + plot_width}" y2="{margin_top + plot_height}" stroke="#334155"/>',
    ]

    for tick in range(0, 6):
        value = max_value * tick / 5
        y = margin_top + plot_height - (value / max_value * plot_height)
        svg.append(f'<line x1="{margin_left - 5}" y1="{y:.2f}" x2="{margin_left + plot_width}" y2="{y:.2f}" stroke="#e2e8f0"/>')
        svg.append(f'<text x="{margin_left - 10}" y="{y + 4:.2f}" text-anchor="end" font-family="Arial" font-size="12" fill="#475569">{value:.0f}</text>')

    for index, row in enumerate(summary):
        x = margin_left + index * (bar_width + bar_gap)
        h = row["latency_avg_mean_ms"] / max_value * plot_height
        y = margin_top + plot_height - h
        color = colors[row["target"]]
        svg.append(f'<rect x="{x:.2f}" y="{y:.2f}" width="{bar_width:.2f}" height="{h:.2f}" fill="{color}" rx="3"/>')
        svg.append(f'<text x="{x + bar_width / 2:.2f}" y="{y - 6:.2f}" text-anchor="middle" font-family="Arial" font-size="11" fill="#0f172a">{row["latency_avg_mean_ms"]:.0f}</text>')
        label = f'{row["scenario"]} {row["target_label"]}'
        svg.append(f'<text transform="translate({x + bar_width / 2:.2f},{margin_top + plot_height + 18}) rotate(55)" text-anchor="start" font-family="Arial" font-size="12" fill="#334155">{label}</text>')

    svg.append(f'<text x="24" y="{margin_top + plot_height / 2:.2f}" transform="rotate(-90 24 {margin_top + plot_height / 2:.2f})" text-anchor="middle" font-family="Arial" font-size="14" fill="#334155">Latência média (ms)</text>')
    svg.append("</svg>")
    (output_dir / "latency_chart.svg").write_text("\n".join(svg) + "\n", encoding="utf-8")


def write_markdown(output_dir: Path, summary: list[dict], metadata: dict) -> None:
    lines = [
        "# Benchmark Results",
        "",
        f"Generated at: `{metadata['generated_at']}`",
        f"Base URL: `{metadata['base_url']}`",
        f"Products: `{metadata['products']}`",
        f"Repetitions per scenario/target: `{metadata['repetitions']}`",
        "",
        "| Scenario | Target | Avg ms | SD | IC95 | P95 ms | RPS | Error % |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in summary:
        lines.append(
            f"| {row['scenario']} | {row['target_label']} | {fmt(row['latency_avg_mean_ms'])} | "
            f"{fmt(row['latency_avg_sd_ms'])} | {fmt(row['latency_avg_ci95_ms'])} | "
            f"{fmt(row['latency_p95_mean_ms'])} | {fmt(row['rps_mean'])} | {fmt(row['error_rate_mean_pct'])} |"
        )
    (output_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--output-dir", default="results/benchmark")
    parser.add_argument("--repetitions", type=int, default=5)
    parser.add_argument("--products", type=int, default=10000)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    await wait_for_api(args.base_url)

    raw_rows = []
    for scenario in SCENARIOS:
        for target in TARGETS:
            for repetition in range(1, args.repetitions + 1):
                print(f"Running {scenario.key} {target.label} repetition {repetition}/{args.repetitions}", flush=True)
                raw_rows.append(await run_once(args.base_url, scenario, target, repetition))
                await asyncio.sleep(0.2)

    summary = summarize(raw_rows)
    metadata = {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "base_url": args.base_url,
        "products": args.products,
        "repetitions": args.repetitions,
        "scenarios": [scenario.__dict__ for scenario in SCENARIOS],
        "targets": [target.__dict__ for target in TARGETS],
    }

    (output_dir / "raw.json").write_text(json.dumps({"metadata": metadata, "runs": raw_rows}, indent=2), encoding="utf-8")
    (output_dir / "summary.json").write_text(json.dumps({"metadata": metadata, "summary": summary}, indent=2), encoding="utf-8")
    write_csv(output_dir / "raw.csv", raw_rows)
    write_csv(output_dir / "summary.csv", summary)
    write_latex_tables(output_dir, summary)
    write_svg_chart(output_dir, summary)
    write_markdown(output_dir, summary, metadata)
    print(f"Wrote benchmark results to {output_dir}")


if __name__ == "__main__":
    asyncio.run(main())
