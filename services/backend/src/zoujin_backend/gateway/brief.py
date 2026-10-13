"""Live 会话的系统指令（B-10，backend-design 2.3）：规则（`prompt_texts/live.txt`）+ 人设 + 此刻的局势 + 话し相手 +
さっきまでの会話。

- 人设、局势、玩家三段用叙事者给 `reply` 的同一套（`narrator/view.py` 的 `persona`、`situation`、`player_card`），
  排成日语的条目。所以知情边界（S-086：不知道日名那条事实的人物只给时段）和评测里的人物一样。
- **不放世界模型前缀**：Live 每轮把整段上下文重新计费，前缀放进去每轮多约 0.03 美元〔推算〕。
- 「さっきまでの会話」：网关内存里这个人物最近几轮的文字（跳过作废、删除的），只在内存里，不落库、不进 Trace。
- 局势的条目（`facts`）也用来算中途更新：和上次送进会话的比，只送变了的（`changes`）。
- 版本号 = 规则文本的哈希（同 `Prompt.version` 的做法），记进 Trace 的 `live.session`。
- `live.txt` 和叙事者的 `reply.txt` 是一对（提示文本里不能写注释，写在这里）：S-068 的结论改 `reply.txt` 时，`live.txt`
  同一个 PR 跟着改（#111 数据评审）。
- 「気をつけること」：B-12 输出侧监控的提示（`monitor.notes`），开会话时带上；剧透纠正不点名那个词。
- 玩家的称呼用「話し相手」那一段的名字（`player_card` 的 `name`，即身份名；契约 1.8 起身份名只指玩家）。
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from functools import cache
from typing import Any

from zoujin_worldsim import OCCURRED, SimState

from zoujin_backend.models.live import Recent
from zoujin_backend.models.prompts import text
from zoujin_backend.narrator import roles
from zoujin_backend.narrator.view import persona, player_card, situation, state_view
from zoujin_backend.world import Book

Json = Any


@cache
def rules() -> str:
    return text("live")


def version() -> str:
    return "l" + hashlib.sha256(rules().encode()).hexdigest()[:12]


@dataclass(frozen=True)
class Brief:
    system: str
    facts: tuple[str, ...]  # 局势的条目（「時：…」「場所：…」「知っていること：…」），中途更新时比较


def _names(book: Book) -> dict[str, str]:
    out = {c["id"]: c["name"] for c in book.world["characters"]}
    out |= {p["id"]: p["name"] for p in book.world["places"]}
    return out


def _by_world(book: Book, state: SimState, who: str, fact: str) -> bool:
    """按世界模型（`Character.knows`）他此刻本来就知道：since 是 pre，或那个节拍已经发生 / 改写了。"""
    beats = state["beats"]
    return any(
        k["fact"] == fact and (k["since"] == "pre" or beats.get(k["since"]) in OCCURRED)
        for k in book.characters[who].get("knows", [])
    )


def situation_facts(book: Book, state: SimState, who: str, forgotten: frozenset[str] = frozenset()) -> tuple[str, ...]:
    view = state_view(book, state)
    s = situation(book, state, who, view)
    names = _names(book)
    statements = {f["id"]: f["statement"] for f in book.world["facts"]}
    run = state["runFacts"]
    lines = [f"時：{s['time']}", f"場所：{names.get(s['place'], s['place'])}"]
    here = [names.get(c, c) for c in s["present"]]
    lines.append("近くにいる人：" + ("、".join(here) if here else "（いない）"))
    visible_facts: set[str] = set()
    for k in s["knows"]:
        real = view.real(k)
        if real in forgotten and not _by_world(book, state, who, real):  # 世界模型让他知道的照给（数据复看）
            continue
        if real in statements:
            lines.append("知っていること：" + statements[real])
            visible_facts.add(real)
        elif real in run:
            lines.append("知っていること：" + str(run[real]["statement"]))
    # 亲历的时间只标在已经获准给人物的事实上。整段 beat.summary 是全知叙述，
    # 可能含尚未发生的时长、他人内心或原作相对日期，不能当作人物亲历注入。
    for recent in s["recent"]:
        beat = book.beats[recent["beat"]]
        variant = next((v for v in beat.get("variants", []) if v["id"] == recent.get("variant")), None)
        if state["beats"].get(beat["id"]) == "altered" and variant is None:
            # 自由改写的节拍没有原作摘要的权限，不能拿原作结果冒充本局亲历。
            continue
        for fact in book.world["facts"]:
            if fact["id"] in visible_facts and fact["trueFrom"] == beat["id"]:
                lines.append(f"これまでに見聞きしたこと：（{recent['day']}）{fact['statement']}")
    return tuple(lines)


def build(
    book: Book,
    state: SimState,
    who: str,
    recent: Sequence[Recent] = (),
    notes: Sequence[str] = (),
    memories: Sequence[str] = (),
    forgotten: frozenset[str] = frozenset(),
    *,
    samples: int = 4,
) -> Brief:
    """notes：B-12 输出侧监控给这个人物加的几句提示（剧透纠正、问句过多、不往死亡推，`gateway/monitor.py`），
    放在「# いまの状況」后面的「# 気をつけること」。只在开会话时带上（中途更新只比较 `facts`）。
    memories：B-13 这个人物对玩家没删的记忆（`narrator/memory.memories_for_brief`，按 salience 取、按时间排），
    放在「# いまの状況」后面的「# 覚えていること」；在記憶帳删了的不在这里，会话也随删除重建。
    forgotten：删了的记忆的来源事件里他才学到的事实（`narrator/memory.forgotten_facts`），「知っていること」不带
    （UX 评审：人物就是不知道这件事，玩家再提他当新的事听）。作废的约定和 forget 事件本来就不进局势说明。
    samples：「口ぶりの例」几句（B-14 节约档 2 句；记忆条数和最近对话的轮数由调用的人截）。"""
    p = persona(book, state, who)
    me = player_card(book, state, who)
    facts = situation_facts(book, state, who, forgotten)
    out = [rules(), "", "# あなた", f"名前：{p['name']}"]
    if p.get("summary"):
        out.append(str(p["summary"]))
    if p["traits"]:
        out.append("人柄：" + "／".join(p["traits"]))
    if p["goals"]:
        out.append("いまの目的：" + "／".join(p["goals"]))
    speech = p.get("speech") or {}
    if speech.get("firstPerson"):
        out.append(f"一人称：{speech['firstPerson']}")
    if speech.get("register"):
        out.append(f"口調：{speech['register']}")
    for q in speech.get("sampleLines", [])[:samples]:
        out.append(f"口ぶりの例：「{q}」")
    out += ["", "# いまの状況"]
    out += [f"- {x}" for x in facts]
    if memories:
        out += ["", "# 覚えていること"]
        out += [f"- {x}" for x in memories]
    if notes:
        out += ["", "# 気をつけること"]
        out += [f"- {x}" for x in notes]
    out += ["", "# 話し相手", f"{me['name']}（{'顔見知り' if me['knownToYou'] else '初めて会う相手'}）"]
    out += roles.brief_lines(book, state, who)  # B-19
    said = [r for r in recent if r.player or r.reply]
    if said:
        out += ["", "# さっきまでの会話"]
        for r in said:
            if r.player:
                out.append(f"{me['name']}：{_flat(r.player)}")
            if r.reply:
                out.append(f"あなた：{_flat(r.reply)}")
    return Brief("\n".join(out), facts)


def changes(old: Sequence[str], new: Sequence[str]) -> str | None:
    """中途更新：只送新出现的条目（变了的时刻、地点、在场的人，新知道的事）。没有变化回 None。"""
    added = [x for x in new if x not in set(old)]
    if not added:
        return None
    return "【状況の変化】\n" + "\n".join(f"- {x}" for x in added)


def _flat(s: str) -> str:
    """原话里的换行和「#」开头不让它冒充指令的段落。"""
    return " ".join(s.split()).lstrip("#")
