"""Scene packs and character files for the deploy (B-23), run by deploy.sh build on zg's Mac.

    python packs.py <worktree of the deployed commit> <repo on the Mac where they were built> <output dir>

Scene packs and character models are not in git (S-075); each pipeline builds them in the repo on the Mac: scenes in
`assets/scenes/<dir>/build/`, characters in `assets/cast/build/<name>/`. This creates, under <output dir>,
`scenes/<dir>` → a symlink to that build (read by vite build's ZOUJIN_SCENE_ROOT and the gateway's ZJ_SCENE_PACKS) and
`cast` → `assets/cast/build` (ZOUJIN_CAST_ROOT), then checks:

- missing: a scene dir with a committed manifest (scene.json, index.json, pack.json) has no build/, or a character
  file listed in cast.json is absent;
- stale: the build was not made by the pipeline of the deployed commit. When the manifest has inputs (layout, scripts'
  sha256, tool versions, env vars) only the inputs are compared, as the pipeline's own check_scene.mjs does; without
  inputs (road-common, lighting sub-packs, index.json) the structure is compared: same keys, file names and tier names
  means the same version, numbers and sha256 are not compared. Derived bytes such as texture PNGs and bakes differ a
  little from machine to machine (the inputs comment in pack_scene.mjs), so a rebuild on zg's Mac that does not match
  the commit is not stale. A character file whose sha256 does not match cast.json is stale.

When anything is missing or stale, print which ones and the commands to run: exit code 1 if something is missing,
2 if only stale; 0 if all are present.

デプロイ用のシーンパックと登場人物のファイル（B-23）。zg の Mac 上で deploy.sh build が実行する。

    python packs.py <デプロイするコミットの作業ツリー> <Mac 上で生成済みのリポジトリ> <出力ディレクトリ>

シーンパックと登場人物のモデルは git に入れず（S-075）、それぞれのパイプラインが Mac のリポジトリ内で生成する：
シーンは `assets/scenes/<ディレクトリ>/build/`、登場人物は `assets/cast/build/<名前>/`。
ここでは <出力ディレクトリ> の下に `scenes/<ディレクトリ>` → その build へのシンボリックリンク（vite build の
ZOUJIN_SCENE_ROOT とゲートウェイの ZJ_SCENE_PACKS が読む）と、`cast` → `assets/cast/build`（ZOUJIN_CAST_ROOT）を
作り、次を確認する：

- 欠落：リポジトリにマニフェスト（scene.json、index.json、pack.json）があるシーンのディレクトリに build/ がない、
  または cast.json に載っている登場人物のファイルがない。
- 古い：build がデプロイするこのコミットのパイプラインで生成されていない。マニフェストに inputs（レイアウト、
  スクリプトの sha256、ツールのバージョン、環境変数）があれば inputs だけを比べる（パイプライン自身の
  check_scene.mjs と同じ）。inputs がないもの（road-common、ライティングのサブパック、index.json）は構造を比べる：
  キー、ファイル名、段階名が同じなら同じ版とみなし、数値と sha256 は比べない。テクスチャの PNG やベイクのような
  派生したバイトはマシンが変わると少し違う（pack_scene.mjs の inputs のコメント）ので、zg の Mac で再生成したものが
  コミットと合わなくても古いとはみなさない。登場人物のファイルの sha256 が cast.json と合わなければ古いとみなす。

欠落や古いものがあれば、どれなのかと実行すべきコマンドを出力する：欠落があれば終了コード 1、古いものだけなら 2、
すべて揃っていれば 0。
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

ENTRIES = ("index.json", "scene.json", "pack.json")
# Scene dir → the command that builds it (run at the repo root, final)
# シーンのディレクトリ → それを生成するコマンド（リポジトリのルートで実行、final）
BUILDERS = {
    "syracuse-square": "assets/pipeline/plaza/build.sh final && assets/pipeline/crowd/build.sh",
    "castle-throne": "assets/pipeline/castle/build.sh final",
    "village": "assets/pipeline/village/build.sh final",
    "village-interior": "assets/pipeline/village/build.sh final",
    "road-river": "assets/pipeline/road/build.sh final",
    "road-river-calm": "assets/pipeline/road/build.sh final",
    "road-river-flood": "assets/pipeline/road/build.sh final",
}
# The rest of the way back (F-15): road-pass, -spring, -field, road-run-*
# 帰り道の残りの場所（F-15）：road-pass、-spring、-field、road-run-*
REST = "assets/pipeline/road/build_rest.sh final"
CAST = "assets/pipeline/cast/build.sh"
# Problem labels; main() tells missing from stale (exit code) and characters from scenes by these prefixes
# 問題のラベル。main() はこの接頭辞で欠落と古いもの（終了コード）、登場人物とシーンを見分ける
MISSING = "missing"
STALE = "stale"
CHARACTER = "character"


def builder(name: str) -> str:
    if name in BUILDERS:
        return BUILDERS[name]
    if name.startswith(("road-pass", "road-spring", "road-field", "road-run")):
        return REST
    if name.startswith("village-light-"):
        # The village's dusk, night and rain lighting sub-packs (F-11), built along with the village's final
        # 村の夕暮れ、夜、雨のライティングのサブパック（F-11）。村の final と一緒に生成される
        return BUILDERS["village"]
    if name == "road-common":
        # The shared roadside pack: the river's, the village's and the rest's final builds all add to it
        # 共用の道端パック：川、村、残りの場所の final がどれもここに追加する
        return "assets/pipeline/road/build.sh final"
    return (
        f"(unknown which pipeline builds {name}; ask the frontend)"
        f" / （{name} をどのパイプラインが生成するか不明。フロントエンドに聞くこと）"
    )


HEX64 = re.compile(r"[0-9a-f]{64}")


def shape(v: object) -> object:
    """The manifest without derived values: numbers, booleans and sha256 become placeholders; keys, file names and
    tier names remain.

    派生した値を除いたマニフェスト：数値、真偽値、sha256 はプレースホルダーに置き換え、
    キー、ファイル名、段階名などだけを残す。
    """
    if isinstance(v, dict):
        return {k: shape(x) for k, x in v.items()}
    if isinstance(v, list):
        return [shape(x) for x in v]
    if isinstance(v, str):
        return "#" if HEX64.fullmatch(v) else v
    return "#" if v is not None else None


def same_build(committed: bytes, built: bytes) -> bool:
    a, b = json.loads(committed), json.loads(built)
    if isinstance(a, dict) and isinstance(b, dict) and "inputs" in a:
        return bool(a["inputs"] == b.get("inputs"))
    # road-common can be merged by the village or the way-back pipeline; the top-level note is just the generator's
    # signature, not part of the asset structure. Only this one note field is dropped; files / textures / nested
    # structure and the inputs check stay as they are.
    # road-common は村または帰り道のパイプラインがマージしうる。トップレベルの note は生成器の署名にすぎず、
    # アセットの構造ではない。この説明フィールドだけを外し、files / textures / 入れ子の構造と inputs の検査はそのまま。
    if isinstance(a, dict) and isinstance(b, dict):
        a.pop("note", None)
        b.pop("note", None)
    return shape(a) == shape(b)


def sha256(path: Path) -> str:
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def scenes(commit: Path, built: Path, out: Path) -> list[tuple[str, str]]:
    problems = []
    root = out / "scenes"
    root.mkdir(parents=True, exist_ok=True)
    for d in sorted(p for p in (commit / "assets" / "scenes").iterdir() if p.is_dir()):
        committed = [d / n for n in ENTRIES if (d / n).is_file()]
        if not committed:
            continue
        build = built / "assets" / "scenes" / d.name / "build"
        link = root / d.name
        if link.is_symlink() or link.exists():
            link.unlink()
        if not build.is_dir():
            problems.append((d.name, f"{MISSING} / 欠落"))
            continue
        link.symlink_to(build.resolve(), target_is_directory=True)
        for c in committed:
            b = build / c.name
            if not b.is_file():
                problems.append((d.name, f"{MISSING} build/{c.name} / build/{c.name} が欠落"))
            elif not same_build(c.read_bytes(), b.read_bytes()):
                problems.append(
                    (
                        d.name,
                        f"{STALE} (build/{c.name} was not built by this commit's pipeline)"
                        f" / 古い（build/{c.name} はこのコミットのパイプラインで生成されていない）",
                    )
                )
    return problems


def cast(commit: Path, built: Path, out: Path) -> list[tuple[str, str]]:
    manifest = commit / "assets" / "cast" / "cast.json"
    build = built / "assets" / "cast" / "build"
    link = out / "cast"
    if link.is_symlink() or link.exists():
        link.unlink()
    if not manifest.is_file():
        return []
    if build.is_dir():
        link.symlink_to(build.resolve(), target_is_directory=True)
    problems = []
    for name, c in json.loads(manifest.read_text(encoding="utf-8"))["characters"].items():
        for kind, f in c["files"].items():
            path = build / name / f"{kind}.glb"
            if not path.is_file():
                problems.append((f"{CHARACTER} {name}", f"{MISSING} {kind}.glb / {kind}.glb が欠落"))
                break
            if sha256(path) != f["sha256"]:
                problems.append(
                    (
                        f"{CHARACTER} {name}",
                        f"{STALE} ({kind}.glb's sha256 does not match cast.json)"
                        f" / 古い（{kind}.glb の sha256 が cast.json と合わない）",
                    )
                )
                break
    return problems


def main(argv: list[str]) -> None:
    if len(argv) != 4:
        sys.exit(__doc__)
    commit, built, out = Path(argv[1]).resolve(), Path(argv[2]).resolve(), Path(argv[3])
    problems = scenes(commit, built, out) + cast(commit, built, out)
    if not problems:
        print(
            "Scene packs and character files are all present and match the committed manifests"
            " / シーンパックと登場人物のファイルはすべて揃っており、コミットのマニフェストと一致"
        )
        return
    print("Scene packs or character files are incomplete / シーンパックか登場人物のファイルが揃っていない:")
    commands: list[str] = []
    for what, why in problems:
        print(f"  {what}: {why}")
        cmd = CAST if what.startswith(CHARACTER) else builder(what)
        if cmd not in commands:
            commands.append(cmd)
    print("Run at the repo root (with BPY_PYTHON set) / リポジトリのルートで実行（BPY_PYTHON を設定しておく）:")
    for cmd in commands:
        print(f"  {cmd}")
    sys.exit(1 if any(not why.startswith(STALE) for _, why in problems) else 2)


if __name__ == "__main__":
    main(sys.argv)
