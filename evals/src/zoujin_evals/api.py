"""How the runner calls the backend's eval entry point zoujin_backend.eval_api (api-contract section 7; B-0 item 9
built the minimal version).

Only the shapes the runner depends on are written here; the backend implements them and does not need to inherit
these classes:

- The module-level function setup(setup, *, mode) starts a game and returns a session. setup is the case's setup as is
  (the runner neither simulates nor fills in fields), and mode is the case's mode (text / voice).
- The session has one method per kind of step; each call is one step. Steps are numbered from 1 and match the index
  of the case's steps (from_step of delete_memory, step of retract and step of utterance_cleared all use this number).
  Each step returns a StepResult.
- Queries can be called at any time: state(), events(), memories(), trust(), utterance_cleared(), db_absent(),
  ending(). After new_playthrough() queries answer about the new game; after delete_playthrough() db_absent() answers
  about the deleted game.
- Steps and queries that are not implemented raise EvalNotImplemented("name"); not found in the replay raises
  ReplayMissing. The runner recognises them by exception class name; B-0 defines both classes in
  zoujin_backend.eval_api. A method missing from the session also counts as not implemented.
- ZJ_MODEL (fake / replay) and ZJ_WORLD (absolute path of world.json; 1.0.0-slice with `--slice`) are set by the runner
  before calling setup(), and the backend reads them on every setup().
- Simulated games (setup with persona + seed): the backend uses them only to set the role, the starting point and the
  fake model's seed; the AI player lives in the runner and calls say / act / propose / choose step by step according
  to the persona, and the runner itself records what the player said (agreed with the backend on 2026-10-10).
- check() is not a case step: S-2 uses it to hand one candidate event to the narrator's steps 3 and 4, without
  committing.

ランナーがバックエンドの評価エントリ zoujin_backend.eval_api をどう呼ぶか（api-contract 第 7 節。B-0 第 9 条が最小版を
作った）。

ここにはランナーが依存する形だけを書く。バックエンドはそれに従って実装し、ここのクラスを継承する必要はない：

- モジュールレベルの関数 setup(setup, *, mode) が局を始め、セッションを返す。setup はケースの setup そのもの（ランナーは
  シミュレーションもフィールドの補完もしない）、mode はケースの mode（text / voice）。
- セッションにはステップの種類ごとにメソッドが 1 つあり、1 回の呼び出しが 1 ステップ。ステップ番号は 1 から始まり、
  ケースの steps の添字と一致する（delete_memory の from_step、retract の step、utterance_cleared の step はすべてこの
  番号）。各ステップは StepResult を返す。
- クエリはいつでも呼べる：state()、events()、memories()、trust()、utterance_cleared()、db_absent()、ending()。
  new_playthrough() の後のクエリは新しい局について答え、delete_playthrough() の後の db_absent() は削除された局について
  答える。
- 未実装のステップとクエリは EvalNotImplemented("名前") を投げる。リプレイに見つからなければ ReplayMissing を投げる。
  ランナーは例外のクラス名で認識し、B-0 は zoujin_backend.eval_api でこの 2 つのクラスを定義する。セッションにない
  メソッドも未実装とみなす。
- ZJ_MODEL（fake / replay）と ZJ_WORLD（world.json の絶対パス。`--slice` のときは 1.0.0-slice）はランナーが setup() を
  呼ぶ前に設定し、バックエンドは setup() のたびに読む。
- シミュレーション局（setup に persona + seed）：バックエンドはこれでロール、開始点、偽モデルのシードを決めるだけ。
  AI プレイヤーはランナー内にあり、ペルソナに従って say / act / propose / choose を一歩ずつ呼ぶ。プレイヤーの発言は
  ランナー自身が記録する（2026-10-10 にバックエンドと取り決め）。
- check() はケースのステップではない：S-2 がこれを使って候補イベントを 1 つナレーターの第 3、4 ステップに渡し、
  コミットはしない。
"""

