"""Gateway and narrator configuration, read only from environment variables (B-0, B-2).

There are no settings for cloud credentials, project IDs or keys: with `ZJ_MODEL=real` the real clients read the project
and region set explicitly on the Mac themselves (`models/vertex.py`), and Claude's model IDs and key
(`models/claude.py`); other modes read none of them. Which provider and which model each prompt kind goes to (for Claude
only the tier name plus version), how deep it thinks and how long its deadline is are written only here (B-8). Local
development uses the values in `compose.yaml`.

ゲートウェイとナレーターの設定。環境変数からのみ読む（B-0、B-2）。

クラウドの認証情報・プロジェクト ID・キーの設定項目は一切ない：`ZJ_MODEL=real` のとき、
本物のクライアントが Mac で明示的に設定されたプロジェクトとリージョン（`models/vertex.py`）、
Claude のモデル ID とキー（`models/claude.py`）を自分で読み、ほかのモードでは読まない。
プロンプトの種類ごとにどのプロバイダー・どのモデル（Claude はティア名とバージョンだけ）を使うか、どこまで思考させるか、
タイムアウトをどれだけにするかはここにだけ書く（B-8）。ローカル開発では `compose.yaml` の値を使う。
"""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Literal

# services/backend/src/zoujin_backend/config.py → repo root / リポジトリのルート
REPO = Path(__file__).resolve().parents[4]

type ModelMode = Literal["fake", "replay", "real"]
MODEL_MODES: tuple[ModelMode, ...] = ("fake", "replay", "real")

type Provider = Literal["google", "claude"]


@dataclass(frozen=True)
class TextSpec:
    """How one prompt kind is called (the list in card B-8). fake and replay use only provider and model, to compute
    the replay key.

    1 種類のプロンプトの呼び方（B-8 カードの一覧）。fake と replay は provider と model
    だけを使ってリプレイのキーを計算する。
    """

    provider: Provider
    # Google: model ID; Claude: tier name plus version (as written by `zoujin_llm.model_tag`). Used by the replay key,
    # the ledger and `check.checker`. Claude's model IDs are given only on the Mac through environment variables
    # (CLAUDE_TIERS); the call is made only if the recognised tier name plus version equals this one.
    # Google：モデル ID。Claude：ティア名とバージョン（`zoujin_llm.model_tag` の書き方）。リプレイのキー、
    # 台帳、`check.checker` がこれを使う。Claude のモデル ID は Mac 上で環境変数（CLAUDE_TIERS）からだけ渡し、
    # 認識したティア名とバージョンがここと同じときだけ呼ぶ。
    model: str
    # Per-call deadline (seconds); on timeout cancel and immediately resend once (backend-design 2.4)
    # [provisional, decided by S-5]
    # 1 回の呼び出しのタイムアウト（秒）。超えたらキャンセルしてすぐに 1 回だけ再送する（backend-design 2.4）〔暫定、
    # S-5 で決める〕
    deadline: float
    max_output: int  # Output limit, including thinking / 出力の上限（思考を含む）
    # Google: thinkingLevel (LOW, MEDIUM), None = not set;
    # Claude: disabled (Haiku can turn it off), between_tools (no upfront thinking; Sonnet's minimum),
    # adaptive (adaptive).
    # Google：thinkingLevel（LOW、MEDIUM）、None = 設定しない。Claude：disabled（Haiku はオフにできる）、
    # between_tools（先に思考しない。Sonnet の最低はこれ）、
    # adaptive（適応的）。
    thinking: str | None = None
    effort: str | None = None  # Claude: output_config.effort (low, medium…), None = not sent / None = 送らない
    # Google only: Claude's Messages API has no such parameter (since SDK 1.13).
    # Google だけが使う：Claude の Messages API にはこのパラメーターがない（SDK 1.13 以降）。
    temperature: float | None = None


