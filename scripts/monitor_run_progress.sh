#!/usr/bin/env bash
set -euo pipefail

show_help() {
  cat <<'EOF'
Usage:
  ./scripts/monitor_run_progress.sh --run-dir <path> [--port PORT]

Example:
  ./scripts/monitor_run_progress.sh \
    --run-dir /root/.codex/worktrees/13da/vibe-serve/exp_env/20260604-025022-qwen3-0.6b-smoke \
    --port 62187

What it does:
  1) Writes a live-updating progress page to <run-dir>/reports/live_progress.html
  2) Serves <run-dir>/reports on the given port
  3) Prints a URL to open in browser
EOF
}

RUN_DIR=""
PORT="8765"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --run-dir)
      if [[ $# -lt 2 ]]; then
        echo "ERROR: --run-dir requires a path argument." >&2
        exit 1
      fi
      RUN_DIR="$2"
      shift 2
      ;;
    --port)
      if [[ $# -lt 2 ]]; then
        echo "ERROR: --port requires a value." >&2
        exit 1
      fi
      PORT="$2"
      shift 2
      ;;
    -h|--help)
      show_help
      exit 0
      ;;
    *)
      echo "ERROR: unknown argument: $1" >&2
      show_help
      exit 1
      ;;
  esac
done

if [[ -z "$RUN_DIR" ]]; then
  echo "ERROR: --run-dir is required." >&2
  show_help
  exit 1
fi

if [[ ! -d "$RUN_DIR" ]]; then
  echo "ERROR: run directory not found: $RUN_DIR" >&2
  exit 1
fi

REPORT_DIR="${RUN_DIR}/reports"
if [[ ! -d "$REPORT_DIR" ]]; then
  echo "ERROR: reports dir not found: ${REPORT_DIR}" >&2
  exit 1
fi

REPO_DIR="$(cd "${RUN_DIR}/../.." && pwd)"
RUN_NAME="$(basename "$RUN_DIR")"
BASELINE_JSON=""
if [[ "$RUN_NAME" == *"qwen3-0.6b"* ]]; then
  BASELINE_JSON="$(find "$REPO_DIR/examples/qwen3-0.6b/baseline" -path '*/vllm_bench_results*/*.json' -name 'c*.json' -type f 2>/dev/null | sort | tail -n 1 || true)"
fi
if [[ -z "$BASELINE_JSON" ]]; then
  BASELINE_JSON="$(find "$REPO_DIR/examples" -path '*/baseline/vllm_bench_results*/*.json' -name 'c*.json' -type f 2>/dev/null | sort | tail -n 1 || true)"
fi
if [[ -n "$BASELINE_JSON" && -f "$BASELINE_JSON" ]]; then
  cp "$BASELINE_JSON" "${REPORT_DIR}/baseline_target.json"
  echo "[monitor] baseline target: $BASELINE_JSON"
fi

cat > "${REPORT_DIR}/live_progress.html" <<'EOF'
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>VibeServe Run Monitor</title>
  <style>
    :root {
      --bg: #0b1020;
      --card: #121a2c;
      --muted: #9aa4be;
      --line: #2b3652;
      --text: #e8edff;
      --pass: #3ecf8e;
      --fail: #ff6b6b;
      --warn: #ffd166;
      --ok: #60a5fa;
      --target: #f59e0b;
    }
    * { box-sizing: border-box; font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, sans-serif; }
    body { margin: 0; background: radial-gradient(circle at top, #121a2c 0%, #0b1020 60%); color: var(--text); }
    .wrap { max-width: 1120px; margin: 0 auto; padding: 22px; }
    h1 { margin: 0 0 6px; font-size: 32px; line-height: 1.1; }
    .muted { color: var(--muted); font-size: 14px; overflow-wrap: anywhere; }
    .bar { margin: 16px 0; display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 12px; }
    .card { min-width: 0; border: 1px solid var(--line); border-radius: 8px; background: rgba(18,26,44,.72); padding: 14px; }
    .card h2 { margin: 0 0 8px; font-size: 12px; color: var(--muted); text-transform: uppercase; letter-spacing: .08em; }
    .card p { margin: 0; font-size: 22px; line-height: 1.1; font-weight: 750; overflow-wrap: anywhere; }
    .pass { color: var(--pass); }
    .fail { color: var(--fail); }
    .unknown { color: var(--warn); }
    .ok { color: var(--ok); }
    table { width: 100%; border-collapse: collapse; margin-top: 6px; font-size: 13px; }
    th, td { border-top: 1px solid var(--line); padding: 8px 6px; text-align: left; vertical-align: top; }
    th { color: var(--muted); font-weight: 600; }
    pre {
      background: #090d17;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 12px;
      height: 260px;
      overflow: auto;
      white-space: pre-wrap;
      color: #d6deff;
    }
    .pill { display: inline-block; border-radius: 999px; padding: 2px 8px; font-size: 11px; font-weight: 700; border: 1px solid currentColor; }
    .target { color: var(--target); }
    .refresh { margin: 4px 0 14px; color: #b8c4ff; font-size: 12px; }
    .events { display: grid; gap: 10px; }
    .event-item { border: 1px solid var(--line); border-radius: 8px; background: #090d17; padding: 12px; }
    .event-item strong { display: block; font-size: 14px; line-height: 1.35; margin-bottom: 6px; color: #dfe6ff; }
    .event-item p { margin: 0; color: #c4ccef; font-size: 13px; line-height: 1.5; overflow-wrap: anywhere; }
    a { color: #8fb8ff; }
    .small-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 10px; }
    .kv { border-top: 1px solid var(--line); padding-top: 8px; margin-top: 8px; }
    .kv span { display: block; color: var(--muted); font-size: 12px; }
    .kv strong { display: block; margin-top: 2px; font-size: 16px; overflow-wrap: anywhere; }
    .agent-graph { overflow-x: auto; padding-bottom: 2px; }
    .agent-round { min-width: 720px; display: grid; grid-template-columns: 72px repeat(5, minmax(110px, 1fr)); align-items: center; gap: 8px; margin-top: 10px; }
    .agent-round:first-child { margin-top: 0; }
    .round-label { color: var(--muted); font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: .06em; }
    .agent-node { position: relative; border: 1px solid var(--line); border-radius: 8px; padding: 10px; min-height: 64px; background: #090d17; }
    .agent-node::after { content: ""; position: absolute; right: -14px; top: 50%; width: 14px; height: 1px; background: var(--line); }
    .agent-node:last-child::after { display: none; }
    .agent-node span { display: block; color: var(--muted); font-size: 11px; text-transform: uppercase; letter-spacing: .06em; }
    .agent-node strong { display: block; margin-top: 4px; font-size: 14px; color: #dfe6ff; }
    .agent-node.done { border-color: rgba(62,207,142,.85); box-shadow: inset 0 0 0 1px rgba(62,207,142,.15); }
    .agent-node.active { border-color: rgba(245,158,11,.95); box-shadow: 0 0 0 2px rgba(245,158,11,.12); }
    .agent-node.failed { border-color: rgba(255,107,107,.85); box-shadow: inset 0 0 0 1px rgba(255,107,107,.12); }
    .agent-node.pending { opacity: .58; }
    .agent-node small { display: block; margin-top: 5px; color: var(--muted); font-size: 11px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    @media (max-width: 520px) {
      .wrap { padding: 16px; }
      h1 { font-size: 26px; }
      .bar { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <div class="wrap">
    <h1>VibeServe Live Progress</h1>
    <div class="muted" id="pathInfo">Loading run path...</div>
    <div class="refresh">auto-refreshing every 5s • last update: <span id="lastTick">-</span></div>
    <div class="bar">
      <div class="card">
        <h2>Status</h2><p id="status" class="unknown">unknown</p>
      </div>
      <div class="card">
        <h2>Primary Metric</h2><p id="metric">-</p>
      </div>
      <div class="card">
        <h2>Rounds</h2><p id="rounds">-</p>
      </div>
      <div class="card">
        <h2>Current Benchmark</h2><p id="benchmarkEngine">-</p>
      </div>
    </div>

    <div class="card" style="margin-bottom: 12px;">
      <h2>vLLM Baseline Target</h2>
      <div class="small-grid">
        <div class="kv"><span>Target Throughput</span><strong id="baselineTarget" class="target">loading</strong></div>
        <div class="kv"><span>Workload</span><strong id="baselineWorkload">loading</strong></div>
        <div class="kv"><span>Timing</span><strong id="baselineLatency">see latency table</strong></div>
        <div class="kv"><span>Model</span><strong id="baselineModel">loading</strong></div>
      </div>
    </div>

    <div class="card" style="margin-bottom: 12px;">
      <h2>Latency by Case</h2>
      <div id="latencyTableWrap">
        <span class="muted">Waiting for latency metrics ...</span>
      </div>
    </div>

    <div class="card" style="margin-bottom: 12px;">
      <h2>Agent Loop</h2>
      <div class="agent-graph" id="agentGraph">
        <span class="muted">Waiting for agent events ...</span>
      </div>
    </div>

    <div class="card">
      <h2 id="roundResultsTitle">Round Results vs Target</h2>
      <div id="roundTableWrap">
        <span class="muted">No round results reported yet.</span>
      </div>
    </div>

    <div class="card" style="margin-top: 12px;">
      <h2>Recent Events</h2>
      <div class="events" id="events">Waiting for report.json ...</div>
    </div>

    <p class="muted" style="margin-top: 12px;">Also open <a href="round_summary.json">round_summary.json</a> and logs from the run directory for per-step details.</p>
  </div>

  <script>
    function clsForStatus(s) {
      if (!s) return "unknown";
      const v = String(s).toLowerCase();
      if (v === "passed" || v === "pass" || v === "done" || v === "completed") return "pass";
      if (v === "failed" || v === "fail") return "fail";
      if (v === "target") return "target";
      if (v === "in progress" || v === "running" || v === "active" || v === "reported") return "ok";
      return "unknown";
    }

    function displayStatus(report) {
      const raw = report.global_objective_status || "unknown";
      if (String(raw).toLowerCase() !== "unknown") return raw;
      const events = Array.isArray(report.events) ? report.events : [];
      const rounds = report.round_records || report.rounds || [];
      if (events.length > 0 || rounds.length > 0) return "in progress";
      return "unknown";
    }

    function renderRounds(rounds, metricName, baselineValue) {
      if ((!Array.isArray(rounds) || rounds.length === 0) && baselineValue == null) {
        return '<span class="muted">No target or round results reported yet.</span>';
      }
      let html = '<table><thead><tr><th>Entry</th><th>Status</th><th>Result</th><th>Delta vs vLLM</th><th>Source</th></tr></thead><tbody>';
      if (baselineValue != null) {
        html += `<tr>
          <td>vLLM target</td>
          <td><span class="pill target">target</span></td>
          <td>${fmtNumber(baselineValue)} tokens/sec</td>
          <td>0.0%</td>
          <td>baseline_target.json</td>
        </tr>`;
      }
      for (const row of rounds) {
        const status = row.status || row.verdict || "unknown";
        const cls = clsForStatus(status);
        const metric = row.metric_name || row.judge_perf_name || row.perf_name || metricName || "unknown";
        const rawValue = row.metric_value ?? row.judge_metric_value ?? row.judge_perf_metric ?? row.perf_metric;
        const value = rawValue == null ? "unknown" : fmtNumber(rawValue);
        const baseline = (row.baseline_value ?? "unknown");
        const delta = row.delta_pct == null ? deltaText(rawValue, baseline) : `${Number(row.delta_pct).toFixed(1)}%`;
        const source = row.source || row.commit || "-";
        html += `<tr>
          <td>round ${row.round ?? "-"}</td>
          <td><span class="pill ${cls}">${status}</span></td>
          <td>${value}</td>
          <td>${delta}</td>
          <td>${escapeHtml(source)}</td>
        </tr>`;
      }
      html += '</tbody></table>';
      return html;
    }

    function renderLatencyTable(rows) {
      if (!Array.isArray(rows) || rows.length === 0) {
        return '<span class="muted">Waiting for latency metrics ...</span>';
      }
      let html = '<table><thead><tr><th>Source</th><th>Completed</th><th>Output tok/s</th><th>TTFT P50</th><th>TTFT P99</th><th>TPOT P50</th><th>TPOT P99</th></tr></thead><tbody>';
      for (const row of rows) {
        html += `<tr>
          <td>${escapeHtml(row.source)}</td>
          <td>${escapeHtml(row.completed)}</td>
          <td>${escapeHtml(row.outputThroughput)}</td>
          <td>${escapeHtml(row.ttftP50)}</td>
          <td>${escapeHtml(row.ttftP99)}</td>
          <td>${escapeHtml(row.tpotP50)}</td>
          <td>${escapeHtml(row.tpotP99)}</td>
        </tr>`;
      }
      html += '</tbody></table>';
      return html;
    }

    function escapeHtml(value) {
      return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
    }

    function compactMetricName(name) {
      const v = String(name || "-");
      if (v === "tokens_per_sec") return "tokens/sec";
      if (v === "median_tok_per_sec") return "median tok/s";
      return v.replaceAll("_", " ");
    }

    function fmtNumber(value, digits = 2) {
      if (value == null || value === "") return "unknown";
      const n = Number(value);
      if (!Number.isFinite(n)) return "unknown";
      return n.toLocaleString(undefined, { maximumFractionDigits: digits });
    }

    function fmtMs(value) {
      if (value == null || value === "") return "unknown";
      const n = Number(value);
      if (!Number.isFinite(n)) return "unknown";
      return `${fmtNumber(n)} ms`;
    }

    function firstMetric(obj, names) {
      if (!obj) return null;
      for (const name of names) {
        if (obj[name] != null) return obj[name];
      }
      return null;
    }

    function caseLabel(obj) {
      if (!obj) return "unknown";
      const c = obj.max_concurrency ?? obj.concurrency ?? "?";
      const n = obj.num_prompts ?? obj.num_samples ?? obj.completed ?? "?";
      const inputLen = obj.random_input_len ?? (obj.total_input_tokens && obj.num_prompts ? obj.total_input_tokens / obj.num_prompts : "?");
      const outputLen = obj.random_output_len ?? (obj.total_output_tokens && obj.num_prompts ? obj.total_output_tokens / obj.num_prompts : "?");
      return `c${c} n${n} in${inputLen} out${outputLen}`;
    }

    function latencyRow(source, obj, fallbackBaseline) {
      if (!obj) return null;
      const throughput = firstMetric(obj, ["output_throughput", "tokens_per_sec", "metric_value", "judge_metric_value", "judge_perf_metric", "perf_metric"]);
      const ttftP50 = firstMetric(obj, ["median_ttft_ms", "p50_ttft_ms", "ttft_p50_ms"]);
      const ttftP99 = firstMetric(obj, ["p99_ttft_ms", "ttft_p99_ms"]);
      const tpotP50 = firstMetric(obj, ["median_tpot_ms", "p50_tpot_ms", "tpot_p50_ms"]);
      const tpotP99 = firstMetric(obj, ["p99_tpot_ms", "tpot_p99_ms"]);
      if ([throughput, ttftP50, ttftP99, tpotP50, tpotP99].every((v) => v == null)) {
        return null;
      }
      return {
        source,
        case: caseLabel(obj),
        completed: obj.completed ?? obj.num_prompts ?? obj.num_samples ?? "unknown",
        outputThroughput: throughput == null ? (fallbackBaseline == null ? "unknown" : `${fmtNumber(fallbackBaseline)} tok/s`) : `${fmtNumber(throughput)} tok/s`,
        ttftP50: fmtMs(ttftP50),
        ttftP99: fmtMs(ttftP99),
        tpotP50: fmtMs(tpotP50),
        tpotP99: fmtMs(tpotP99),
      };
    }

    function latencyRows(baseline, rounds, baselineValue) {
      const rows = [];
      const baselineRow = latencyRow("vLLM target", baseline, baselineValue);
      if (baselineRow) rows.push(baselineRow);
      for (const row of rounds || []) {
        const source = `round ${row.round ?? "?"}`;
        const direct = latencyRow(source, row, null);
        if (direct) rows.push(direct);
        for (const key of ["benchmark", "metrics", "result"]) {
          const nested = latencyRow(source, row[key], null);
          if (nested) rows.push(nested);
        }
      }
      return rows;
    }

    function deltaText(value, baseline) {
      const v = Number(value);
      const b = Number(baseline);
      if (!Number.isFinite(v) || !Number.isFinite(b) || b === 0) return "unknown";
      const pct = ((v - b) / b) * 100;
      return `${pct >= 0 ? "+" : ""}${pct.toFixed(1)}%`;
    }

    function baselineMetricValue(baseline, metricName) {
      if (!baseline) return null;
      if (baseline.output_throughput != null) return baseline.output_throughput;
      if (baseline.tokens_per_sec != null) return baseline.tokens_per_sec;
      if (baseline.total_token_throughput != null && metricName !== "tokens_per_sec") return baseline.total_token_throughput;
      return null;
    }

    function summarizeEventBody(body) {
      const text = String(body || "").replace(/\s+/g, " ").trim();
      if (text.length <= 360) return text;
      return `${text.slice(0, 357)}...`;
    }

    function eventRoundResults(events, metricName, baselineValue) {
      const byRound = new Map();
      for (const e of events || []) {
        const body = String(e.body || "");
        const m = body.match(/tokens_per_sec(?:\s+about|\s*[:=])?\s+([0-9]+(?:\.[0-9]+)?)/i);
        if (!m) continue;
        const round = e.round ?? "?";
        byRound.set(String(round), {
          round,
          status: "reported",
          metric_name: metricName || "tokens/sec",
          metric_value: Number(m[1]),
          baseline_value: baselineValue,
          source: `${e.agent || "event"}: ${e.title || "latest note"}`,
        });
      }
      return [...byRound.values()].sort((a, b) => Number(a.round) - Number(b.round));
    }

    function normalizeRoundRows(report, baselineValue) {
      const rounds = Array.isArray(report.rounds) ? report.rounds : [];
      const records = Array.isArray(report.round_records) ? report.round_records : [];
      const byRound = new Map();
      for (const row of records) {
        byRound.set(String(row.round), { ...row });
      }
      for (const row of rounds) {
        byRound.set(String(row.round), { ...(byRound.get(String(row.round)) || {}), ...row });
      }
      return [...byRound.values()]
        .map((row) => ({
          ...row,
          status: row.status || (row.passed === true ? "passed" : row.passed === false ? "failed" : "unknown"),
          metric_name: row.metric_name || row.judge_perf_name || row.perf_name,
          metric_value: row.metric_value ?? row.judge_metric_value ?? row.judge_perf_metric ?? row.perf_metric,
          baseline_value: row.baseline_value ?? baselineValue,
        }))
        .sort((a, b) => Number(a.round) - Number(b.round));
    }

    function normalizeAgent(agent) {
      const v = String(agent || "").toLowerCase();
      if (v.includes("orchestrator")) return "orchestrator";
      if (v.includes("implementer")) return "implementer";
      if (v.includes("judge")) return "judge";
      if (v.includes("profiler")) return "profiler";
      if (v.includes("event")) return "event";
      return v || "event";
    }

    function agentLabel(agent) {
      return {
        event: "Plan",
        orchestrator: "Orchestrator",
        implementer: "Implementer",
        judge: "Judge",
        profiler: "Profiler",
      }[agent] || agent;
    }

    function buildAgentRows(events, rounds) {
      const order = ["event", "orchestrator", "implementer", "judge", "profiler"];
      const byRound = new Map();
      for (const e of events || []) {
        const round = String(e.round || 1);
        if (!byRound.has(round)) {
          byRound.set(round, Object.fromEntries(order.map((a) => [a, { state: "pending", title: "" }])));
        }
        const agent = normalizeAgent(e.agent);
        if (!order.includes(agent)) continue;
        const title = String(e.title || "");
        const body = String(e.body || "");
        const failed = /fail|failed|error|timeout/i.test(`${title} ${body}`);
        byRound.get(round)[agent] = { state: failed ? "failed" : "done", title };
      }
      for (const r of rounds || []) {
        const round = String(r.round || 1);
        if (!byRound.has(round)) {
          byRound.set(round, Object.fromEntries(order.map((a) => [a, { state: "pending", title: "" }])));
        }
        if (/fail/i.test(String(r.status || ""))) {
          byRound.get(round).judge = { state: "failed", title: "round failed" };
        }
      }
      const sorted = [...byRound.entries()].sort(([a], [b]) => Number(a) - Number(b));
      const latest = sorted.at(-1);
      if (latest) {
        const row = latest[1];
        const firstPending = order.find((a) => row[a].state === "pending");
        if (firstPending) row[firstPending] = { ...row[firstPending], state: "active", title: "waiting/running" };
      }
      return sorted.map(([round, agents]) => ({ round, agents, order }));
    }

    function renderAgentGraph(events, rounds) {
      const rows = buildAgentRows(events, rounds);
      if (!rows.length) return '<span class="muted">Waiting for agent events ...</span>';
      return rows.map(({ round, agents, order }) => {
        const nodes = order.map((agent) => {
          const info = agents[agent] || { state: "pending", title: "" };
          return `<div class="agent-node ${info.state}"><span>${escapeHtml(agentLabel(agent))}</span><strong>${escapeHtml(info.state)}</strong><small>${escapeHtml(info.title || "-")}</small></div>`;
        }).join("");
        return `<div class="agent-round"><div class="round-label">Round ${escapeHtml(round)}</div>${nodes}</div>`;
      }).join("");
    }

    async function loadBaseline() {
      try {
        const r = await fetch(`baseline_target.json?ts=${Date.now()}`);
        if (!r.ok) return null;
        return await r.json();
      } catch (_e) {
        return null;
      }
    }

    async function refresh() {
      try {
        const r = await fetch(`report.json?ts=${Date.now()}`);
        const j = await r.json();
        const baseline = await loadBaseline();
        const metricName = j.benchmark && j.benchmark.primary_metric;
        const baselineFromReport = j.benchmark && (j.benchmark.baseline_value ?? (j.benchmark.baseline_metrics && j.benchmark.baseline_metrics.tokens_per_sec));
        const baselineValue = baselineMetricValue(baseline, metricName) ?? baselineFromReport;

        document.getElementById("pathInfo").textContent = `source_experiment: ${j.source_experiment || "(unknown)"}`;
        const status = displayStatus(j);
        const statusEl = document.getElementById("status");
        statusEl.textContent = status;
        statusEl.className = clsForStatus(status);
        document.getElementById("metric").textContent = compactMetricName(metricName);
        const completedRows = normalizeRoundRows(j, baselineValue);
        document.getElementById("rounds").textContent = String(completedRows.length);
        document.getElementById("benchmarkEngine").textContent = (j.benchmark && (j.benchmark.baseline && j.benchmark.baseline.engine || j.benchmark.baseline_engine)) || "unknown";

        document.getElementById("baselineTarget").textContent = baselineValue == null ? "not recorded yet" : `${fmtNumber(baselineValue)} tokens/sec`;
        if (baseline) {
          document.getElementById("baselineWorkload").textContent = `c${baseline.max_concurrency ?? "?"} / n${baseline.num_prompts ?? "?"} / in ${baseline.total_input_tokens && baseline.num_prompts ? baseline.total_input_tokens / baseline.num_prompts : "?"} / out ${baseline.total_output_tokens && baseline.num_prompts ? baseline.total_output_tokens / baseline.num_prompts : "?"}`;
          document.getElementById("baselineLatency").textContent = "TTFT/TPOT P50/P99 below";
          document.getElementById("baselineModel").textContent = baseline.model_id || "vLLM";
        } else {
          document.getElementById("baselineWorkload").textContent = "waiting for baseline_target.json";
          document.getElementById("baselineLatency").textContent = "waiting for latency metrics";
          document.getElementById("baselineModel").textContent = "vLLM";
        }

        const rows = completedRows.length ? completedRows : eventRoundResults(j.events || [], compactMetricName(metricName), baselineValue);
        document.getElementById("latencyTableWrap").innerHTML = renderLatencyTable(latencyRows(baseline, completedRows, baselineValue));
        document.getElementById("agentGraph").innerHTML = renderAgentGraph(j.events || [], completedRows);
        document.getElementById("roundResultsTitle").textContent = `Round Results vs Target (${compactMetricName(metricName)})`;
        document.getElementById("roundTableWrap").innerHTML = renderRounds(rows, compactMetricName(metricName), baselineValue);

        const events = Array.isArray(j.events) ? j.events : [];
        if (events.length) {
          const items = events.slice(-8).reverse().map((e) => {
            const agent = e.agent || "";
            const title = e.title || "";
            const body = summarizeEventBody(e.body || "");
            return `<div class="event-item"><strong>${escapeHtml(agent)}: ${escapeHtml(title)}</strong><p>${escapeHtml(body)}</p></div>`;
          });
          document.getElementById("events").innerHTML = items.join("");
        } else {
          document.getElementById("events").textContent = "No event log yet.";
        }
      } catch (_e) {
        document.getElementById("events").textContent = "Waiting for report artifacts ...";
      }
      document.getElementById("lastTick").textContent = new Date().toLocaleTimeString();
    }

    refresh();
    setInterval(refresh, 5000);
  </script>
</body>
</html>
EOF

echo "[monitor] wrote ${REPORT_DIR}/live_progress.html"
echo "[monitor] serving ${REPORT_DIR} at http://127.0.0.1:${PORT}/live_progress.html"
echo "[monitor] Ctrl-C to stop."
cd "$REPORT_DIR"
python3 -m http.server "$PORT"
