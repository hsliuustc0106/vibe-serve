from __future__ import annotations

import html
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ReportResult:
    report_path: Path
    data_path: Path


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_json_if_exists(path: Path, default: Any) -> Any:
    if not path.is_file():
        return default
    return _read_json(path)


def _read_text_if_exists(path: Path) -> str:
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def _fmt(value: Any) -> str:
    if value is None:
        return "unknown"
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


def _pct(value: Any) -> str:
    if value is None:
        return "unknown"
    try:
        return f"{float(value):+.2f}%"
    except (TypeError, ValueError):
        return str(value)


def _status_class(status: Any) -> str:
    text = str(status or "unknown").lower()
    if text in {"passed", "measured", "improved"}:
        return "passed"
    if text in {"failed", "regressed"}:
        return "failed"
    if text == "unmeasured":
        return "warn"
    return "unknown"


def _parse_progress_events(progress_text: str, *, limit: int = 80) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    body: list[str] = []
    for line in progress_text.splitlines():
        if line.startswith("## Round "):
            if current is not None:
                current["body"] = "\n".join(body).strip()
                events.append(current)
            title = line.removeprefix("## ").strip()
            round_part, _, agent_part = title.partition(" — ")
            round_number: int | None = None
            try:
                round_number = int(round_part.removeprefix("Round ").split()[0])
            except (IndexError, ValueError):
                round_number = None
            agent = agent_part.split(" (", 1)[0].strip() or "Event"
            current = {"round": round_number, "agent": agent, "title": title}
            body = []
        elif current is not None:
            body.append(line)
    if current is not None:
        current["body"] = "\n".join(body).strip()
        events.append(current)
    return events[-limit:]


def _load_usage(log_dir: Path) -> list[dict[str, Any]]:
    usage: list[dict[str, Any]] = []
    for path in sorted(log_dir.glob("usage*.json")):
        data = _read_json_if_exists(path, None)
        if data is None:
            continue
        usage.append({"file": path.name, "data": data})
    for path in sorted(log_dir.glob("usage*.jsonl")):
        rows = []
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                rows.append({"raw": line})
        usage.append({"file": path.name, "data": rows})
    return usage


def _artifact_list(log_dir: Path) -> list[str]:
    if not log_dir.is_dir():
        return []
    return sorted(
        str(path.relative_to(log_dir))
        for path in log_dir.rglob("*")
        if path.is_file()
    )


def load_report_data(exp_dir: Path) -> dict[str, Any]:
    exp_dir = exp_dir.expanduser().resolve()
    log_dir = exp_dir / "logs"
    workspace = exp_dir / "workspace"
    summary = _read_json_if_exists(log_dir / "round_summary.json", {})
    rounds = _read_json_if_exists(log_dir / "rounds.json", [])
    progress = _read_text_if_exists(workspace / "progress.md")
    roadmap = _read_text_if_exists(workspace / "roadmap.md")
    return {
        "source_experiment": str(exp_dir),
        "benchmark": summary.get("benchmark", {}) if isinstance(summary, dict) else {},
        "rounds": summary.get("rounds", []) if isinstance(summary, dict) else [],
        "best_round": summary.get("best_round") if isinstance(summary, dict) else None,
        "global_objective_status": summary.get("global_objective_status") if isinstance(summary, dict) else None,
        "global_objective_reason": summary.get("global_objective_reason") if isinstance(summary, dict) else None,
        "round_records": rounds if isinstance(rounds, list) else [],
        "events": _parse_progress_events(progress),
        "roadmap": roadmap,
        "usage": _load_usage(log_dir),
        "artifacts": _artifact_list(log_dir),
    }


def build_agent_report(
    exp_dir: Path,
    *,
    output_path: Path | None = None,
    data_path: Path | None = None,
) -> ReportResult:
    exp_dir = exp_dir.expanduser().resolve()
    if not exp_dir.is_dir():
        raise FileNotFoundError(f"experiment directory not found: {exp_dir}")
    data = load_report_data(exp_dir)
    reports_dir = exp_dir / "reports"
    report_path = (output_path or reports_dir / "report.html").expanduser().resolve()
    json_path = (data_path or reports_dir / "report.json").expanduser().resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    report_path.write_text(render_report_html(data), encoding="utf-8")
    return ReportResult(report_path=report_path, data_path=json_path)


