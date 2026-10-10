"""Build dist/zoujin-spike.zip for zg's Mac: python3 make_zip.py

Bundles the scripts, tests, lockfile, README, snapshots of data engineering's world.json and S-068 probe set
(once it exists) and the frontend's S2 test page (as page/).
"""

import shutil
import tempfile
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORLD = HERE.parents[1] / "data" / "worlds" / "hashire-merosu" / "1.0.0-draft" / "world.json"
INCLUDE = ["README.md", "s1b-plan.md", "mac-s1b-run.md", "s1b_deploy.sh", "s1b", "pyproject.toml", "uv.lock", "zj_spike", "tests"]
# The frontend's S2 test page, served by the S-1b proxy from page/ (only when the frontend has written it).
PAGE = HERE.parents[1] / "frontend" / "spikes" / "s2-voice" / "page"
PROBES = HERE.parents[1] / "data" / "evals" / "probes" / "s3_spoiler_probes.json"
SELFHARM = HERE.parents[1] / "data" / "evals" / "safety" / "s4_selfharm.jsonl"  # S-069, once data engineering writes it


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "zoujin-spike"
        root.mkdir()
        for name in INCLUDE:
            src = HERE / name
            if src.is_dir():
                shutil.copytree(src, root / name, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            else:
                shutil.copy2(src, root / name)
        shutil.copy2(WORLD, root / "zj_spike" / "data" / "world.json")
        if PROBES.exists():
            shutil.copy2(PROBES, root / "zj_spike" / "data" / "s3_probes.json")
            print(f"included data engineering's probe set from {PROBES}")
        if SELFHARM.exists():
            shutil.copy2(SELFHARM, root / "zj_spike" / "data" / "s4_selfharm.jsonl")
            print(f"included data engineering's self-harm set from {SELFHARM}")
        if (PAGE / "index.html").exists():
            shutil.copytree(PAGE, root / "page", ignore=shutil.ignore_patterns(".*"))
            print(f"included the frontend test page from {PAGE}")
        out = HERE / "dist" / "zoujin-spike.zip"
        out.parent.mkdir(exist_ok=True)
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
            for path in sorted(root.rglob("*")):
                if path.is_dir():
                    z.write(path, path.relative_to(root.parent))
                    continue
                info = zipfile.ZipInfo.from_file(path, path.relative_to(root.parent))
                info.compress_type = zipfile.ZIP_DEFLATED
                if path.suffix == ".sh":
                    info.external_attr = 0o100755 << 16  # the deploy script stays executable after unzipping
                z.writestr(info, path.read_bytes())
    print(f"wrote {out} ({out.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