# Prompt kind → how it is called (B-8, D-028: everything that can use Claude uses Claude; `reply` only stands in for
# Live as a character in evals, so it stays on Google, S-085 ①). Extraction and checking use Sonnet first; S-2 and the
# first slice eval measure Haiku again, and S-085 ③ decides whether to switch.
# プロンプトの種類 → 呼び方（B-8、D-028：Claude を使えるものはすべて Claude。`reply` は評価で Live
# の代わりに登場人物を演じるだけなので Google に残す、S-085 ①）。抽出とチェックはまず Sonnet を使い、
# S-2 と最初のスライス評価で Haiku をもう一度測って、S-085 ③ に従って切り替えるかを決める。
TEXT: dict[str, TextSpec] = {
    "triage": TextSpec("claude", "haiku-5.5", 5.0, 256, thinking="disabled"),
    "extract": TextSpec("claude", "sonnet-5.5", 15.0, 4096, thinking="between_tools", effort="low"),
    "check": TextSpec("claude", "sonnet-5.5", 15.0, 8192, thinking="adaptive", effort="medium"),
    "rewrite": TextSpec("claude", "sonnet-5.5", 15.0, 4096, thinking="between_tools", effort="low"),
    "reply": TextSpec("google", "gemini-3.8-flash", 15.0, 1024, thinking="LOW", temperature=0.8),
    "narrate": TextSpec("claude", "sonnet-5.5", 10.0, 1024, thinking="between_tools", effort="low"),
    "plan": TextSpec("claude", "sonnet-5.5", 15.0, 4096, thinking="adaptive", effort="low"),
    # B-12: safety screening (S-072's 3-second deadline, resend once on timeout; B-8's table sets Haiku, thinking off)
    # B-12：安全スクリーニング（S-072 の 3 秒のタイムアウト、超えたら 1 回再送。B-8 の表で Haiku・思考オフと決めた）
    "safety": TextSpec("claude", "haiku-5.5", 3.0, 64, thinking="disabled"),
    # B-15 (S-072 ⑤): review of a first-pass signal (the stronger tier, no upfront thinking; 2.5 seconds; on timeout
    # or error the signal is kept, no resend)
    # B-15（S-072 ⑤）：1 回目の signal の再確認（強い方のティア、先に思考しない。2.5 秒。
    # タイムアウトでもエラーでも signal を残し、再送しない）
    "safety_review": TextSpec("claude", "sonnet-5.5", 2.5, 64, thinking="between_tools", effort="low"),
    # B-9: the ending must be fast, no upfront thinking. Mac probe (10-11, 20 runs): first token p95 about 2 s, full
    # p95 about 10 s, longest about 11 s, output about 970 tokens on average; deadline 20 seconds
    # B-9：エンディングは速さが必要なので先に思考しない。Mac のプローブ（10-11、20 回）：最初の文字 p95 約 2 秒、
    # 全体 p95 約 10 秒、最長約 11 秒、出力は平均約 970 トークン。タイムアウトは 20 秒
    "ending": TextSpec("claude", "sonnet-5.5", 20.0, 4096, thinking="between_tools", effort="low"),
    # B-17: model check of the ending (backend-design 2.9 step 4: do the three layers make sense, MEDIUM). A check
    # timeout does not block the ending; deadline 15 seconds
    # B-17：エンディングのモデルチェック（backend-design 2.9 第 4 段階、3 層の筋が通るか、MEDIUM）。
    # チェックがタイムアウトしてもエンディングは止めない。タイムアウトは 15 秒
    "ending-check": TextSpec("claude", "sonnet-5.5", 15.0, 2048, thinking="adaptive", effort="medium"),
    # B-13: one memory line, one "consequence that will not be undone" line (B-8's table: Haiku, thinking off; memory
    # 5 seconds, no resend on timeout, nothing written this turn; the consequence line 2 seconds (UX review: the
    # frontend waits for it before enabling 〔忘れてもらう〕), on timeout return null, not cached) B-13：
    # 記憶の一文と「取り消されない結果」の一文（B-8 の表：Haiku・思考オフ。記憶は 5 秒、タイムアウトでも再送せず、
    # このターンは書かない。結果の一文は 2 秒（UX レビュー：フロントエンドはそれが返ってから〔忘れてもらう〕を
    # 押せるようにする）、タイムアウトなら null を返し、キャッシュしない）
    "memory": TextSpec("claude", "haiku-5.5", 5.0, 256, thinking="disabled"),
    "keeps": TextSpec("claude", "haiku-5.5", 2.0, 128, thinking="disabled"),
    # B-21: suggested utterances (backend-design 3.6, section 8: Haiku, thinking off; must arrive within about 1 second
    # after the character finishes; 3-second deadline, otherwise none are shown)
    # B-21：発話の候補（backend-design 3.6・第 8 節：Haiku・思考オフ。登場人物が話し終えて約 1 秒以内に届く必要がある。
    # タイムアウトは 3 秒、間に合わなければ出さない）
    "suggest": TextSpec("claude", "haiku-5.5", 3.0, 256, thinking="disabled"),
    # B-16: world advance (act change, after a key moment, the middle of each act). Same tier as end-of-act plans; the
    # player does not wait for it (except at an act change), so the deadline is looser
    # B-16：世界の進行（幕の切り替え、重要な瞬間の後、各幕の中盤）。幕末のプランと同じティア。
    # プレイヤーは待たない（幕の切り替え時を除く）ので、タイムアウトを緩める
    "world": TextSpec("claude", "sonnet-5.5", 20.0, 4096, thinking="adaptive", effort="low"),
}
TEXT_MODELS: dict[str, str] = {k: v.model for k, v in TEXT.items()}
DEADLINES: dict[str, float] = {k: v.deadline for k, v in TEXT.items()}
# Claude tier → environment variable that gives the model ID on the Mac (IDs stay out of the repo, same as the data
# judges)
# Claude のティア → Mac 上でモデル ID を渡す環境変数（ID はリポジトリに入れない。データの審査員と同じ）
CLAUDE_TIERS: dict[str, str] = {"haiku": "ZJ_CLAUDE_HAIKU", "sonnet": "ZJ_CLAUDE_SONNET"}
# Temporary tier switch (S-085 ③: S-2 and the slice eval measure again with Haiku):
# `ZJ_TEXT_MODELS=check=haiku-5.5,extract=haiku-5.5`. Only the tier name plus version of the Claude kinds can change;
# thinking and effort stay as they are; the replay key, the ledger and `check.checker` follow the change
# 一時的なティア切り替え（S-085 ③：S-2 とスライス評価で Haiku
# でもう一度測る）：`ZJ_TEXT_MODELS=check=haiku-5.5,extract=haiku-5.5`。
# 変えられるのは Claude の種類のティア名とバージョンだけで、思考と effort はそのまま。リプレイのキー、
# 台帳、`check.checker` はそれに合わせて変わる
OVERRIDE_ENV = "ZJ_TEXT_MODELS"
_TAG = re.compile(r"(haiku|sonnet)-\d+\.\d+")