def render_report_html(data: dict[str, Any]) -> str:
    rounds = data.get("rounds") if isinstance(data.get("rounds"), list) else []
    best = data.get("best_round") if isinstance(data.get("best_round"), dict) else None
    benchmark = data.get("benchmark") if isinstance(data.get("benchmark"), dict) else {}
    events = data.get("events") if isinstance(data.get("events"), list) else []
    usage = data.get("usage") if isinstance(data.get("usage"), list) else []
    artifacts = data.get("artifacts") if isinstance(data.get("artifacts"), list) else []

    return "\n".join(
        [
            "<!doctype html>",
            '<html lang="en">',
            "<head>",
            '<meta charset="utf-8">',
            '<meta name="viewport" content="width=device-width, initial-scale=1">',
            f"<title>VibeServe Report - {html.escape(Path(str(data.get('source_experiment', 'run'))).name)}</title>",
            "<style>",
            _CSS,
            "</style>",
            "</head>",
            "<body>",
            "<main>",
            _summary_section(data, benchmark, best, rounds),
            _visuals_section(rounds, benchmark),
            _rounds_section(rounds),
            _events_section(events),
            _details_section("Recent Usage", _json_pre(usage), open_by_default=False),
            _details_section("Benchmark Artifacts", _artifact_markup(artifacts), open_by_default=False),
            "</main>",
            "</body>",
            "</html>",
        ]
    )


def _summary_section(
    data: dict[str, Any],
    benchmark: dict[str, Any],
    best: dict[str, Any] | None,
    rounds: list[Any],
) -> str:
    source = html.escape(str(data.get("source_experiment", "unknown")))
    baseline_engine = html.escape(_fmt(benchmark.get("baseline_engine")))
    primary_metric_raw = benchmark.get("primary_metric")
    primary_metric = html.escape(_fmt(primary_metric_raw))
    metric_label = html.escape(str(primary_metric_raw)) if primary_metric_raw else "Metric Value"
    baseline_value = html.escape(_fmt(benchmark.get("baseline_value")))
    best_round = html.escape(_fmt(best.get("round") if best else None))
    best_metric = html.escape(_fmt(best.get("metric_value") if best else None))
    latest = rounds[-1] if rounds and isinstance(rounds[-1], dict) else {}
    latest_global = html.escape(
        _fmt(
            data.get("global_objective_status")
            or latest.get("global_objective_status")
            or latest.get("status")
        )
    )
    latest_reason = html.escape(
        _fmt(
            data.get("global_objective_reason")
            or latest.get("global_objective_reason")
            or (
                f"fallback from latest round status: {latest.get('status')}"
                if latest.get("status")
                else None
            )
        )
    )
    return f"""
<section class="top">
  <div>
    <h1>Agent Run Report</h1>
    <p class="muted">{source}</p>
  </div>
  <div class="stats">
    <div><span>Rounds</span><strong>{len(rounds)}</strong></div>
    <div><span>Best Round</span><strong>{best_round}</strong></div>
    <div><span>{metric_label}</span><strong>{best_metric}</strong></div>
    <div><span>Latest Global</span><strong>{latest_global}</strong></div>
    <div><span>Baseline</span><strong>{baseline_value}</strong><small>{baseline_engine}</small></div>
  </div>
  <p class="muted">Primary metric: {primary_metric}</p>
  <p class="muted">Global objective reason: {latest_reason}</p>
</section>
"""


def _visuals_section(rounds: list[Any], benchmark: dict[str, Any]) -> str:
    return f"""
<section>
  <h2>Run Visualization</h2>
  <div class="viz-grid">
    <div>
      <h3>Pass/Fail Timeline</h3>
      {_timeline_markup(rounds)}
    </div>
    <div>
      <h3>Throughput / Metric Trend</h3>
      {_trend_svg(rounds, benchmark)}
    </div>
  </div>
</section>
"""


def _timeline_markup(rounds: list[Any]) -> str:
    parts = []
    for row in rounds:
        if not isinstance(row, dict):
            continue
        round_no = html.escape(_fmt(row.get("round")))
        status = str(row.get("status") or "unknown")
        global_status = str(row.get("global_objective_status") or "unknown")
        title = (
            f"Round {round_no}: task={status}; global={global_status}; "
            f"metric={_fmt(row.get('metric_value'))}; {row.get('global_objective_reason') or ''}"
        )
        parts.append(
            f'<span class="tick {_status_class(global_status if global_status != "unknown" else status)}" '
            f'title="{html.escape(title)}">{round_no}</span>'
        )
    if not parts:
        return '<p class="empty">No round data found.</p>'
    return f'<div class="timeline">{"".join(parts)}</div>'


