"""Summarize the S-1b part 2 (iPhone 4G) logs: `python3 -I s1b_report.py [--rows] out/s1b/logs-*.jsonl`.

Input: the JSON lines `s1b_deploy.sh logs` writes (proxy events plus the test page's telemetry, event "client").
Only numbers and fixed words are in that file, so this report can go to the team as is.
Stdlib only; percentiles are nearest-rank like zj_spike.common.percentile (with n=10, p95 is the max).
Route: "airpods" in the 2026-10-07 log means whatever earphone was picked (none was; Bose Ultra Earbuds, Bluetooth, untagged);
from the S2 page v1.0 on it is "bluetooth" / "wired" / "speaker", and all three selectors must be chosen before talking.
"""

from __future__ import annotations

import json
import math
import sys
from collections import defaultdict

ITEMS = {"t1": "1 release to sound (4G) / 離してから音が出るまで（4G）", "t2": "2 barge-in / 割り込み",
         "t3": "3 earphone mic, two ways / イヤホンマイクの 2 つのやり方", "t4": "4 silent switch / 消音スイッチ",
         "t5": "5 speaking quietly / 小声で話す", "t6": "6 LINE", "t7": "7 app in background / バックグラウンドへ切り替え",
         "t8": "8 Wi-Fi comparison / Wi-Fi 比較"}
LIMITS = {"clientReleaseToAudibleMs": (1800, 3000), "pressToFirstUpMs": 60, "firstDownToAudibleMs": 150,
          "pressToSilenceMs": 200}


def pct(vals: list[float], q: float) -> float | None:
    if not vals:
        return None
    s = sorted(vals)
    return s[max(1, math.ceil(q / 100 * len(s))) - 1]


def stat(vals: list) -> str:
    v = [x for x in vals if isinstance(x, (int, float)) and not isinstance(x, bool)]
    if not v:
        return "—"
    return f"n={len(v)} median/中央値 {pct(v, 50):.0f} / p95 {pct(v, 95):.0f} / max/最大 {max(v):.0f}"


def load(paths: list[str]) -> list[dict]:
    rows = []
    for p in paths:
        with open(p, encoding="utf-8") as f:
            rows += [json.loads(line) for line in f if line.strip()]
    return rows