def text_spec(kind: str, env: Mapping[str, str] | None = None) -> TextSpec:
    """How this prompt kind is called this time: `TEXT` plus the `ZJ_TEXT_MODELS` tier switch.

    この種類のプロンプトを今回どう呼ぶか：`TEXT` に `ZJ_TEXT_MODELS` のティア切り替えを加えたもの。
    """
    base = TEXT[kind]
    value = (os.environ if env is None else env).get(OVERRIDE_ENV, "")
    for part in (x.strip() for x in value.split(",")):
        name, _, tag = part.partition("=")
        if name.strip() != kind:
            continue
        tag = tag.strip()
        if base.provider != "claude" or not _TAG.fullmatch(tag):
            raise ConfigError(
                f"{OVERRIDE_ENV} can only switch Claude prompts to haiku-x.y or sonnet-x.y, got {part!r} / "
                f"{OVERRIDE_ENV} で切り替えられるのは Claude のプロンプトを haiku-x.y か sonnet-x.y にすることだけ、"
                f"指定は {part!r}"
            )
        return replace(base, model=tag)
    return base


# Google unit prices: US dollars per 1 million tokens (docs/data/cost/pricing-2026-10-06.md, global endpoint). Claude's
# unit prices are in claude-prices.json of the shared package `zoujin_llm`, the only copy. Recorded at the list price
# on the bill: the 50% discount on 3.8 Flash until the end of 2026 is refunded afterwards, so the ledger does not
# deduct it and stops at the cap earlier than actual spend, never later. Regional endpoints (non-global) cost 10% more
# Google の単価：100 万トークンあたりの米ドル（docs/data/cost/pricing-2026-10-06.md、global エンドポイント）。
# Claude の単価は共有パッケージ `zoujin_llm` の claude-prices.json にあり、それが唯一のもの。請求書の定価で記録する：
# 3.8 Flash の 2026 年末までの半額は事後に返金されるので台帳では差し引かず、上限で止まるのは実際の支出より早くなり、
# 遅くはならない。リージョンエンドポイント（global 以外）は 10% 高い
PRICES: dict[str, dict[str, float]] = {
    "gemini-3.8-flash": {"input": 1.50, "cachedInput": 0.15, "output": 7.50},
    "gemini-3.5-flash-lite": {"input": 0.30, "cachedInput": 0.03, "output": 2.50},
}
REGIONAL_MARKUP = 1.10