def _trend_svg(rounds: list[Any], benchmark: dict[str, Any]) -> str:
    points: list[tuple[int, float]] = []
    for row in rounds:
        if not isinstance(row, dict):
            continue
        try:
            value = float(row.get("metric_value"))
        except (TypeError, ValueError):
            continue
        try:
            round_no = int(row.get("round"))
        except (TypeError, ValueError):
            round_no = len(points) + 1
        points.append((round_no, value))
    if not points:
        return '<p class="empty">No benchmark metrics recorded yet.</p>'
    width = 520
    height = 220
    pad_l = 42
    pad_r = 18
    pad_t = 18
    pad_b = 34
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    x_min, x_max = min(xs), max(xs)
    y_min, y_max = min(ys), max(ys)
    if y_min == y_max:
        y_min = 0.0
        y_max = max(1.0, y_max)

    def sx(x: int) -> float:
        if x_max == x_min:
            return width / 2
        return pad_l + (x - x_min) / (x_max - x_min) * (width - pad_l - pad_r)

    def sy(y: float) -> float:
        return pad_t + (y_max - y) / (y_max - y_min) * (height - pad_t - pad_b)

    polyline = " ".join(f"{sx(x):.1f},{sy(y):.1f}" for x, y in points)
    dots = "\n".join(
        f'<circle cx="{sx(x):.1f}" cy="{sy(y):.1f}" r="4"><title>Round {x}: {y:.3f}</title></circle>'
        for x, y in points
    )
    primary = html.escape(_fmt(benchmark.get("primary_metric")))
    return f"""
<svg class="trend" viewBox="0 0 {width} {height}" role="img" aria-label="{primary} trend">
  <line x1="{pad_l}" y1="{height-pad_b}" x2="{width-pad_r}" y2="{height-pad_b}" />
  <line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{height-pad_b}" />
  <text x="{pad_l}" y="14">{primary}</text>
  <text x="4" y="{pad_t+4}">{y_max:.2f}</text>
  <text x="4" y="{height-pad_b+4}">{y_min:.2f}</text>
  <polyline points="{polyline}" />
  {dots}
</svg>
"""


def _rounds_section(rounds: list[Any]) -> str:
    rows = []
    for row in rounds:
        if not isinstance(row, dict):
            continue
        status = html.escape(str(row.get("status", "unknown")))
        rows.append(
            "<tr>"
            f"<td>{html.escape(_fmt(row.get('round')))}</td>"
            f'<td><span class="status {_status_class(status)}">{status}</span></td>'
            f'<td><span class="status {_status_class(row.get("global_objective_status"))}">{html.escape(_fmt(row.get("global_objective_status")))}</span></td>'
            f"<td>{html.escape(_fmt(row.get('metric_name')))}</td>"
            f"<td>{html.escape(_fmt(row.get('metric_value')))}</td>"
            f"<td>{html.escape(_fmt(row.get('metric_source')))}</td>"
            f"<td>{html.escape(_fmt(row.get('judge_success_rate')))}</td>"
            f"<td>{html.escape(_fmt(row.get('baseline_value')))}</td>"
            f"<td>{html.escape(_pct(row.get('delta_pct')))}</td>"
            f"<td>{html.escape(_fmt(row.get('commit')))}</td>"
            "</tr>"
        )
    body = "\n".join(rows) or '<tr><td colspan="10" class="empty">No round data found.</td></tr>'
    return f"""
<section>
  <h2>Round Progress</h2>
  <div class="table-wrap">
    <table>
      <thead><tr><th>Round</th><th>Task</th><th>Global</th><th>Metric</th><th>Value</th><th>Source</th><th>Success Rate</th><th>Baseline</th><th>Delta</th><th>Commit</th></tr></thead>
      <tbody>{body}</tbody>
    </table>
  </div>
</section>
"""


def _events_section(events: list[Any]) -> str:
    if not events:
        body = '<p class="empty">No progress events found.</p>'
    else:
        parts = []
        last_agent = None
        for event in events:
            if not isinstance(event, dict):
                continue
            agent = str(event.get("agent") or "Event")
            split = " split" if last_agent is not None and agent != last_agent else ""
            last_agent = agent
            agent_words = agent.lower().split()
            agent_class = agent_words[0] if agent_words else "event"
            parts.append(
                f'<article class="event {agent_class}{split}">'
                f"<header><span>{html.escape(agent)}</span><strong>{html.escape(str(event.get('title', 'Event')))}</strong></header>"
                f"<pre>{html.escape(str(event.get('body') or ''))}</pre>"
                "</article>"
            )
        body = "\n".join(parts)
    return f"""
<section>
  <h2>Recent Agent Events</h2>
  <div class="events">{body}</div>
</section>
"""