from __future__ import annotations

import importlib
from collections.abc import Mapping, Sequence
from typing import Any, Literal, NotRequired, Protocol, TypedDict

type Json = Any
type Event = dict[str, Json]  # the Event of contract section 3 / 契約第 3 節の Event


class SafetyCard(TypedDict):
    """Crisis card (S-043, S-057).

    危機カード（S-043、S-057）。
    """

    shown: bool  # the card appeared at this step / このステップでカードが出た
    # the story is paused (no events and no character speaks while paused)
    # 物語が一時停止した（一時停止中はイベントがなく、人物も話さない）
    paused: bool
    canReturn: bool  # the player can return to the story from the card / プレイヤーはカードから物語に戻れる


class StepResult(TypedDict):
    """The result of one step (api-contract section 7 "what each step returns").

    The backend may leave out fields it cannot provide; checks that use them record "skipped: backend not implemented
    (StepResult.field)".

    1 ステップの結果（api-contract 第 7 節「各ステップの戻り値」）。

    バックエンドが出せないフィールドは省いてよく、それを使うチェックは「スキップ：バックエンド未実装
    （StepResult.フィールド）」と記録する。
    """

    # the character's reply text; None when the character did not speak / 人物の返答の文字。話さなかったら None
    reply: NotRequired[str | None]
    # the character spoke but there is no text (backend-design 3.1); recorded as "no character text"
    # 人物が話したが文字がない（backend-design 3.1）。「原文なし」と記録する
    characterTextMissing: NotRequired[bool]
    # All events this step wrote to the log, in seq order, each with eventId and seq: the candidate events (committed
    # and vetoed) and the system events settled when due within this step (origin = schedule). For a vetoed one, check
    # is added to the candidate's original effects (in the log its effects are empty, contract section 3).
    # このステップでログに書かれた全イベント。seq 順で、どれも eventId と seq を持つ：候補イベント（コミットされた
    # ものと拒否されたもの）と、このステップ内で時刻が来て決着したシステムイベント（origin = schedule）。拒否された
    # ものは候補の元の effects に check を加える（ログ上の effects は空、契約第 3 節）。
    events: NotRequired[list[Event]]
    clockMinutes: NotRequired[int]  # how many minutes the clock advanced / 時計が何分進んだか
    safetyCard: NotRequired[SafetyCard]
    # the plan when an end-of-act plan goes ahead (contract Event.plan)
    # 幕末のプランが成立したときの plan（契約 Event.plan）
    plan: NotRequired[dict[str, Json] | None]
    # alternative destinations the backend returns when an end-of-act plan does not go ahead
    # 幕末のプランが成立しないときにバックエンドが返す代わりの行き先
    alternatives: NotRequired[list[dict[str, Json]]]
    followups: NotRequired[int]  # how many follow-up questions after silence / silence の後に人物が何回追問したか
    traceId: NotRequired[str]


