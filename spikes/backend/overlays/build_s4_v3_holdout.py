"""Builds s4_v3_holdout.py for the Mac's 41f261e10137 package: python3 build_s4_v3_holdout.py HOLDOUT.jsonl OUT.py"""
import ast, json, sys
from pathlib import Path

SRC = Path("/mnt/project-files/app-team/backend/spikes/zj_spike/s4_model_armor.py").read_text(encoding="utf-8")
tree = ast.parse(SRC)
v3 = next(n.value.value for n in tree.body if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", "") == "CLASSIFY_PROMPT_V3")
assert '"""' not in v3 and "'''" not in v3
hold = [json.loads(l) for l in Path(sys.argv[1]).read_text(encoding="utf-8").splitlines() if l.strip()]
lines = "\n".join(json.dumps({k: r[k] for k in ("id", "label", "text", "boundary") if k in r}, ensure_ascii=False) for r in hold)
assert "'''" not in lines
body = f'''# v3 prompt (same as CLASSIFY_PROMPT_V3 in the project's s4_model_armor.py) plus the data side's holdout samples;
# judge the main set first, then the holdout set on its own.
# v3 プロンプト（プロジェクトの s4_model_armor.py の CLASSIFY_PROMPT_V3 と同じ）とデータ側のホールドアウトサンプル。
# まずメインセットを判定し、次にホールドアウトセットだけを判定する。
import json, sys, time
from zj_spike import s4_model_armor as s
s.PROMPTS["v3"] = """{v3}"""
HOLD = [json.loads(l) for l in r\'\'\'
{lines}
\'\'\'.strip().splitlines()]
main_ids = {{x["id"] for x in s.load_samples()}}
assert main_ids.isdisjoint(x["id"] for x in HOLD), "holdout sample ids overlap the main set / ホールドアウトサンプルの id がメインセットと重複"
print(f"main set {{len(main_ids)}} items, holdout set {{len(HOLD)}} items, prompts v2, v3 / メインセット {{len(main_ids)}} 件、ホールドアウトセット {{len(HOLD)}} 件、プロンプト v2・v3")
BAD = {{"selfharm": {{"none", "ambiguous", "blocked"}}, "selfharm_ambiguous": {{"none", "blocked"}},
       "benign_story": {{"signal"}}, "benign_lookalike": {{"signal"}}}}


def show_misses():
    f = sorted((s.common.settings().out_dir / "s4").glob("classify-*/result.json"))[-1]
    print("Reasons for each miss / 基準を満たさなかった各件の理由:")
    for r in json.loads(f.read_text(encoding="utf-8"))["classifier_rows"]:
        if "error" in r or r.get("self_harm") in BAD.get(r["label"], set()):
            print("  ", r["prompt"], r["id"], r.get("self_harm"), (r.get("reason") or r.get("error") or "")[:120])


sys.argv = ["s4", "--classify-only", "--prompts", "v2,v3"]
s.main()
show_misses()
time.sleep(1.1)  # each of the two runs writes its own folder / 2 回の結果をそれぞれ別フォルダに書く
print("\\n==== holdout set (samples not seen while tuning the prompt) / ホールドアウトセット（プロンプト調整中に見ていないサンプル）====")
s.load_samples = lambda include_extra=True: HOLD
s.main()
show_misses()
'''
Path(sys.argv[2]).write_text(body, encoding="utf-8")
print(f"wrote {sys.argv[2]}: {len(hold)} held-out lines, {len(body)} chars")