def report(rows: list[dict]) -> str:
    out = []
    ev = defaultdict(list)
    for r in rows:
        ev[r.get("event")].append(r)
    client = ev.get("client", [])
    turns = [c for c in client if "clientReleaseToAudibleMs" in c or "turnId" in c]
    events = [c for c in client if c not in turns]

    out.append("## Test page (phone-side timing) / テストページ（スマホ側の計時）")
    groups = defaultdict(list)
    for t in turns:
        mic = "?" if "extMicCount" not in t else ("external mic/外部マイク" if t["extMicCount"] else "phone mic/本体マイク")  # page v0.9.6+
        groups[(t.get("item", "?"), t.get("route", "?"), t.get("network", "?"), t.get("mode", "?"), mic)].append(t)
    for key in sorted(groups):
        g = groups[key]
        item, route, net, mode, mic = key
        out.append(f"\n### {ITEMS.get(item, item)} · {route} / {net} / {mode} / {mic} ({len(g)} turns / {len(g)} ターン)")
        for k in ("clientReleaseToAudibleMs", "serverReleaseToFirstAudioMs", "netMs", "clientReleaseToFirstDownMs",
                  "pressToFirstUpMs", "firstDownToAudibleMs", "pressToSilenceMs", "pressToInterruptedMs", "micOpenMs",
                  "cerPct", "underrunCount", "timeoutCount", "bargeInCount"):
            vals = [t.get(k) for t in g if t.get(k) is not None]
            if not vals:
                continue
            line = f"- {k}: {stat(vals)}"
            lim = LIMITS.get(k)
            if isinstance(lim, tuple):
                ok = pct(vals, 50) <= lim[0] and pct(vals, 95) <= lim[1]
                line += f" → S-017 (median/中央値 ≤ {lim[0]}, p95 ≤ {lim[1]}) {'pass/合格' if ok else 'fail/不合格'}"
            elif lim is not None:
                over = sum(1 for v in vals if v > lim)
                within = pct(vals, 50) <= lim
                line += (f" → limit/基準 {lim} ms, median/中央値 {'within/以内' if within else 'over/超過'}, "
                         f"over the limit/超過 {over}x")
            if k in ("underrunCount", "timeoutCount", "bargeInCount"):
                line = f"- {k}: total/合計 {sum(vals):.0f} ({len(vals)} turns / ターン)"
            out.append(line)

    if events:
        out.append("\n### Page events / ページイベント")
        for e in events:
            fields = ", ".join(f"{k}={v}" for k, v in e.items() if k not in ("at", "event", "kind", "severity"))
            out.append(f"- {e.get('at', '')[:19]} {fields}")

    out.append("\n## Proxy (server side) / プロキシ（サーバー側）")
    st = [t for t in ev.get("turn", [])]
    voice = [t for t in st if t.get("via") == "voice"]
    out.append(f"- turns/ターン数 {len(st)} (voice/音声 {len(voice)}, "
               f"interrupted/割り込まれた {sum(1 for t in st if t.get('interrupted'))})")
    out.append(f"- serverReleaseToFirstAudioMs (uninterrupted voice turns / 割り込みのない音声ターン): "
               f"{stat([t.get('serverReleaseToFirstAudioMs') for t in voice if not t.get('interrupted')])}")
    out.append(f"- firstPlayerTranscriptMs: {stat([t.get('firstPlayerTranscriptMs') for t in voice])}")
    out.append(f"- focusToReadyMs: {stat([f.get('focusToReadyMs') for f in ev.get('focus', [])])}")
    out.append(f"- session_open setupMs: {stat([s.get('setupMs') for s in ev.get('session_open', [])])}")
    usd = [t.get("usd") for t in st if isinstance(t.get("usd"), (int, float))]
    out.append(f"- cost recorded on turns / ターンに記録された費用 ${sum(usd):.4f} "
                   "(interrupted turns are null; the real cost is in the ledger / 割り込まれたターンは null、実費は台帳にある)")
    for name in ("session_error", "live_goaway", "late_transcript", "ws_refused", "voice_off"):
        if ev.get(name):
            out.append(f"- {name}: {len(ev[name])}x")
            for e in ev[name][:5]:
                fields = ", ".join(f"{k}={v}" for k, v in e.items() if k not in ("at", "event", "kind", "severity"))
                out.append(f"  - {e.get('at', '')[:19]} {fields}")
    logins = ev.get("login", [])
    out.append(f"- login/ログイン: ok/成功 {sum(1 for x in logins if x.get('ok'))}, "
               f"failed/失敗 {sum(1 for x in logins if not x.get('ok'))}, "
               f"blocked/制限 {sum(1 for x in logins if x.get('blocked'))}")
    conns = ev.get("conn_end", [])
    if conns:
        out.append(f"- connections/接続 {len(conns)}x, total/合計 {sum(c.get('seconds', 0) for c in conns):.0f} s")
    return "\n".join(out)


ROW_KEYS = ("clientReleaseToAudibleMs", "serverReleaseToFirstAudioMs", "netMs", "pressToFirstUpMs", "firstDownToAudibleMs",
            "pressToSilenceMs", "pressToInterruptedMs", "micOpenMs", "speechMs", "cerPct", "underrunCount", "timeoutCount",
            "bargeInCount", "extMicCount")


def rows_table(rows: list[dict]) -> str:
    """One line per page-side turn, in log order: item route/network/mode, then the timing fields present."""
    out = ["\n## Each turn (test page) / ターンごと（テストページ）"]
    for r in rows:
        if r.get("event") != "client" or "turnId" not in r:
            continue
        nums = " ".join(f"{k.replace('Ms', '')}={r[k]:g}" for k in ROW_KEYS if isinstance(r.get(k), (int, float)))
        out.append(f"{r.get('at', '')[11:19]} {r.get('item', '?')} {r.get('route', '?')}/{r.get('network', '?')}/"
                   f"{r.get('mode', '?')} #{r.get('turnSeq', '?')} {nums}")
    return "\n".join(out)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--rows"]
    if not args:
        sys.exit(__doc__)
    data = load(args)
    print(report(data))
    if "--rows" in sys.argv[1:]:
        print(rows_table(data))
