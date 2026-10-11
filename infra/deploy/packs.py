"""部署用的场景包和人物文件（B-23），由 deploy.sh build 在 zg 的 Mac 上跑。

    python packs.py <部署的提交的工作树> <Mac 上生成过的仓库> <输出目录>

场景包、人物模型不进 git（S-075），由各自的流水线在 Mac 的仓库里生成：场景 `assets/scenes/<目录>/build/`，人物
`assets/cast/build/<名字>/`。这里在 <输出目录> 下建 `scenes/<目录>` → 那个 build 的符号链接（vite build 的
ZOUJIN_SCENE_ROOT、网关的 ZJ_SCENE_PACKS 都读它），`cast` → `assets/cast/build`（ZOUJIN_CAST_ROOT），再查：

- 缺：仓库里有清单（scene.json、index.json、pack.json）的场景目录没有 build/，或 cast.json 列的人物文件没有；
- 旧：build 里的清单和部署的这个提交里的不一样（流水线的 final 会把清单刷回仓库，一样才说明是同一次生成），人物文件的
  sha256 和 cast.json 对不上。

有缺或旧就打印是哪几个、该跑哪条命令：有缺退出码 1，只有旧退出码 2；全齐退出码 0。
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ENTRIES = ("index.json", "scene.json", "pack.json")
# 场景目录 → 生成它的命令（在仓库根跑，final）
BUILDERS = {
    "syracuse-square": "assets/pipeline/plaza/build.sh final && assets/pipeline/crowd/build.sh",
    "castle-throne": "assets/pipeline/castle/build.sh final",
    "village": "assets/pipeline/village/build.sh final",
    "village-interior": "assets/pipeline/village/build.sh final",
    "road-river": "assets/pipeline/road/build.sh final",
    "road-river-calm": "assets/pipeline/road/build.sh final",
    "road-river-flood": "assets/pipeline/road/build.sh final",
}
REST = "assets/pipeline/road/build_rest.sh final"  # 归途其余几处（F-15）：road-pass、-spring、-field、road-run-*
CAST = "assets/pipeline/cast/build.sh"


def builder(name: str) -> str:
    if name in BUILDERS:
        return BUILDERS[name]
    if name.startswith(("road-pass", "road-spring", "road-field", "road-run")):
        return REST
    if name.startswith("village-light-"):
        return BUILDERS["village"]  # 村子的黄昏、夜、雨的光照子包（F-11），村子的 final 一起生成
    if name == "road-common":
        return "assets/pipeline/road/build.sh final"  # 共用的路边包：河、村子、其余几处的 final 都往里加
    return f"（不知道哪条流水线生成 {name}，问前端）"


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
            problems.append((d.name, "缺"))
            continue
        link.symlink_to(build.resolve(), target_is_directory=True)
        for c in committed:
            b = build / c.name
            if not b.is_file():
                problems.append((d.name, f"缺 build/{c.name}"))
            elif b.read_bytes() != c.read_bytes():
                problems.append((d.name, f"旧（build/{c.name} 和提交的不一样）"))
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
                problems.append((f"人物 {name}", f"缺 {kind}.glb"))
                break
            if sha256(path) != f["sha256"]:
                problems.append((f"人物 {name}", f"旧（{kind}.glb 的 sha256 和 cast.json 对不上）"))
                break
    return problems


def main(argv: list[str]) -> None:
    if len(argv) != 4:
        sys.exit(__doc__)
    commit, built, out = Path(argv[1]).resolve(), Path(argv[2]).resolve(), Path(argv[3])
    problems = scenes(commit, built, out) + cast(commit, built, out)
    if not problems:
        print("场景包和人物文件都齐，和提交的清单一致")
        return
    print("场景包或人物文件不齐：")
    commands: list[str] = []
    for what, why in problems:
        print(f"  {what}：{why}")
        cmd = CAST if what.startswith("人物") else builder(what)
        if cmd not in commands:
            commands.append(cmd)
    print("在仓库根（BPY_PYTHON 设好）跑：")
    for cmd in commands:
        print(f"  {cmd}")
    sys.exit(1 if any(not why.startswith("旧") for _, why in problems) else 2)


if __name__ == "__main__":
    main(sys.argv)