class EvalSession(Protocol):
    """One game. Parameter names of steps and queries follow api-contract section 7, in snake case for Python.

    1 局。ステップとクエリの引数名は api-contract 第 7 節に従い、Python ではスネークケースにする。
    """

    def say(self, to: str, text: str) -> StepResult: ...
    def act(
        self, kind: str, target: str | None, params: Mapping[str, Json], *, action_id: str | None = None
    ) -> StepResult: ...
    def delete_memory(self, character: str, from_step: int) -> StepResult: ...
    def delete_memory_id(self, memory_id: str) -> StepResult: ...
    def confirm(self, answer: str | None) -> StepResult: ...
    def retract(self, step: int) -> StepResult: ...
    def delete_playthrough(self) -> StepResult: ...
    def new_playthrough(self) -> StepResult: ...
    def advance(self, minutes: int) -> StepResult: ...
    def silence(self, seconds: int) -> StepResult: ...
    def propose(self, text: str) -> StepResult: ...
    def choose(self, exit: str, en_route: int | None = None) -> StepResult: ...

    def check(self, candidate: Mapping[str, Json], turn: Mapping[str, Json], model_checks: str = "scoped") -> Json:
        """S-2: returns {"check": CheckResult, "rules": [{"rule", "status": pass / fail / skipped, "reason"?}]}.
        Does not commit.

        S-2：{"check": CheckResult, "rules": [{"rule", "status": pass / fail / skipped, "reason"?}]} を返す。
        コミットはしない。
        """
        ...

    def state(self) -> dict[str, Json]: ...  # the WorldState of contract 3.1 / 契約 3.1 の WorldState
    # all events of this game (including those the eval set up and vetoed ones), by seq
    # この局の全イベント（評価が配置したもの、拒否されたものを含む）、seq 順
    def events(self) -> list[Event]: ...
    # the MemoryItem of contract 4, including deleted ones / 契約 4 の MemoryItem、削除済みを含む
    def memories(self, character: str) -> list[dict[str, Json]]: ...
    # the public projection of the official 記憶帳, for the simulated player
    # 正式な記憶帳の公開投影。シミュレーションのプレイヤーが使う
    def memory_book(self) -> dict[str, Json]: ...
    def trust(self, character: str) -> int: ...
    # the utterances (the player's and the character's) of that step's turn are all cleared
    # このステップのターンの原文（プレイヤーと人物の）がすべて消去された
    def utterance_cleared(self, step: int) -> bool: ...
    # how many rows of this game can still be found in each table / 各テーブルでこの局の行がまだ何行見つかるか
    def db_absent(self, tables: Sequence[str]) -> Mapping[str, int]: ...
    # the Ending of contract section 5; None when no ending was reached (the check fails)
    # 契約第 5 節の Ending。結末に入っていなければ None（チェックは不合格）
    def ending(self) -> dict[str, Json] | None: ...


class EvalApi(Protocol):
    def setup(self, setup: Mapping[str, Json], *, mode: Literal["text", "voice"]) -> EvalSession: ...


BACKEND_MODULE = "zoujin_backend.eval_api"


def load_backend() -> EvalApi | None:
    """The backend's eval entry point; None while B-0 does not have it yet (every case records "skipped: backend not
    implemented (eval_api)").

    バックエンドの評価エントリ。B-0 にまだなければ None を返す（各ケースは「スキップ：バックエンド未実装（eval_api）」と
    記録する）。
    """
    try:
        module: EvalApi = importlib.import_module(BACKEND_MODULE)
    except ModuleNotFoundError as e:
        if e.name is not None and BACKEND_MODULE.startswith(e.name):
            return None
        raise
    return module


class EvalNotImplemented(Exception):
    """Used by the runner itself: the session has no method for this step or query; handled like the backend's
    exception of the same name.

    ランナー自身が使う：セッションにこのステップやクエリのメソッドがない。バックエンドが投げる同名の例外と同じに扱う。
    """


def not_implemented(e: BaseException) -> str | None:
    """An exception by which the backend says "not implemented": return the name of what is not implemented, or None
    for any other exception.

    バックエンドが「未実装」と言う例外：未実装のものの名前を返す。この種の例外でなければ None を返す。
    """
    if any(c.__name__ == "EvalNotImplemented" for c in type(e).__mro__):
        return str(e.args[0]) if e.args else "?"
    return None


def replay_missing(e: BaseException) -> bool:
    """Not found in the replay (B-0's ReplayMissing): recorded as "replay missing or stale", not treated as a pass, and
    no fallback to the fake model.

    リプレイに見つからない（B-0 の ReplayMissing）：「リプレイが無いか期限切れ」と記録し、合格扱いにせず、偽モデルにも
    戻らない。
    """
    return any(c.__name__ == "ReplayMissing" for c in type(e).__mro__)
