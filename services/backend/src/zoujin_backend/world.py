"""世界模型和场景布局（只读）。

- 世界模型：`worlds/<bookId>/<版本目录>/world.json`，按 `worldModelVersion` 找；一局开局时锁定版本（data-design 4.5）。
- 场景布局：`assets/scenes/<场景>/scene.json`（前端的流水线生成）的 `defaultPlace`、`places`、`spots`、`exits`、
  `startSpots`。有布局的场景才能投影位置点；还没有布局的场景，位置点用地点 ID 的最后一段。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path
from typing import Any

from zoujin_backend.clock import Labels

Json = Any


@dataclass(frozen=True)
class Scene:
    scene_id: str
    places: tuple[str, ...]  # 第一个是 defaultPlace
    spots: dict[str, str]  # 位置点 → 地点，按布局里的顺序
    exits: tuple[dict[str, str], ...]  # {place, spot}
    start_spots: dict[str, str]  # 地点 → 玩家站的位置点

    @classmethod
    def read(cls, path: Path) -> Scene:
        d = json.loads(path.read_text(encoding="utf-8"))
        places = [d["defaultPlace"], *(p["id"] for p in d.get("places", []) if p["id"] != d["defaultPlace"])]
        return cls(
            scene_id=d["sceneId"],
            places=tuple(places),
            spots={k: v["place"] for k, v in d.get("spots", {}).items()},
            exits=tuple({"place": e["place"], "spot": e["spot"]} for e in d.get("exits", [])),
            start_spots=dict(d.get("startSpots", {})),
        )

    def player_spot(self, place: str) -> str:
        if place in self.start_spots:
            return self.start_spots[place]
        return next((s for s, p in self.spots.items() if p == place and not s.startswith("way.")), _slug(place))

    def character_spots(self, people: list[tuple[str, str]], taken: set[str] | None = None) -> dict[str, str]:
        """人物按顺序占自己地点里还空着的位置点（布局顺序，way.* 和 taken 除外）；不够了就和最后一个重叠。
        taken 给玩家站的点，人物不站到玩家身上。"""
        taken = set(taken or ())
        out: dict[str, str] = {}
        for who, place in people:
            free = [s for s, p in self.spots.items() if p == place and not s.startswith("way.") and s not in taken]
            spot = free[0] if free else next((s for s, p in self.spots.items() if p == place), _slug(place))
            taken.add(spot)
            out[who] = spot
        return out


def _slug(place_id: str) -> str:
    return place_id.removeprefix("place.")


@dataclass
class Book:
    """一本书的一个世界模型版本。"""

    book_id: str
    world: Json
    scenes: dict[str, Scene] = field(default_factory=dict)

    @property
    def version(self) -> str:
        v: str = self.world["worldModelVersion"]
        return v

    @cached_property
    def labels(self) -> Labels:
        return Labels(self.world)

    def label(self, t: int) -> str:
        return self.labels.label(t)

    @cached_property
    def characters(self) -> dict[str, Json]:
        return {c["id"]: c for c in self.world["characters"]}

    @cached_property
    def roles(self) -> dict[str, Json]:
        return {r["id"]: r for r in self.world["roles"]}

    @cached_property
    def acts(self) -> dict[str, Json]:
        return {a["id"]: a for a in self.world["acts"]}

    @cached_property
    def beats(self) -> dict[str, Json]:
        return {b["id"]: b for b in self.world["beats"]}

    @cached_property
    def places(self) -> dict[str, Json]:
        return {p["id"]: p for p in self.world["places"]}

    def act_of(self, state_vars: Json) -> str:
        act: str = state_vars.get("var.act.current") or min(self.world["acts"], key=lambda a: a["order"])["id"]
        return act

    def scene_of(self, place: str, act: str) -> str:
        """玩家所在地点属于哪个场景：有布局的按布局，否则取这一幕的第一个场景。"""
        for s in self.scenes.values():
            if place in s.places:
                return s.scene_id
        scenes: list[str] = self.acts[act]["scenes"]
        return scenes[0]


class Library:
    """仓库里全部的世界模型和场景布局，开进程时读一次。"""

    def __init__(self, worlds: Path, scenes: Path) -> None:
        layouts = {}
        for p in sorted(scenes.glob("*/scene.json")):
            s = Scene.read(p)
            layouts[s.scene_id] = s
        self.by_version: dict[str, Book] = {}
        self.latest: dict[str, Book] = {}
        for p in sorted(worlds.glob("*/*/world.json")):
            w = json.loads(p.read_text(encoding="utf-8"))
            book = Book(book_id=w["book"]["id"], world=w)
            book.scenes = {k: v for k, v in layouts.items() if k in {s["id"] for s in w["scenes"]}}
            self.by_version[book.version] = book
            self.latest[book.book_id] = book  # 目录名排序后的最后一个

    def book(self, book_id: str) -> Book | None:
        return self.latest.get(book_id)

    def version(self, world_model_version: str) -> Book:
        return self.by_version[world_model_version]