# The world model used for new playthroughs. `ZJ_WORLD` (absolute path to world.json; E-0's runner sets it, to the
# slice with `--slice`) replaces it. We do not pick the newest by sorting directory names: the slice (1.0.0-slice)
# sorts after 1.0.0-draft, and sorting would silently put new playthroughs on the slice
# 新しいプレイに使う世界モデル。`ZJ_WORLD`（world.json の絶対パス。
# E-0 のランナーがこう設定し、`--slice` のときはスライス版）で置き換える。
# ディレクトリ名でソートして最新を選ぶことはしない：スライス（1.0.0-slice）は 1.0.0-draft の後ろに並ぶので、
# ソートすると新しいプレイが気づかないうちにスライスになってしまう
DEFAULT_WORLD = REPO / "worlds" / "hashire-merosu" / "1.0.0-draft" / "world.json"

REPLAYS = REPO / "fixtures" / "model-replays"

COOKIE = "zj_session"
# B-10: after how many turns each Live session is rebuilt (S-073 ⑤)
# B-10：Live セッションを何ターン話し終えたら作り直すか（S-073 ⑤）
LIVE_REBUILD_TURNS = 8
# Session cookie lasts 30 days, renewed on a sliding basis each time it is used (backend-design 5.2)
# セッション Cookie は 30 日、使うたびにスライド延長する（backend-design 5.2）
SESSION_DAYS = 30


class ConfigError(ValueError):
    pass


def model_mode(env: Mapping[str, str] | None = None) -> ModelMode:
    """`ZJ_MODEL`: fake (default), replay, real (only on zg's Mac, G-7).

    `ZJ_MODEL`：fake（デフォルト）、replay、real（zg の Mac 上だけ、G-7）。
    """
    value = (os.environ if env is None else env).get("ZJ_MODEL", "fake")
    for m in MODEL_MODES:
        if value == m:
            return m
    modes = " / ".join(MODEL_MODES)
    raise ConfigError(f"ZJ_MODEL must be {modes}, got {value!r} / ZJ_MODEL は {modes} のいずれか、指定は {value!r}")


def live_mode(env: Mapping[str, str], model: ModelMode) -> Literal["fake", "real"]:
    """`ZJ_LIVE`: fake / real (B-10); if unset it follows `ZJ_MODEL` (only real means real; replay uses the fake Live).

    `ZJ_LIVE`：fake / real（B-10）。未設定なら `ZJ_MODEL` に従う（real のときだけ real、replay の Live は偽物を使う）。
    """
    value = env.get("ZJ_LIVE", "") or ("real" if model == "real" else "fake")
    if value not in ("fake", "real"):
        raise ConfigError(
            f"ZJ_LIVE must be fake / real, got {value!r} / ZJ_LIVE は fake / real のいずれか、指定は {value!r}"
        )
    return "real" if value == "real" else "fake"