def _details_section(title: str, body: str, *, open_by_default: bool) -> str:
    open_attr = " open" if open_by_default else ""
    return f"""
<details{open_attr}>
  <summary>{html.escape(title)}</summary>
  {body}
</details>
"""


def _json_pre(value: Any) -> str:
    return f"<pre>{html.escape(json.dumps(value, indent=2))}</pre>"


def _artifact_markup(artifacts: list[Any]) -> str:
    if not artifacts:
        return '<p class="empty">No artifacts found.</p>'
    items = "\n".join(f"<li>{html.escape(str(path))}</li>" for path in artifacts)
    return f"<ul>{items}</ul>"


_CSS = """
:root {
  color-scheme: light;
  --bg: #f7f8fa;
  --fg: #1b1f24;
  --muted: #667085;
  --line: #d9dee7;
  --panel: #ffffff;
  --accent: #2563eb;
  --pass: #137333;
  --fail: #b42318;
  --warn: #b7791f;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--fg);
  font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}
main { max-width: 1180px; margin: 0 auto; padding: 28px 20px 48px; }
section, details {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 8px;
  margin-top: 16px;
  padding: 18px;
}
h1, h2 { margin: 0; letter-spacing: 0; }
h1 { font-size: 28px; }
h2 { font-size: 18px; margin-bottom: 14px; }
.muted { color: var(--muted); margin: 6px 0 0; }
.top { display: grid; gap: 16px; }
.stats {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 10px;
}
.stats div { border: 1px solid var(--line); border-radius: 6px; padding: 12px; }
.stats span { display: block; color: var(--muted); font-size: 12px; }
.stats strong { display: block; font-size: 24px; margin-top: 4px; }
.stats small { color: var(--muted); }
.table-wrap { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; min-width: 780px; }
th, td { border-bottom: 1px solid var(--line); padding: 10px 8px; text-align: left; font-size: 14px; }
th { color: var(--muted); font-weight: 600; }
.status { border-radius: 999px; padding: 3px 8px; font-size: 12px; font-weight: 700; }
.status.passed { color: var(--pass); background: #e7f4ea; }
.status.failed { color: var(--fail); background: #fce8e6; }
.status.warn { color: var(--warn); background: #fff4d6; }
.status.unknown { color: var(--muted); background: #eef1f5; }
.viz-grid {
  display: grid;
  grid-template-columns: minmax(260px, 0.9fr) minmax(320px, 1.4fr);
  gap: 18px;
}
h3 { margin: 0 0 10px; font-size: 14px; color: var(--muted); }
.timeline { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
.tick {
  display: inline-flex;
  width: 30px;
  height: 30px;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 800;
  border: 1px solid var(--line);
}
.tick.passed { color: var(--pass); background: #e7f4ea; border-color: #acd8b8; }
.tick.failed { color: var(--fail); background: #fce8e6; border-color: #f1b7b2; }
.tick.warn { color: var(--warn); background: #fff4d6; border-color: #f4d48a; }
.tick.unknown { color: var(--muted); background: #eef1f5; }
.trend { width: 100%; max-width: 560px; height: auto; overflow: visible; }
.trend line { stroke: var(--line); stroke-width: 1; }
.trend polyline { fill: none; stroke: var(--accent); stroke-width: 3; stroke-linejoin: round; stroke-linecap: round; }
.trend circle { fill: var(--accent); stroke: white; stroke-width: 2; }
.trend text { fill: var(--muted); font-size: 11px; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
.events { display: grid; gap: 0; }
.event { border-left: 4px solid var(--line); padding: 12px 0 12px 14px; }
.event.split { border-top: 1px solid var(--line); margin-top: 8px; }
.event header { display: flex; flex-wrap: wrap; gap: 8px; align-items: baseline; margin-bottom: 8px; }
.event header span { color: var(--accent); font-weight: 700; }
.event.implementer { border-left-color: #7c3aed; }
.event.judge { border-left-color: #b42318; }
.event.profiler { border-left-color: #0f766e; }
.event.orchestrator { border-left-color: #2563eb; }
pre {
  margin: 0;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 12px;
  line-height: 1.45;
  color: #344054;
}
summary { cursor: pointer; font-weight: 700; }
details pre, details ul { margin-top: 14px; }
li { margin: 4px 0; overflow-wrap: anywhere; }
.empty { color: var(--muted); }
@media (max-width: 700px) {
  main { padding: 18px 12px 32px; }
  section, details { padding: 14px; }
  .viz-grid { grid-template-columns: 1fr; }
}
"""