def rebuild_turns(env: Mapping[str, str]) -> int:
    """`ZJ_LIVE_REBUILD_TURNS`: after how many turns each Live session is replaced at a pause (B-10, dev-plan: 7〜10);
    default 8.

    `ZJ_LIVE_REBUILD_TURNS`：Live セッションを何ターン話し終えたら間で新しいものに替えるか（B-10、dev-plan：7〜10）。
    デフォルトは 8。
    """
    value = env.get("ZJ_LIVE_REBUILD_TURNS", "") or str(LIVE_REBUILD_TURNS)
    if not value.isdigit() or not 7 <= int(value) <= 10:
        raise ConfigError(
            f"ZJ_LIVE_REBUILD_TURNS must be 7〜10, got {value!r} / ZJ_LIVE_REBUILD_TURNS は 7〜10、指定は {value!r}"
        )
    return int(value)


def world_path(env: Mapping[str, str] | None = None) -> Path:
    """`ZJ_WORLD`: absolute path to world.json; `DEFAULT_WORLD` if unset.

    `ZJ_WORLD`：world.json の絶対パス。未設定なら `DEFAULT_WORLD`。
    """
    value = (os.environ if env is None else env).get("ZJ_WORLD", "")
    if not value:
        return DEFAULT_WORLD
    path = Path(value)
    if not path.is_absolute():
        raise ConfigError(
            f"ZJ_WORLD must be an absolute path to world.json, got {value!r} / "
            f"ZJ_WORLD には world.json の絶対パスを書く、指定は {value!r}"
        )
    if not path.is_file():
        raise ConfigError(f"The file ZJ_WORLD points to does not exist / ZJ_WORLD が指すファイルが存在しない: {value}")
    return path


def open_release(env: Mapping[str, str] | None = None) -> int:
    """`ZJ_RELEASE`: the manifest lists the roles whose `release` is not greater than it; 1 if unset (S-002).

    `ZJ_RELEASE`：manifest は `release` がこれ以下の役を出す。未設定なら 1（S-002）。
    """
    value = (os.environ if env is None else env).get("ZJ_RELEASE", "1")
    if not value.isdigit() or int(value) < 1:
        raise ConfigError(
            f"ZJ_RELEASE must be an integer of 1 or more, got {value!r} / "
            f"ZJ_RELEASE には 1 以上の整数を書く、指定は {value!r}"
        )
    return int(value)


WORLDS_FORMAT = (
    "ZJ_WORLDS must be a JSON array of absolute paths to world.json / "
    "ZJ_WORLDS には world.json の絶対パスの JSON 配列を書く"
)


def released_worlds(env: Mapping[str, str]) -> tuple[Path, ...]:
    """ZJ_WORLDS is a JSON array of absolute paths to world.json of additionally opened books; by default nothing
    extra is opened.

    ZJ_WORLDS は追加で公開する本の world.json の絶対パスを並べた JSON 配列。デフォルトでは追加公開しない。
    """
    import json

    try:
        values = json.loads(env.get("ZJ_WORLDS", "[]"))
    except ValueError:
        raise ConfigError(WORLDS_FORMAT) from None
    if not isinstance(values, list) or not all(isinstance(v, str) for v in values):
        raise ConfigError(WORLDS_FORMAT)
    paths = tuple(Path(v) for v in values)
    if any(not p.is_absolute() or not p.is_file() for p in paths):
        raise ConfigError(
            "Every file in ZJ_WORLDS must exist and be an absolute path / "
            "ZJ_WORLDS の各ファイルは存在し、絶対パスでなければならない"
        )
    return paths


def narrator_auth(env: Mapping[str, str]) -> Literal["none", "iam"]:
    """`ZJ_NARRATOR_AUTH`: none (default, local) / iam (Cloud Run: the narrator opens only an internal ingress and only
    the gateway's service account may call it, B-23).

    `ZJ_NARRATOR_AUTH`：none（デフォルト、ローカル）/ iam（Cloud Run：ナレーターは内部の入口だけを開き、
    ゲートウェイのサービスアカウントからの呼び出しだけを許す、B-23）。
    """
    value = env.get("ZJ_NARRATOR_AUTH", "") or "none"
    if value not in ("none", "iam"):
        raise ConfigError(
            f"ZJ_NARRATOR_AUTH must be none / iam, got {value!r} / "
            f"ZJ_NARRATOR_AUTH は none / iam のいずれか、指定は {value!r}"
        )
    return "iam" if value == "iam" else "none"


def async_url(url: str) -> str:
    """postgresql://… → SQLAlchemy's psycopg 3 driver form.

    postgresql://… → SQLAlchemy の psycopg 3 ドライバーの書き方。
    """
    for prefix in ("postgresql://", "postgres://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url.removeprefix(prefix)
    return url


@dataclass(frozen=True)
class Settings:
    database_url: str  # postgresql+psycopg://…
    model: ModelMode = "fake"
    # Dev switch: the session cookie has no Secure (local http), and the narrator does not check the caller's OIDC token
    # 開発スイッチ：セッション Cookie に Secure を付けない（ローカルの http）、
    # narrator は呼び出し元の OIDC トークンを確認しない
    dev: bool = False
    # Origins allowed besides the same origin (frontend dev server)
    # 同一オリジン以外に通す Origin（フロントエンドの開発サーバー）
    allow_origins: tuple[str, ...] = ()
    narrator_url: str = "http://127.0.0.1:8002"
    repo: Path = REPO
    # Fake Live intervals are multiplied by this: 0 = no waiting (tests)
    # 偽 Live の間隔に掛ける数：0 = 待たない（テスト）
    speed: float = 1.0
    live: Literal["fake", "real"] = "fake"  # B-10：ZJ_LIVE
    live_rebuild_turns: int = LIVE_REBUILD_TURNS
    fake_voice: Path = field(default=REPO / "fixtures" / "fake-voice")
    fake_text: Path = field(default=REPO / "fixtures" / "fake-text")
    # ZJ_REPLAYS switches to another directory (e.g. replays of the holdout set, kept out of the repo)
    # ZJ_REPLAYS で別のディレクトリに替える（例：ホールドアウトセットのリプレイ。リポジトリには入れない）
    replays: Path = REPLAYS
    # World model for new playthroughs; existing playthroughs use the version they locked
    # 新しいプレイに使う世界モデル。既存のプレイは自分が固定したバージョンを使う
    world: Path = DEFAULT_WORLD
    # Additionally opened books; drafts in the repo are not published automatically
    # 追加で公開する本。リポジトリ内の草稿は自動では公開しない
    released_worlds: tuple[Path, ...] = ()
    # Private preview gate, injected only from the environment / Secret
    # 非公開プレビューのゲート。環境変数 / Secret からのみ注入する
    site_password: str | None = field(default=None, repr=False)
    # manifest (B-7): up to which release roles are opened (S-002, first release 1), the scene pack directory (points to
    # the build output when deployed, S-075), the voice directory
    # manifest（B-7）：何版目までの役を公開するか（S-002、最初の版は 1）、
    # シーンパックのディレクトリ（デプロイ時はビルドの出力を指す、S-075）、音声のディレクトリ
    release: int = 1
    scene_packs: Path | None = None  # None = the repo's assets/scenes / None = リポジトリの assets/scenes
    # None = the repo's assets/voice (tests switch to a temp directory)
    # None = リポジトリの assets/voice（テストでは一時ディレクトリに替える）
    voices: Path | None = None
    deadlines: Mapping[str, float] = field(default_factory=lambda: dict(DEADLINES))
    # With real: the ledger (JSONL; both accounts in one file, the same one as E-0 live and the judges), each
    # provider's total cap (accumulated across all runs: D-027's Google 50 dollars, D-029's Claude 100 dollars), which
    # item to record under and that item's cap, and the directory for recording replays. The runner sets the caps into
    # the environment from command-line arguments (S-2's zoujin-s2, E-0's live); there are no defaults
    # real のとき：台帳（JSONL。2 つの勘定は同じファイルで、E-0 live・審査員と同じもの）、
    # 各プロバイダーの総上限（すべての実行で累計：D-027 の Google 50 ドル、D-029 の Claude 100 ドル）、
    # どの項目に記録するかとその項目の上限、リプレイを録るディレクトリ。
    # 上限はランナーがコマンドライン引数から環境に設定する（S-2 の zoujin-s2、E-0 の live）。デフォルトはない
    ledger: Path | None = None
    max_google_usd: float | None = None
    max_claude_usd: float | None = None
    ledger_item: str | None = None
    max_item_usd: float | None = None
    record_replays: Path | None = None
    # Deployment (B-23): the gateway also serves the frontend build (`ZJ_WEB_DIST`, vite build's dist; not served if
    # unset); identity for service-to-service calls (`ZJ_NARRATOR_AUTH=iam`: Cloud Run's IAM has already verified the
    # gateway service account's OIDC token; the gateway attaches the token when calling the narrator)
    # デプロイ（B-23）：ゲートウェイがフロントエンドのビルドも配信する（`ZJ_WEB_DIST`、vite build の dist。
    # 未設定なら配信しない）。サービス間呼び出しの ID（`ZJ_NARRATOR_AUTH=iam`：
    # Cloud Run の IAM がゲートウェイのサービスアカウントの OIDC トークンを検証済みで、
    # ゲートウェイはナレーターを呼ぶときにトークンを付ける）
    web_dist: Path | None = None
    narrator_auth: Literal["none", "iam"] = "none"

    @property
    def schemas(self) -> Path:
        return self.repo / "packages" / "contracts" / "schemas"

    @property
    def worlds(self) -> Path:
        return self.repo / "worlds"

    @property
    def scenes(self) -> Path:
        return self.repo / "assets" / "scenes"

    @property
    def packs(self) -> Path:
        return self.scene_packs or self.scenes

    @property
    def voice_dir(self) -> Path:
        return self.voices or self.repo / "assets" / "voice"

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Settings:
        e = os.environ if env is None else env
        url = e.get("DATABASE_URL")
        if not url:
            raise ConfigError(
                "No DATABASE_URL (locally: docker compose up db, see services/backend/README.md) / "
                "DATABASE_URL がない（ローカルでは docker compose up db、services/backend/README.md を参照）"
            )
        origins = tuple(o.strip() for o in e.get("ZJ_ALLOW_ORIGINS", "").split(",") if o.strip())
        return cls(
            database_url=async_url(url),
            model=model_mode(e),
            dev=e.get("ZJ_DEV", "") == "1",
            allow_origins=origins,
            narrator_url=e.get("ZJ_NARRATOR_URL", cls.narrator_url),
            speed=float(e.get("ZJ_SPEED", "1")),
            live=live_mode(e, model_mode(e)),
            live_rebuild_turns=rebuild_turns(e),
            world=world_path(e),
            released_worlds=released_worlds(e),
            site_password=e.get("ZJ_SITE_PASSWORD") or None,
            release=open_release(e),
            scene_packs=_dir(e, "ZJ_SCENE_PACKS"),
            ledger=_path(e, "ZJ_LEDGER"),
            max_google_usd=float(e["ZJ_MAX_GOOGLE_USD"]) if e.get("ZJ_MAX_GOOGLE_USD") else None,
            max_claude_usd=float(e["ZJ_MAX_CLAUDE_USD"]) if e.get("ZJ_MAX_CLAUDE_USD") else None,
            ledger_item=e.get("ZJ_LEDGER_ITEM") or None,
            max_item_usd=float(e["ZJ_MAX_ITEM_USD"]) if e.get("ZJ_MAX_ITEM_USD") else None,
            record_replays=_path(e, "ZJ_RECORD_REPLAYS"),
            replays=_path(e, "ZJ_REPLAYS") or REPLAYS,
            web_dist=_dir(e, "ZJ_WEB_DIST"),
            narrator_auth=narrator_auth(e),
        )


def _path(env: Mapping[str, str], name: str) -> Path | None:
    value = env.get(name, "")
    if not value:
        return None
    path = Path(value)
    if not path.is_absolute():
        raise ConfigError(
            f"{name} must be an absolute path, got {value!r} / {name} には絶対パスを書く、指定は {value!r}"
        )
    return path


def _dir(env: Mapping[str, str], name: str) -> Path | None:
    path = _path(env, name)
    if path is not None and not path.is_dir():
        raise ConfigError(
            f"The directory {name} points to does not exist / {name} が指すディレクトリが存在しない: {path}"
        )
    return path
