# Generated file, do not edit by hand: change packages/contracts/schemas/ and run `uv run contracts-gen`.
# 生成ファイル。手で編集しないこと：packages/contracts/schemas/ を変更して `uv run contracts-gen` を実行する。

from __future__ import annotations

from typing import Annotated, Any, Literal, TypeAliasType

from pydantic import BaseModel, ConfigDict, Field

type ActId = Annotated[str, Field(pattern="^act\\.[a-z0-9]+(?:[.-][a-z0-9]+)*$", title="ActId")]
"""
Act: `act.` plus a lowercase slug (may contain `.` and `-`) / 幕：`act.` に小文字の slug（`.` と `-` を含めてよい）
"""


type Activity = Annotated[
    Literal["idle", "walk", "run", "talk", "work", "sleep", "absent"],
    Field(title="Activity"),
]
"""
(1.1) What the character is doing right now, same as api-contract 2.3; the frontend treats unknown values as idle (2.4) / （1.1）登場人物がいま何をしているか。api-contract 2.3 と同じ。フロントエンドが知らない値は idle として扱う（2.4）
"""


type AffordanceId = Annotated[str, Field(pattern="^aff\\.[a-z0-9]+(?:[.-][a-z0-9]+)*$", title="AffordanceId")]
"""
Affordance (situational action, 1.1): `aff.` plus a lowercase slug (may contain `.` and `-`) / 状況アクション（1.1）：`aff.` に小文字の slug（`.` と `-` を含めてよい）
"""


type AidId = Annotated[str, Field(pattern="^aid\\.[a-z0-9]+(?:[.-][a-z0-9]+)*$", title="AidId")]
"""
Aid (1.1): `aid.` plus a lowercase slug (may contain `.` and `-`) / 助け合い（1.1）：`aid.` に小文字の slug（`.` と `-` を含めてよい）
"""


type BeatId = Annotated[str, Field(pattern="^beat\\.[a-z0-9]+(?:[.-][a-z0-9]+)*$", title="BeatId")]
"""
Beat: `beat.` plus a lowercase slug (may contain `.` and `-`); beat variants use the same prefix (`beat.25.v-no-doubt`) / ビート：`beat.` に小文字の slug（`.` と `-` を含めてよい）。ビートのバリアントも同じ接頭辞を使う（`beat.25.v-no-doubt`）
"""


type Rank = Annotated[int, Field(ge=1)]
"""
How deeply affected, starting at 1; null when unchanged / 影響の深さ。1 から始まる。unchanged のときは null
"""


type CharacterId = Annotated[str, Field(pattern="^char\\.[a-z0-9]+(?:[.-][a-z0-9]+)*$", title="CharacterId")]
"""
Character: `char.` plus a lowercase slug (may contain `.` and `-`) / 登場人物：`char.` に小文字の slug（`.` と `-` を含めてよい）
"""


class CheckResult(BaseModel):
    """
    Self-check result (section 3) / セルフチェックの結果（第 3 節）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    status: Literal["passed", "rewritten", "downgraded", "rejected"]
    attempts: Annotated[int, Field(ge=1, le=3)]
    """
    Total number of attempts (at most 2 rewrites, so at most 3) / 試行の総回数（書き直しは最大 2 回、つまり最大 3）
    """
    failedRules: list[
        Literal["R1-anchor", "R2-precondition", "R3-time", "R4-knowledge", "R5-persona", "R6-safety", "R7-capability"]
    ]
    reason: str | None = None
    """
    One Japanese sentence for 「なぜこうなった？」 and for reviewers / 「なぜこうなった？」とレビュアー向けの日本語の一文
    """
    checker: str
    """
    Model/rule version used for the self-check / セルフチェックに使ったモデル／ルールのバージョン
    """


class Cite(BaseModel):
    """
    Source in the original text, machine-checkable (section 0) / 原文の出典。機械で検証できる（第 0 節）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    source: str
    """
    Original-text version ID, e.g. "aozora:1567_ruby_4948@sha256:2a437c047d7f" (hash of the normalized full text) / 原文のバージョン ID。例："aozora:1567_ruby_4948@sha256:2a437c047d7f"（正規化した全文のハッシュ）
    """
    para: Annotated[int, Field(ge=1)]
    """
    Paragraph number in the normalized text, starting at 1 / 正規化テキスト内の段落番号。1 から始まる
    """
    quote: Annotated[str, Field(max_length=80, min_length=1)]
    """
    Excerpt from the original, ≤ 80 characters. Must be an exact substring of that paragraph (a cross-field rule, checked by build_world, not in the Schema) / 原文の抜粋。80 字以内。その段落の正確な部分文字列でなければならない（フィールドをまたぐ規則なので build_world が検証し、Schema には含めない）
    """


class ClockDeadlineEarliestArrivalCue(BaseModel):
    """
    (1.5, S-066 ①) A line said once, the first time this playthrough reaches the lower bound / （1.5、S-066 ①）このプレイで初めて下限に達したときに一度だけ言うセリフ
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    speaker: CharacterId
    line: str
    narration: str
    inferred: Literal[True] = True
    note: str | None = None


type BandItem = Annotated[int, Field(ge=0)]


type Band = Annotated[list[BandItem | str], Field(max_length=2, min_length=2)]


type EdgeId = Annotated[str, Field(pattern="^edge\\.[a-z0-9]+(?:[.-][a-z0-9]+)*$", title="EdgeId")]
"""
Causal edge: `edge.` plus a lowercase slug (may contain `.` and `-`) / 因果エッジ：`edge.` に小文字の slug（`.` と `-` を含めてよい）
"""


class EndingWorldContrast(BaseModel):
    """
    (1.1, S-026) 「原作では…／あなたの世界では…」 / （1.1、S-026）「原作では…／あなたの世界では…」
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    original: Annotated[str, Field(min_length=1)]
    yours: Annotated[str, Field(min_length=1)]
    beat: BeatId | None = None


class EndingCardCharacterLinesItem(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    character: CharacterId
    line: Annotated[str, Field(max_length=40, min_length=1)]
    """
    ≤ 40 characters / 40 字以内
    """


class EndingCard(BaseModel):
    """
    (1.1, S-049, S-051) Ending card; the character limits are guaranteed here. Generated for every playthrough from 1.6: a generated ending takes the 1–3 characters with the highest rank, and when nobody is ranked puts one line for Melos (from his original); for a playthrough that failed validation twice and fell back to the template epilogue, the fields take the pre-written sentences of the matching set in ux-design 11.4 / （1.1、S-049、S-051）エンディングカード。字数はここで保証する。1.6 以降はすべてのプレイで生成する：生成されたエンディングでは rank が上位の 1〜3 人を取り、誰も順位に入らないときはメロスの一文を置く（彼の original による）。検証に 2 回失敗してテンプレートのエピローグに切り替えたプレイでは、ux-design 11.4 の該当する組の事前に書いた文をフィールドに使う
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    title: Annotated[str, Field(max_length=14, min_length=1)]
    """
    Title ≤ 14 characters / 称号は 14 字以内
    """
    subtitle: Annotated[str, Field(max_length=26, min_length=1)]
    """
    Where the world ends up ≤ 26 characters / 世界の行く末は 26 字以内
    """
    contrast: Annotated[str, Field(max_length=48, min_length=1)]
    """
    「原作との違い」 ≤ 48 characters / 「原作との違い」は 48 字以内
    """
    characterLines: Annotated[list[EndingCardCharacterLinesItem], Field(max_length=3, min_length=1)]
    """
    (1–3 characters from 1.6) The 1–3 most affected characters; when nobody is ranked, one line for Melos (the card is laid out for at most 3 lines) / （1.6 以降 1〜3 人）最も影響を受けた 1〜3 人。誰も順位に入らないときはメロスの一文（カードは最大 3 行でレイアウトする）
    """


class EndingShare(BaseModel):
    """
    Storage reference of the generated artifact / 生成された成果物の保存先への参照
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    cardImageRef: str | None = None
    videoRef: str | None = None
    branchTreeRef: str | None = None


type EndingId = Annotated[str, Field(pattern="^end_[0-7][0-9A-HJKMNP-TV-Z]{25}$", title="EndingId")]
"""
Ending: `end_` plus a ULID (26 Crockford base32 characters, uppercase) / エンディング：`end_` に ULID（Crockford base32 で 26 文字、大文字）
"""


type EventId = Annotated[str, Field(pattern="^ev_[0-7][0-9A-HJKMNP-TV-Z]{25}$", title="EventId")]
"""
Event: `ev_` plus a ULID (26 Crockford base32 characters, uppercase) / イベント：`ev_` に ULID（Crockford base32 で 26 文字、大文字）
"""


type ExitId = Annotated[str, Field(pattern="^exit\\.[a-z0-9]+(?:[.-][a-z0-9]+)*$", title="ExitId")]
"""
End-of-act destination: `exit.` plus a lowercase slug (may contain `.` and `-`) / 幕末の行き先：`exit.` に小文字の slug（`.` と `-` を含めてよい）
"""


type FactId = Annotated[str, Field(pattern="^fact\\.[a-z0-9]+(?:[.-][a-z0-9]+)*$", title="FactId")]
"""
Fact: `fact.` plus a lowercase slug (may contain `.` and `-`) / 事実：`fact.` に小文字の slug（`.` と `-` を含めてよい）
"""


type ItemId = Annotated[str, Field(pattern="^item\\.[a-z0-9]+(?:[.-][a-z0-9]+)*$", title="ItemId")]
"""
Item (1.1): `item.` plus a lowercase slug (may contain `.` and `-`) / アイテム（1.1）：`item.` に小文字の slug（`.` と `-` を含めてよい）
"""


type MemoryId = Annotated[str, Field(pattern="^mem_[0-7][0-9A-HJKMNP-TV-Z]{25}$", title="MemoryId")]
"""
Memory: `mem_` plus a ULID (26 Crockford base32 characters, uppercase) / 記憶：`mem_` に ULID（Crockford base32 で 26 文字、大文字）
"""


type ObjectId = Annotated[str, Field(pattern="^obj\\.[a-z0-9]+(?:[.-][a-z0-9]+)*$", title="ObjectId")]
"""
(1.7) Inspectable object: `obj.` plus a lowercase slug (may contain `.` and `-`) / （1.7）調査可能オブジェクト：`obj.` に小文字の slug（`.` と `-` を含めてよい）
"""


class PlaceCrossing(BaseModel):
    """
    Place with a river / 川のある地点
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    bridgeMinutes: Annotated[int, Field(ge=0)]
    swimMinutes: Annotated[int, Field(ge=0)]
    boatMinutes: Annotated[int, Field(ge=0)]
    inferred: Literal[True] = True


type PlaceId = Annotated[str, Field(pattern="^place\\.[a-z0-9]+(?:[.-][a-z0-9]+)*$", title="PlaceId")]
"""
Place: `place.` plus a lowercase slug (may contain `.` and `-`) / 地点：`place.` に小文字の slug（`.` と `-` を含めてよい）
"""


type PlaythroughId = Annotated[str, Field(pattern="^pt_[0-7][0-9A-HJKMNP-TV-Z]{25}$", title="PlaythroughId")]
"""
Playthrough: `pt_` plus a ULID (26 Crockford base32 characters, uppercase) / プレイ 1 回：`pt_` に ULID（Crockford base32 で 26 文字、大文字）
"""


type PromiseId = Annotated[str, Field(pattern="^prm_[0-7][0-9A-HJKMNP-TV-Z]{25}$", title="PromiseId")]
"""
Promise (1.1): `prm_` plus a ULID (26 Crockford base32 characters, uppercase) / 約束（1.1）：`prm_` に ULID（Crockford base32 で 26 文字、大文字）
"""


type PromiseTemplateId = Annotated[
    str,
    Field(pattern="^promise\\.[a-z0-9]+(?:[.-][a-z0-9]+)*$", title="PromiseTemplateId"),
]
"""
Promise template (1.1): `promise.` plus a lowercase slug (may contain `.` and `-`) / 約束テンプレート（1.1）：`promise.` に小文字の slug（`.` と `-` を含めてよい）
"""


type RecordedAt = Annotated[
    str,
    Field(
        pattern="^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\\.[0-9]{1,9})?Z$",
        title="RecordedAt",
    ),
]
"""
Real time, ISO 8601 UTC, ending in Z (section 0). Used only for auditing and analysis, not in story logic. Checked with pattern, not format / 実時間。ISO 8601 UTC で末尾は Z（第 0 節）。監査と分析にのみ使い、物語のロジックには関与しない。format ではなく pattern で検証する
"""


class Relationship(BaseModel):
    """
    Relationship; not stored separately, derived from memories (section 4) / 関係。別に保存せず、記憶から導く（第 4 節）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    character: CharacterId
    trust: Annotated[int, Field(ge=-100, le=100)]
    """
    Initial value + the sum of trustDelta over undeleted memories, clamped to -100..100 / 初期値 + 削除されていない記憶の trustDelta の合計。-100..100 に切り詰める
    """
    label: str
    """
    Mapped from the trust range (the table in section 4) / trust の区間から対応付ける（第 4 節の表）
    """
    level: Literal[1, 2, 3, 4, 5]
    """
    (1.5) The level within the same range; called relationLevel in the API / （1.5）同じ区間内の段階。API では relationLevel と呼ぶ
    """


type RoleId = Annotated[str, Field(pattern="^role\\.[a-z0-9]+(?:[.-][a-z0-9]+)*$", title="RoleId")]
"""
Player role: `role.` plus a lowercase slug (may contain `.` and `-`) / プレイヤーの身分：`role.` に小文字の slug（`.` と `-` を含めてよい）
"""


type RuleId = Annotated[str, Field(pattern="^rule\\.[a-z0-9]+(?:[.-][a-z0-9]+)*$", title="RuleId")]
"""
Global rule (globalRules): `rule.` plus a lowercase slug (may contain `.` and `-`) / グローバルルール（globalRules）：`rule.` に小文字の slug（`.` と `-` を含めてよい）
"""


type RunFactId = Annotated[str, Field(pattern="^rf_[0-7][0-9A-HJKMNP-TV-Z]{25}$", title="RunFactId")]
"""
Improvised fact for this playthrough (1.1): `rf_` plus a ULID (26 Crockford base32 characters, uppercase) / このプレイの即興の設定（1.1）：`rf_` に ULID（Crockford base32 で 26 文字、大文字）
"""


type SceneId = Annotated[str, Field(pattern="^scene\\.[a-z0-9]+(?:[.-][a-z0-9]+)*$", title="SceneId")]
"""
3D scene: `scene.` plus a lowercase slug (may contain `.` and `-`) / 3D シーン：`scene.` に小文字の slug（`.` と `-` を含めてよい）
"""


type SchemaVersion = Annotated[
    Literal[
        "1.0",
        "1.1",
        "1.2",
        "1.3",
        "1.4",
        "1.5",
        "1.6",
        "1.7",
        "1.8",
        "1.9",
        "1.10",
        "1.11",
        "1.12",
        "1.13",
        "1.14",
        "1.15",
    ],
    Field(title="SchemaVersion"),
]
"""
Contract version at write time (section 0 "Versions"). Frozen at 1.5; later versions only add, and each new version adds a value here. 1.6: StateVar.valueRequires (C-16), ending cards with 1–3 characters. 1.7: spots (spot on relocate and ActExit, WorldState.spots), Character.group, ActExit.arrival / sub, Affordance.playerSpot (C-18), Act.plan (C-19), WorldModel.setPieces (S-080 ④), WorldModel.objects. 1.8: Affordance.pastLabel; event summaries always refer to the player by role name. 1.9: Clock.labels.daysKnownBy. 1.10: Role.summary, WorldModel.ruby; Character.reading filled for every character. 1.11: Character.originalEnding, endings.characters / templates / fates. 1.12: fields unchanged; a beat with no participating characters counts as the player being present if in the same scene (zoujin_worldsim.sees). 1.13: Character.knows[].inferred. 1.14: Act.stops, Place.shortName, Beat.arriveBefore. 1.15: Act.endLines, Act.closingLine / 書き込み時の契約バージョン（第 0 節「バージョン」）。1.5 で凍結し、以後は追加のみ。新しいバージョンごとにここへ値を 1 つ追加する。1.6：StateVar.valueRequires（C-16）、エンディングカードは 1〜3 人。1.7：位置点（relocate と ActExit の spot、WorldState.spots）、Character.group、ActExit.arrival / sub、Affordance.playerSpot（C-18）、Act.plan（C-19）、WorldModel.setPieces（S-080 ④）、WorldModel.objects。1.8：Affordance.pastLabel。イベントの summary ではプレイヤーを常に身分名で書く。1.9：Clock.labels.daysKnownBy。1.10：Role.summary、WorldModel.ruby。Character.reading は全登場人物で埋める。1.11：Character.originalEnding、endings.characters / templates / fates。1.12：フィールドは変更なし。参加する登場人物のいないビートは、同じシーンにいればプレイヤーが居合わせたとみなす（zoujin_worldsim.sees）。1.13：Character.knows[].inferred。1.14：Act.stops、Place.shortName、Beat.arriveBefore。1.15：Act.endLines、Act.closingLine
"""


class SetPieceOnOption1(BaseModel):
    """
    When it plays: when this beat happens with the player present (beats settled together on entering the ending ignore presence and count as part of the ending staging, 2.11), or after this kind of player action is judged / いつ演じるか：このビートが起きたときにプレイヤーが居合わせた場合（エンディングに入るときにまとめて精算するビートは居合わせたかを見ず、エンディングの演出に含める、2.11）、またはプレイヤーのこの種のアクションが判定された後
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    beat: BeatId


class SetPieceOnOption2(BaseModel):
    """
    When it plays: when this beat happens with the player present (beats settled together on entering the ending ignore presence and count as part of the ending staging, 2.11), or after this kind of player action is judged / いつ演じるか：このビートが起きたときにプレイヤーが居合わせた場合（エンディングに入るときにまとめて精算するビートは居合わせたかを見ず、エンディングの演出に含める、2.11）、またはプレイヤーのこの種のアクションが判定された後
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    act: Literal[
        "examine", "give", "follow", "block", "help", "wait", "go", "shortcut", "run-together", "hasten", "move"
    ]
    """
    The kind from api-contract 3.8 / api-contract 3.8 の kind
    """
    target: Annotated[str | None, Field(max_length=128, min_length=1)] = None
    """
    For actions on a character, the character ID; for move, the place ID; for go, the place the exit leads to (layout exits[].place); for examine, the interactable's ID (obj.*); omitted = the target is not checked / 登場人物へのアクションは登場人物の ID、move は地点の ID、go は出口の行き先の地点（レイアウトの exits[].place）、examine は interactable の ID（obj.*）を書く。省略 = 対象は見ない
    """
    refused: Literal[True] | None = None
    """
    Plays only when refused; omitted = only when it succeeds (done / partial) / 拒否されたときだけ演じる。省略 = 成功したとき（done / partial）だけ
    """


class SetPieceKnowsItem(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    character: CharacterId
    fact: FactId


class SetPieceLinesItemOption1(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    narration: Annotated[str, Field(min_length=1)]
    """
    One line of 地の文 (in Japanese) / 地の文 1 行（日本語）
    """


class SetPieceLinesItemOption2(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    speaker: CharacterId
    line: Annotated[str, Field(min_length=1)]
    """
    A pre-recorded line, also the subtitle (in Japanese) / 事前収録セリフ。字幕も兼ねる（日本語）
    """


class SetPieceLearnsItem(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    character: Literal["player"] | CharacterId
    fact: FactId


type SetPieceId = Annotated[str, Field(pattern="^piece\\.[a-z0-9]+(?:[.-][a-z0-9]+)*$", title="SetPieceId")]
"""
(1.7) Set piece: `piece.` plus a lowercase slug (may contain `.` and `-`) / （1.7）固定演出：`piece.` に小文字の slug（`.` と `-` を含めてよい）
"""


type SpotId = Annotated[str, Field(max_length=64, pattern="^[a-z0-9]+(?:[.-][a-z0-9]+)*$", title="SpotId")]
"""
(1.7) A spot in the scene layout (api-contract section 0 spot; the spots in assets/scenes/<scene>/layout.json), a lowercase slug, e.g. stake-front, way.castle. No type prefix: the frontend sets the names in the layout / （1.7）シーンレイアウト内の位置点（api-contract 第 0 節の spot、assets/scenes/<シーン>/layout.json の spots）。小文字の slug。例：stake-front、way.castle。型の接頭辞は付けない：名前はフロントエンドがレイアウトで決める
"""


type StoryTime = Annotated[int, Field(ge=0, title="StoryTime")]
"""
Story time t: story minutes counted from 00:00 on Day 0 (the day of the promise) (section 0) / 物語時間 t：Day 0（約束の日）00:00 から数えた物語上の分数（第 0 節）
"""


type TLabel = Annotated[str, Field(title="TLabel")]
"""
How a time is phrased, generated from the world model's clock.labels, e.g. 「約束の日・夜」 (section 0) / 時刻の言い表し。世界モデルの clock.labels から生成する。例：「約束の日・夜」（第 0 節）
"""


type TurnId = Annotated[str, Field(pattern="^turn_[0-7][0-9A-HJKMNP-TV-Z]{25}$", title="TurnId")]
"""
Turn: `turn_` plus a ULID (26 Crockford base32 characters, uppercase) / ターン：`turn_` に ULID（Crockford base32 で 26 文字、大文字）
"""


type UtteranceId = Annotated[str, Field(pattern="^utt_[0-7][0-9A-HJKMNP-TV-Z]{25}$", title="UtteranceId")]
"""
Utterance: `utt_` plus a ULID (26 Crockford base32 characters, uppercase) / 発話：`utt_` に ULID（Crockford base32 で 26 文字、大文字）
"""


type VarId = Annotated[str, Field(pattern="^var\\.[a-zA-Z0-9]+(?:[.-][a-zA-Z0-9]+)*$", title="VarId")]
"""
State variable: `var.` plus a slug (may contain `.` and `-`); segments may use camelCase (`var.player.companionOf`, `var.player.knowsShortcut`, `var.melos.knowsTyranny`), section 0 (made explicit in 1.6) / 状態変数：`var.` に slug（`.` と `-` を含めてよい）。各セグメントはキャメルケースでもよい（`var.player.companionOf`、`var.player.knowsShortcut`、`var.melos.knowsTyranny`）。第 0 節（1.6 で明記）
"""


type WorldEndingId = Annotated[str, Field(pattern="^[a-z0-9]+(?:-[a-z0-9]+)*$", title="WorldEndingId")]
"""
ID of a world-ending baseline class: a lowercase hyphenated slug with no prefix, e.g. `canon-reunion` / 世界のエンディングの基本類型の ID。接頭辞なしの小文字ハイフン区切り slug。例：`canon-reunion`
"""


class WorldModelBookSource(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    provider: Literal["aozora"] = "aozora"
    cardId: str
    fileId: str
    url: str
    textSha256: Annotated[str, Field(pattern="^[0-9a-f]{64}$")]
    retrievedAt: str
    """
    Date the original text was retrieved / 原文を取得した日付
    """
    license: Literal["public-domain"] = "public-domain"


class WorldModelBook(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    id: str
    """
    E.g. "hashire-merosu" / 例："hashire-merosu"
    """
    title: str
    author: str
    year: int
    source: Annotated[WorldModelBookSource, Field(title="WorldModelBookSource")]


class WorldModelGlobalRulesItem(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    id: RuleId
    text: str
    inferred: Literal[True] = True
    cite: list[Cite] | None = None
    """
    When there is support in the original text (1.4) / 原文に根拠があるとき（1.4）
    """


class WorldModelEndingsTemplatesItemLinesItem(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    character: CharacterId
    line: Annotated[str, Field(min_length=1)]
    """
    One line on this character's ending, ≤ 40 characters / この登場人物の結末の一文。40 字以内
    """


class WorldModelEndingsFates(BaseModel):
    """
    (1.11, B-9) The 行方 used when the template has no fate, taken by Ending.player.fate.id: witness if present at the ending's place, elsewhere if not (ux-design 11.4) / （1.11、B-9）テンプレートに fate がないときの行方。Ending.player.fate.id で取る：エンディングの地点に居合わせたら witness、いなければ elsewhere（ux-design 11.4）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    witness: Annotated[str, Field(min_length=1)]
    elsewhere: Annotated[str, Field(min_length=1)]


PacingAdditionalProperty = TypeAliasType("PacingAdditionalProperty", Annotated[int, Field(ge=0)])


class WorldModelRubyItem(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    word: Annotated[str, Field(min_length=1)]
    """
    Spelling as it appears in subtitles; the frontend finds it by longest match / 字幕での表記。フロントエンドが最長一致で探す
    """
    reading: Annotated[str, Field(min_length=1)]
    """
    Reading of the whole word, in hiragana / word 全体の読み。ひらがな
    """


class WorldObject(BaseModel):
    """
    (1.7) Inspectable object (2.12): something in a scene the player can 「調べる」 (inspect). The server builds the snapshot's interactables from it (kind examine, 0 minutes) instead of hard-coding them; scene exits follow the layout's exits / （1.7）調査可能オブジェクト（2.12）：シーン内で「調べる」ことができるもの。サーバーはこれをもとにスナップショットの interactables を出す（kind examine、0 分）。ハードコードはしない。シーンの出口はレイアウトの exits に従う
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    id: ObjectId
    place: PlaceId
    """
    Which place it is in (must have a scene) / どの地点にあるか（シーンが必要）
    """
    label: Annotated[str, Field(min_length=1)]
    """
    The text on the button (in Japanese, written by UX) / ボタンの文字（日本語、UX が作成）
    """
    spot: SpotId | None = None
    """
    Spot in the layout (added by the frontend); required when the server builds the snapshot / レイアウト内の位置点（フロントエンドが追加）。サーバーがスナップショットを出すときに必要
    """
    inferred: Literal[True] = True
    note: str | None = None


class ActStart(BaseModel):
    """
    The earliest time this act can start / この幕が最も早く始まる時刻
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    t: StoryTime


class ActEnd(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    onBeats: list[BeatId]
    """
    The act closes as soon as any of these beats has an outcome / これらのビートのいずれかに結果が出たら幕を閉じる
    """
    atLatest: StoryTime
    """
    The act closes at this time at the latest / 遅くともこの時刻に幕を閉じる
    """


class ActPlanArrival(BaseModel):
    """
    Landing, same as ActExit.arrival / 降り立ち。ActExit.arrival と同じ
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    line: Annotated[str, Field(min_length=1)]
    """
    The first line of narration after landing (地の文, in Japanese), shown after the jump / 降り立った後の最初の語り（地の文、日本語）。ジャンプの後に表示する
    """
    opener: CharacterId | None = None
    """
    The character who speaks first after landing: the server starts a turn; the line is generated from the character profile and is not a question / 降り立った後に最初に口を開く登場人物：サーバーがターンを開始し、セリフは人物設定に沿って生成する。疑問文にはしない
    """


class ActExitArrival(BaseModel):
    """
    (1.7) Landing: the first line of narration and the character who speaks first (ux/slice/jump-transition.md, "Landing") / （1.7）降り立ち：最初の語りと最初に口を開く登場人物（ux/slice/jump-transition.md の「降り立ち」）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    line: Annotated[str, Field(min_length=1)]
    """
    The first line of narration after landing (地の文, in Japanese), shown after the jump / 降り立った後の最初の語り（地の文、日本語）。ジャンプの後に表示する
    """
    opener: CharacterId | None = None
    """
    The character who speaks first after landing: the server starts a turn; the line is generated from the character profile and is not a question / 降り立った後に最初に口を開く登場人物：サーバーがターンを開始し、セリフは人物設定に沿って生成する。疑問文にはしない
    """


type Actor = Annotated[Literal["player", "system", "narrator"] | CharacterId, Field(title="Actor")]
"""
Who performed the event (not who wrote it; the writer is always the narrator): player = the player, system = happened naturally on schedule, narrator = only for correction, or a character ID (section 0) / イベントを行ったのは誰か（書いたのは誰かではない。書き込むのは常にナレーター）：player はプレイヤー、system はスケジュールどおり自然に起きたもの、narrator は correction 専用、または登場人物の ID（第 0 節）
"""


class BeatWindow(BaseModel):
    """
    Story minutes; in the original it happens at canonical; after latest it can no longer happen / 物語上の分。原作では canonical に起きる。latest を過ぎるともう起こり得ない
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    earliest: StoryTime
    latest: StoryTime
    canonical: StoryTime


class BeatActivitiesItem(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    character: CharacterId
    activity: Activity


class CausalEdge(BaseModel):
    """
    Causal edge (2.5) / 因果エッジ（2.5）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    id: EdgeId
    from_: Annotated[BeatId | VarId, Field(alias="from")]
    """
    A beat or a stateVar / beat または stateVar
    """
    to: BeatId | VarId
    """
    A beat or a stateVar / beat または stateVar
    """
    type: Literal["enables", "requires", "prevents", "delays", "hastens"]
    timeLink: Literal["shift", "order"] | None = None
    """
    (1.1) Only for enables / requires; default shift / （1.1）enables / requires のみ。既定は shift
    """
    minutes: Annotated[int | None, Field(ge=0)] = None
    """
    Required for delays / hastens: by how many minutes from happening delays (or advances) to / delays / hastens では必須：from が起きると to が何分遅れる（早まる）か
    """
    note: str
    """
    Why this edge exists (in Japanese) / このエッジがある理由（日本語）
    """
    cite: list[Cite] | None = None
    """
    Source, when the original directly supports it / 原文が直接裏付けるときは出典を示す
    """
    inferred: bool
    """
    true when the original does not say so explicitly and it was inferred by a person / 原文に明記されておらず、人が推定したものは true
    """


class CharacterKnowsItem(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    fact: FactId
    since: BeatId | Literal["pre"]
    """
    "pre" = known before the story begins / "pre" = 物語の開始前から知っている
    """
    inferred: Literal[True] | None = None
    """
    (1.13) The original does not say they know it; inferred by a person (marked 〔推断〕 in the review sheet) / （1.13）原文には知っているとは書かれておらず、人が推定したもの（レビュー表では〔推断〕と記す）
    """


class CharacterPlansItem(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    act: ActId
    text: str
    inferred: Literal[True] | None = None
    cite: list[Cite] | None = None


class CharacterOriginalEnding(BaseModel):
    """
    (1.11, B-9) The 「原作では」 line on the ending page, which is also Melos's line on the card when no character was affected; required for every character in endings.characters / （1.11、B-9）エンディングページの「原作では」の一文。どの登場人物にも影響が及ばなかったときにカードに出るメロスの行でもある。endings.characters の登場人物には必須
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    text: Annotated[str, Field(min_length=1)]
    """
    This character's ending in the original, one sentence, ≤ 40 characters, no subject (the ending page already shows the name and 「原作では」 before it) / 原作でのこの登場人物の結末。一文、40 字以内、主語は書かない（エンディングページでは前に名前と「原作では」が付く）
    """
    cite: Annotated[list[Cite], Field(min_length=1)]


class CharacterEndingYoursItem(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    sentence: Annotated[str, Field(min_length=1)]
    cites: Annotated[list[EventId], Field(min_length=1)]
    """
    Cites at least one event from this playthrough / このプレイのイベントを少なくとも 1 つ引用する
    """


class CharacterEnding(BaseModel):
    """
    (1.1) The ending of each talkable character (section 5) / （1.1）会話できる各登場人物の結末（第 5 節）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    character: CharacterId
    rank: Rank | None
    """
    How deeply affected, starting at 1; null when unchanged / 影響の深さ。1 から始まる。unchanged のときは null
    """
    unchanged: bool
    """
    The player did not interact with them and the world's changes did not reach them: only 「原作どおり」 is shown, no sentences are generated / プレイヤーが関わらず、世界の変化も及ばなかった：「原作どおり」だけを表示し、文は生成しない
    """
    original: Annotated[str | None, Field(min_length=1)] = None
    """
    Their ending in the original, one sentence (in Japanese) / 原作での結末。一文（日本語）
    """
    yours: Annotated[list[CharacterEndingYoursItem] | None, Field(max_length=3, min_length=1)] = None
    """
    1–3 sentences, 「あなたの世界では」; omitted when unchanged / 1〜3 文、「あなたの世界では」。unchanged のときは省略
    """


class ClockDeadline(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    t: StoryTime
    label: str
    """
    E.g. 「三日目の日没」 / 例「三日目の日没」
    """
    cite: list[Cite]
    watchBeat: BeatId | None = None
    """
    (1.1) The beat that decides whether he makes it in time / （1.1）間に合うかどうかを決めるビート
    """
    earliestArrival: StoryTime | None = None
    """
    (1.4, S-066) The earliest time of watchBeat / （1.4、S-066）watchBeat の最も早い時刻
    """
    earliestArrivalCue: Annotated[
        ClockDeadlineEarliestArrivalCue | None,
        Field(title="ClockDeadlineEarliestArrivalCue"),
    ] = None
    """
    (1.5, S-066 ①) A line said once, the first time this playthrough reaches the lower bound / （1.5、S-066 ①）このプレイで初めて下限に達したときに一度だけ言うセリフ
    """


class ClockLabels(BaseModel):
    """
    Rules for generating tLabel / tLabel の生成規則
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    days: list[str]
    """
    Index = Day (S-037) / 添字 = Day（S-037）
    """
    bands: list[Band]
    """
    Start (in minutes) and name of each time of day within a day, e.g. [1140,"日没"]; starts at 0 and strictly increasing / 1 日の中の各時間帯の開始（分）と呼び方。例：[1140,"日没"]。0 から始まり狭義単調増加
    """
    format: str
    """
    (1.1) Template, containing {day} and {band} / （1.1）テンプレート。{day} と {band} を含む
    """
    daysKnownBy: FactId | None = None
    """
    (1.9) When the day names (days) carry plot, which fact a character must know before the day name is used. A character who does not know this fact is given only the time of day (band), e.g. 「夜」; the UI, tLabel, 記憶帳 and 地の文 still use the full phrasing (S-086). Omitted = everyone gets the full phrasing / （1.9）日の名前（days）が筋に関わるとき、日の名前を言うにはどの事実を知っている必要があるか。この事実を知らない登場人物には時間帯（band）だけを渡す。例「夜」。画面、tLabel、記憶帳、地の文は従来どおり完全な言い方を使う（S-086）。省略 = 誰にでも完全な言い方を渡す
    """
    inferred: Literal[True] = True
    note: str | None = None
    cite: list[Cite] | None = None
    """
    (1.1) Support in the original for the time-of-day names / （1.1）時間帯の呼び方の原文上の根拠
    """


class Condition(BaseModel):
    """
    Condition: references stateVars (2.4). Shared by beat preconditions, variants, destinations, affordances, and world endings / 条件：stateVars を参照する（2.4）。ビートの前提条件、バリアント、行き先、状況アクション、世界のエンディングで共用する
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    var: VarId
    op: Literal["==", "!=", ">=", "<=", "in"]
    value: Any
    inferred: Literal[True] | None = None
    note: str | None = None
    """
    Explanation of a precondition not in the original, designed for the game / 原文にはなく、ゲームのために設計した前提条件の説明
    """


class DesignLine(BaseModel):
    """
    (1.4) Sample lines not in the original, written for the game (2.1) / （1.4）原文にはなく、ゲームのために書いたセリフ例（2.1）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    text: str
    """
    One Japanese sentence. Used in the character prompt as an example like sampleLines, not read out verbatim / 日本語の一文。キャラクタープロンプトでは sampleLines と同じく例として使い、一字一句そのまま読み上げはしない
    """
    since: BeatId | None = None
    """
    Used only from when that beat happens (1.1) / そのビートが起きてから使う（1.1）
    """
    until: BeatId | None = None
    """
    No longer used after that beat happens (1.1) / そのビートが起きた後は使わない（1.1）
    """
    when: list[Condition] | None = None
    """
    Used only when the current WorldState meets these conditions (1.4); when since / until / when are all given, all three must hold / 現時点の WorldState がこれらの条件を満たすときだけ使う（1.4）。since / until / when を同時に書いた場合は 3 つすべてを満たす必要がある
    """
    inferred: Literal[True] = True
    note: str | None = None
    """
    When it is said / どんな場面で言うか
    """
    cite: list[Cite] | None = None
    """
    The original text it is based on / 根拠とする原文
    """


class EffectHold(BaseModel):
    """
    (1.3) An item changes hands; only for portable items / （1.3）アイテムの持ち主が変わる。portable なアイテムのみ
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    op: Literal["hold"] = "hold"
    item: ItemId
    to: Literal["player"] | CharacterId | None
    """
    The new holder; null = taken away or used up / 新しい持ち主。null = 持ち去られた、使い切られた
    """
    from_: Annotated[Literal["player"] | CharacterId | None, Field(alias="from")] = None


class EffectImprov(BaseModel):
    """
    (1.1) Improvised fact (S-030 ②); see RunFact in 3.1 / （1.1）即興の設定（S-030 ②）。3.1 の RunFact を参照
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    op: Literal["improv"] = "improv"
    factId: RunFactId
    character: CharacterId
    statement: str


class EffectInc(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    op: Literal["inc"] = "inc"
    var: VarId
    by: int


class EffectLearn(BaseModel):
    """
    A character learns a fact; (1.1) fact may also be rf_… (someone else's improvised fact); (1.7) character may be player (contract 2.1: when a character tells the player, the narrator extracts it; when the player is at the beat's place, the shared rules write it into the beat's system event) / ある登場人物がある事実を知る。（1.1）fact は rf_…（他人の即興の設定）でもよい。（1.7）character は player でもよい（契約 2.1：登場人物がプレイヤーに伝えたときはナレーターが抽出し、プレイヤーがビートの地点にいるときは共有ルールがビートのシステムイベントに書き込む）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    op: Literal["learn"] = "learn"
    character: Literal["player"] | CharacterId
    fact: FactId | RunFactId


class EffectPromiseDue(BaseModel):
    """
    Deadline (a time or a beat) / 期限（時刻またはビート）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    t: StoryTime | None = None
    beat: BeatId | None = None


class EffectPromise(BaseModel):
    """
    (1.1) Promise; see Promise in 3.1 / （1.1）約束。3.1 の Promise を参照
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    op: Literal["promise"] = "promise"
    promiseId: PromiseId | None = None
    """
    Optional (made explicit in contract section 3 in 1.6): omitted in world-model effect templates (2.10) and candidate events (evals/s2/README.md); the narrator assigns a prm_… at commit. Committed events additionally require it (Event.effects) / 任意（1.6 で契約第 3 節に明記）：世界モデルのエフェクトテンプレート（2.10）と候補イベント（evals/s2/README.md）では書かず、コミット時にナレーターが prm_… を割り当てる。コミットされたイベントでは別途必須（Event.effects）
    """
    change: Literal["made", "kept", "broken", "voided"]
    from_: Annotated[Literal["player"] | CharacterId | None, Field(alias="from")] = None
    """
    Required when change = made / change = made のときは必須
    """
    to: Literal["player"] | CharacterId | None = None
    """
    Required when change = made / change = made のときは必須
    """
    text: str | None = None
    """
    Required when change = made / change = made のときは必須
    """
    due: Annotated[EffectPromiseDue | None, Field(title="EffectPromiseDue")] = None
    """
    Deadline (a time or a beat) / 期限（時刻またはビート）
    """
    template: PromiseTemplateId | None = None
    """
    Template ID (optional) / テンプレート ID（任意）
    """


class EffectRelocate(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    op: Literal["relocate"] = "relocate"
    character: CharacterId
    place: PlaceId
    spot: SpotId | None = None
    """
    (1.7) Which spot at this place to stand on; omitted = the backend places them by the layout's placement rules (section 3.1 WorldState.spots) / （1.7）この地点のどの位置点に立つか。省略 = バックエンドがレイアウトの立ち位置の規則で配置する（第 3.1 節 WorldState.spots）
    """


class EffectSet(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    op: Literal["set"] = "set"
    var: VarId
    value: Any
    from_: Annotated[Any | None, Field(alias="from")] = None


class EndingWorldChangedBeatsItem(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    beat: BeatId
    to: str
    causedBy: list[EventId]


class EndingWorldVariantClaimsItem(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    var: VarId
    value: Any


class EndingWorldVariant(BaseModel):
    """
    (1.1, S-031 ①) The world ending generated for this playthrough; absent = the baseline class itself / （1.1、S-031 ①）このプレイで生成した世界のエンディング。ない = 基本類型そのもの
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    id: Annotated[str, Field(min_length=1)]
    """
    Unique within the playthrough, e.g. "gen.king-abdicates" (the API's outcomeId) / プレイ内で一意。例："gen.king-abdicates"（API の outcomeId）
    """
    title: Annotated[str, Field(min_length=1)]
    summary: Annotated[str, Field(min_length=1)]
    claims: list[EndingWorldVariantClaimsItem]
    """
    The final state it claims; must match finalVars / これが主張する最終状態。finalVars と一致しなければならない
    """
    causedBy: Annotated[list[EventId], Field(min_length=2)]
    """
    At least 2 events from this playthrough ("it makes sense") / このプレイのイベントを少なくとも 2 つ（「筋が通る」）
    """


class EndingWorld(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    outcome: WorldEndingId
    """
    WorldModel.endings.world[].id (baseline class) / WorldModel.endings.world[].id（基本類型）
    """
    summary: Annotated[str, Field(min_length=1)]
    """
    Japanese / 日本語
    """
    changedBeats: list[EndingWorldChangedBeatsItem]
    """
    Beats that differ from the original, each pointing back to events / 原作と異なるビート。それぞれイベントを指し示す
    """
    finalVars: dict[VarId, Any]
    title: Annotated[str | None, Field(min_length=1)] = None
    """
    (1.1) A one-line title for the world ending. Required from 1.6: a playthrough with a template epilogue writes the label of this class from the world model's endings.world (world.title in api-contract 2.8) / （1.1）世界のエンディングの一行タイトル。1.6 以降は必須：テンプレートのエピローグを使うプレイでは、世界モデルの endings.world にあるこの類型の label を書く（api-contract 2.8 の world.title）
    """
    variant: Annotated[EndingWorldVariant | None, Field(title="EndingWorldVariant")] = None
    """
    (1.1, S-031 ①) The world ending generated for this playthrough; absent = the baseline class itself / （1.1、S-031 ①）このプレイで生成した世界のエンディング。ない = 基本類型そのもの
    """
    signature: dict[VarId | BeatId, Any] | None = None
    """
    (1.1) The signature computed from endings.signature (2.9.1): variable → final value, beat → whether it happened as in the original / （1.1）endings.signature から算出したシグネチャ（2.9.1）：変数 → 最終値、ビート → 原作どおりに起きたか
    """
    contrast: Annotated[EndingWorldContrast | None, Field(title="EndingWorldContrast")] = None
    """
    (1.1, S-026) 「原作では…／あなたの世界では…」 / （1.1、S-026）「原作では…／あなたの世界では…」
    """


class EndingPlayerFate(BaseModel):
    """
    Advisor, hostage, companion, witness, executed… / 相談役、人質、同行者、目撃者、処刑された…
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    id: Annotated[str, Field(min_length=1)]
    label: Annotated[str, Field(min_length=1)]
    causedBy: Annotated[list[EventId], Field(min_length=1)]


class EndingPlayerRelationshipsItem(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    character: CharacterId
    trust: Annotated[int, Field(ge=-100, le=100)]
    """
    Initial value + the sum of trustDelta over undeleted memories, clamped to -100..100 / 初期値 + 削除されていない記憶の trustDelta の合計。-100..100 に切り詰める
    """
    label: Annotated[str, Field(min_length=1)]
    line: Annotated[str | None, Field(min_length=1)] = None
    memoryIds: list[MemoryId]


class EndingPlayerTitle(BaseModel):
    """
    E.g. 「王に信を説いた旅人」 / 例「王に信を説いた旅人」
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    text: Annotated[str, Field(min_length=1)]
    causedBy: Annotated[list[EventId], Field(min_length=1)]


class EndingPlayerEpilogueItem(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    sentence: Annotated[str, Field(min_length=1)]
    cites: Annotated[list[EventId], Field(min_length=1)]
    """
    Cites at least one event from this playthrough / このプレイのイベントを少なくとも 1 つ引用する
    """


class EndingPlayerLastScene(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    place: PlaceId
    description: Annotated[str, Field(min_length=1)]
    present: list[CharacterId] | None = None
    """
    (1.1) Characters present in the ending staging (S-053) / （1.1）エンディングの演出に居合わせる登場人物（S-053）
    """


class EndingPlayerDidForYouItem(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    sentence: Annotated[str, Field(min_length=1)]
    cites: Annotated[list[EventId], Field(min_length=1)]
    """
    Cites at least one event from this playthrough / このプレイのイベントを少なくとも 1 つ引用する
    """


class EndingPlayerYouDidItem(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    sentence: Annotated[str, Field(min_length=1)]
    cites: Annotated[list[EventId], Field(min_length=1)]
    """
    Cites at least one event from this playthrough / このプレイのイベントを少なくとも 1 つ引用する
    """


class EndingPlayer(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    fate: Annotated[EndingPlayerFate, Field(title="EndingPlayerFate")]
    """
    Advisor, hostage, companion, witness, executed… / 相談役、人質、同行者、目撃者、処刑された…
    """
    relationships: list[EndingPlayerRelationshipsItem]
    title: Annotated[EndingPlayerTitle, Field(title="EndingPlayerTitle")]
    """
    E.g. 「王に信を説いた旅人」 / 例「王に信を説いた旅人」
    """
    epilogue: list[EndingPlayerEpilogueItem]
    """
    Each sentence cites at least one event / 各文で少なくとも 1 つのイベントを引用する
    """
    lastScene: Annotated[EndingPlayerLastScene, Field(title="EndingPlayerLastScene")]
    didForYou: list[EndingPlayerDidForYouItem] | None = None
    """
    (1.1, D-012) What characters did for you / （1.1、D-012）登場人物があなたのためにしたこと
    """
    youDid: list[EndingPlayerYouDidItem] | None = None
    """
    (1.1) What you did for characters / （1.1）あなたが登場人物のためにしたこと
    """


class Ending(BaseModel):
    """
    Ending (section 5). For endings written from 1.6 on, world.title, player.didForYou / youDid (may be empty arrays), characters and card are required / エンディング（第 5 節）。1.6 以降に書き込むエンディングでは world.title、player.didForYou / youDid（空配列でもよい）、characters、card が必須
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    schemaVersion: SchemaVersion
    endingId: EndingId
    playthroughId: PlaythroughId
    worldModelVersion: str
    trigger: Literal["deadline", "story-closed", "abandoned"]
    """
    story-closed = the closing beat of the last act has an outcome / story-closed = 最後の幕の幕を閉じるビートに結果が出た
    """
    t: StoryTime
    decidedAt: RecordedAt
    world: Annotated[EndingWorld, Field(title="EndingWorld")]
    player: Annotated[EndingPlayer, Field(title="EndingPlayer")]
    characters: list[CharacterEnding] | None = None
    """
    (1.1, D-015, S-032) All 7 talkable characters are included / （1.1、D-015、S-032）会話できる 7 人の登場人物が全員含まれる
    """
    card: Annotated[EndingCard | None, Field(title="EndingCard")] = None
    """
    (1.1, S-049, S-051) Ending card; the character limits are guaranteed here. Generated for every playthrough from 1.6: a generated ending takes the 1–3 characters with the highest rank, and when nobody is ranked puts one line for Melos (from his original); for a playthrough that failed validation twice and fell back to the template epilogue, the fields take the pre-written sentences of the matching set in ux-design 11.4 / （1.1、S-049、S-051）エンディングカード。字数はここで保証する。1.6 以降はすべてのプレイで生成する：生成されたエンディングでは rank が上位の 1〜3 人を取り、誰も順位に入らないときはメロスの一文を置く（彼の original による）。検証に 2 回失敗してテンプレートのエピローグに切り替えたプレイでは、ux-design 11.4 の該当する組の事前に書いた文をフィールドに使う
    """
    share: Annotated[EndingShare | None, Field(title="EndingShare")] = None
    """
    Storage reference of the generated artifact / 生成された成果物の保存先への参照
    """


class EndingSignature(BaseModel):
    """
    (1.1) Ending signature: what counts as "substantively different world endings" (2.9.1) / （1.1）エンディングシグネチャ：「世界のエンディングが実質的に異なる」とは何か（2.9.1）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    vars: list[VarId]
    """
    Final values of these variables / これらの変数の最終値
    """
    beats: list[BeatId]
    """
    Whether these beats happened as in the original / これらのビートが原作どおりに起きたか
    """
    inferred: Literal[True] = True
    note: str | None = None


class EventPlan(BaseModel):
    """
    (1.2, S-031 ③) Only for type=act-transition (actor=player) when the player stated their own plan / （1.2、S-031 ③）type=act-transition（actor=player）で、プレイヤーが自分のプランを述べた場合のみ
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    label: str
    """
    The narrator's paraphrase in Japanese; does not quote the player verbatim / ナレーターによる日本語での言い換え。プレイヤーの発言をそのまま引用しない
    """
    toAct: ActId
    place: PlaceId
    t: StoryTime
    """
    Not earlier than Act.start.t / Act.start.t より早くない
    """
    with_: Annotated[list[CharacterId] | None, Field(alias="with")] = None
    """
    Characters going along / 同行する登場人物
    """


class Fact(BaseModel):
    """
    Fact (2.3) / 事実（2.3）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    id: FactId
    statement: str
    """
    Neutral statement (in Japanese) / 中立的な記述（日本語）
    """
    trueFrom: BeatId | Literal["pre"]
    """
    From which beat it holds; "pre" = already holds before the opening / どの beat から成り立つか。"pre" = 開幕前から成り立っている
    """
    visibility: Literal["public", "private"]
    """
    public: everyone present learns it; private: only those listed in knows know it / public：居合わせた人は皆知る。private：knows にいる人だけが知っている
    """
    spoilerTerms: list[str] | None = None
    """
    Words and aliases commonly used when stating this fact (in Japanese) / この事実を口にするときによく使う語と別名（日本語）
    """
    cite: list[Cite]


class Item(BaseModel):
    """
    (1.1) Item in the story (2.10) / （1.1）物語に登場するアイテム（2.10）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    id: ItemId
    name: str
    """
    Japanese / 日本語
    """
    at: list[PlaceId]
    """
    Readily available at these places; write [] for items that can be carried / これらの地点ですぐ手に入る。持ち歩けるアイテムは [] と書く
    """
    portable: Literal[True] | None = None
    """
    (1.3) A single physical object: in only one person's hands at any moment / （1.3）実物 1 つ：同時に 1 人の手にしかない
    """
    inferred: Literal[True] = True
    note: str | None = None
    cite: list[Cite] | None = None


class MemoryItem(BaseModel):
    """
    A character's memory of the player, deletable (section 4). Generated only from committed events / 登場人物がプレイヤーについて持つ記憶。削除できる（第 4 節）。コミット済みのイベントからのみ生成する
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    schemaVersion: SchemaVersion
    memoryId: MemoryId
    playthroughId: PlaythroughId
    character: CharacterId
    """
    Who remembers / 誰が覚えているか
    """
    kind: Literal["promise", "help", "harm", "shared-moment", "claim", "impression"]
    text: str
    """
    One Japanese sentence from the character's point of view, shown in the 記憶帳; no real-world personal information; cleared after deletion / 登場人物の視点による日本語の一文。記憶帳に表示する。現実の個人情報は含めない。削除後は空にする
    """
    fromEvents: Annotated[list[EventId], Field(min_length=1)]
    """
    Which events it came from; memories are generated only from committed events (section 4), so at least one / どのイベントから来たか。記憶はコミット済みのイベントからのみ生成する（第 4 節）ので、少なくとも 1 つ
    """
    t: StoryTime
    trustDelta: Annotated[int, Field(ge=-20, le=20)]
    """
    This memory's effect on trust, -20..+20 / この記憶が信頼に与える影響。-20..+20
    """
    salience: Annotated[float, Field(ge=0.0, le=1.0)]
    """
    0..1, used for retrieval ranking / 0..1。検索の並べ替えに使う
    """
    via: Literal["witnessed", "told", "rumor"] | None = None
    """
    (1.1) 見た / 聞いた / 噂で (saw / heard / by rumor) / （1.1）見た / 聞いた / 噂で
    """
    promiseId: PromiseId | None = None
    """
    (1.1) Which promise this memory belongs to / （1.1）この記憶がどの約束に属するか
    """
    createdAt: RecordedAt
    deletedAt: RecordedAt | None = None
    """
    After deletion: text is cleared; only the ID and deletion time remain (for auditing) / 削除後：text を空にし、ID と削除時刻だけを残す（監査用）
    """


class PlaceAdjacentItem(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    place: PlaceId
    travelMinutes: Annotated[int, Field(ge=0)]
    inferred: bool | None = None


class Place(BaseModel):
    """
    Place (2.2) / 地点（2.2）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    id: PlaceId
    name: str
    shortName: Annotated[str | None, Field(max_length=8, min_length=1)] = None
    """
    (1.14) Short name (Japanese, ≤ 8 characters): used for the first half 「{place}・{day}の{time of day}」 of the destination subtitle on the end-of-act page; omitted = use name / （1.14）短い名前（日本語、8 字以内）：幕末ページの行き先の副題の前半「{地点}・{日}の{時間帯}」に使う。省略 = name を使う
    """
    description: str
    adjacent: list[PlaceAdjacentItem]
    """
    Walking minutes; other paces such as running are converted by the narrator with a factor / 徒歩の分数。走るなど他のペースはナレーターが係数で換算する
    """
    crossing: Annotated[PlaceCrossing | None, Field(title="PlaceCrossing")] = None
    """
    Place with a river / 川のある地点
    """
    sceneRef: SceneId | None
    """
    The corresponding 3D scene; null = no scene in the first version / 対応する 3D シーン。null = 最初の版ではシーンなし
    """
    inferred: bool | None = None
    """
    A place not in the original, designed for the game / 原文にはなく、ゲームのために設計した地点
    """
    note: str | None = None
    cite: list[Cite]


class Playthrough(BaseModel):
    """
    One playthrough of the game (section 1) / 1 回のプレイ（第 1 節）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    schemaVersion: SchemaVersion
    playthroughId: PlaythroughId
    userRef: str
    """
    Anonymous ID of the invite-code account (S-020), not an email address or a name / 招待コードアカウントの匿名 ID（S-020）。メールアドレスでも氏名でもない
    """
    worldModelVersion: str
    """
    Locked at the start, unchanged for the whole playthrough / 開始時に固定し、プレイ中は変わらない
    """
    roleId: RoleId
    """
    The role the player chose / プレイヤーが選んだ身分
    """
    playerAlias: str | None = None
    """
    S-010: not filled by default; the first version has no UI for it / S-010：既定では埋めない。最初の版には入力する画面がない
    """
    ageBand: Literal["under13", "13to17", "18plus", "unknown"] | None = None
    """
    S-010: not collected by default / S-010：既定では収集しない
    """
    status: Literal["active", "ended", "abandoned", "deleted"]
    startedAt: RecordedAt
    endedAt: RecordedAt | None = None
    lastActiveAt: RecordedAt
    """
    Real time of the last player activity; the default retention period counts from it / プレイヤーが最後に操作した実時間。既定の保持期間はこれを起点に数える
    """
    lastSeq: Annotated[int, Field(ge=0)]
    """
    Sequence number of the last event / 最後のイベントの通し番号
    """


class PromiseTemplate(BaseModel):
    """
    (1.1) Promises typical for this character; the narrator references them when writing promise effects (2.1) / （1.1）この登場人物によくある約束。ナレーターが promise エフェクトを書くときに参照する（2.1）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    id: PromiseTemplateId
    by: Literal["player"] | CharacterId
    """
    Who makes the promise; the other party is the character the template belongs to (when by is that character, the other party is the player) / 誰が約束するか。相手はテンプレートが属する登場人物（by がその登場人物自身のときは、相手はプレイヤー）
    """
    text: str
    """
    What is promised (in Japanese), e.g. 「必ず戻る」 / 約束の内容（日本語）。例「必ず戻る」
    """
    inferred: Literal[True] | None = None
    cite: list[Cite] | None = None
    note: str | None = None
    """
    (1.4) Tone, and on what occasion / （1.4）口調、どんな場面か
    """


class RoleConditionalAccessItem(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    place: PlaceId
    when: list[Condition]
    note: str | None = None


class Role(BaseModel):
    """
    Player role (2.7) / プレイヤーの身分（2.7）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    id: RoleId
    name: str
    summary: Annotated[str, Field(min_length=1)]
    """
    (1.10) One sentence shown to the player on the role page and in the manifest (in Japanese); UX decides the wording. note is for authors and not shown to the player / （1.10）身分ページと manifest でプレイヤーに見せる一文（日本語）。文言は UX が決める。note は書き手向けで、プレイヤーには見せない
    """
    release: Annotated[int, Field(ge=1)]
    """
    Which release opens it / どの版で開放するか
    """
    startAct: ActId
    startPlace: PlaceId
    startT: StoryTime
    knownCharacters: list[CharacterId]
    """
    Whom they know from the start (these characters start with trust +10) / 最初から知っている相手（これらの登場人物は開始時に信頼 +10）
    """
    access: list[PlaceId]
    """
    Places they can enter and leave freely / 自由に出入りできる地点
    """
    conditionalAccess: list[RoleConditionalAccessItem] | None = None
    """
    (1.1) Can also enter when the conditions are met / （1.1）条件を満たせば入ることもできる
    """
    initialKnowledge: list[FactId]
    """
    Facts the role knows from the outset / 身分が最初から知っている fact
    """
    items: list[ItemId] | None = None
    """
    (1.3) Items carried at the start / （1.3）開始時に身に付けているアイテム
    """
    inferred: Literal[True] = True
    note: str | None = None


class RunFact(BaseModel):
    """
    (1.1) Improvised fact for this playthrough (3.1) / （1.1）このプレイの即興の設定（3.1）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    factId: RunFactId
    character: CharacterId
    """
    Who said it (whom it is attributed to) / 誰が言ったか（誰に帰属するか）
    """
    statement: str
    """
    One neutral Japanese sentence / 中立的な日本語の一文
    """
    madeBy: EventId
    """
    The event that recorded it / これを記録したイベント
    """


class Scene(BaseModel):
    """
    3D scene (2.2) / 3D シーン（2.2）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    id: SceneId
    """
    The ID is proposed by the frontend (frontend-design 8.1) / ID はフロントエンドが提案する（frontend-design 8.1）
    """
    name: str
    release: Annotated[int, Field(ge=1)]
    """
    Which release builds it / どの版で作るか
    """
    inferred: Literal[True] = True
    note: str | None = None


class SetPiece(BaseModel):
    """
    (1.7) Set piece (2.11, S-080 ④): pre-written 地の文 and characters' pre-recorded lines, the same in every playthrough, attached to a beat or a player action and sent by the server at the right moment. Staging only: not an event, does not change the world state; the exception is learns (what is said in the set piece becomes known to those who hear it) / （1.7）固定演出（2.11、S-080 ④）：どのプレイでも同じ、書き上げ済みの地の文と登場人物の事前収録セリフ。ビートやプレイヤーのアクションに結び付き、サーバーが適切なタイミングで送る。演出にすぎず、イベントではなく、世界状態を変えない。例外は learns（演出の中で語られたことは、聞いた人が知る）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    id: SetPieceId
    on: SetPieceOnOption1 | SetPieceOnOption2
    """
    When it plays: when this beat happens with the player present (beats settled together on entering the ending ignore presence and count as part of the ending staging, 2.11), or after this kind of player action is judged / いつ演じるか：このビートが起きたときにプレイヤーが居合わせた場合（エンディングに入るときにまとめて精算するビートは居合わせたかを見ず、エンディングの演出に含める、2.11）、またはプレイヤーのこの種のアクションが判定された後
    """
    after: list[BeatId] | None = None
    """
    These beats have already happened (happened / altered) / これらのビートはすでに起きている（happened / altered）
    """
    before: list[BeatId] | None = None
    """
    These beats have not happened yet / これらのビートはまだ起きていない
    """
    knows: list[SetPieceKnowsItem] | None = None
    """
    These characters know this: an entry in Character.knows that already holds at this moment (since), or a learn already committed in this playthrough / これらの登場人物がこのことを知っている：Character.knows のうちこの時点で成り立っているもの（since）、またはこのプレイでコミット済みの learn
    """
    played: list[SetPieceId] | None = None
    """
    At least one of these set pieces has already played in this playthrough / これらの固定演出のうち少なくとも 1 つがこのプレイですでに演じられた
    """
    notPlayed: list[SetPieceId] | None = None
    """
    None of these set pieces has played yet in this playthrough / これらの固定演出はこのプレイでまだどれも演じられていない
    """
    when: list[Condition] | None = None
    """
    Other state conditions (same as beat preconditions) / その他の状態条件（ビートの前提条件と同じ）
    """
    once: Literal[True] | None = None
    """
    Plays only once per playthrough / 1 回のプレイで 1 度だけ演じる
    """
    lines: Annotated[list[SetPieceLinesItemOption1 | SetPieceLinesItemOption2], Field(min_length=1)]
    """
    Played in order; the whole entry is sent in a single set_piece message (api-contract 3.14): narration = 地の文; speaker + line = one pre-recorded line by this character (generated at build time, ux-design 16.2), whose recording is the manifest's setPieceVoices["{id}/{n}"], with n starting at 1 and 地の文 lines counted too / 順に演じ、全体を 1 つの set_piece メッセージで送る（api-contract 3.14）：narration = 地の文。speaker + line = その登場人物の事前収録セリフ 1 つ（ビルド時に生成、ux-design 16.2）。録音は manifest の setPieceVoices["{id}/{番号}"] で、番号は 1 から始まり地の文も数える
    """
    learns: Annotated[list[SetPieceLearnsItem] | None, Field(min_length=1)] = None
    """
    Who learns what when this plays (S-077 ⑪): in the same commit as this set piece, the server writes a separate event of type learn right after it (actor = the first character who speaks, or system when there is only 地の文; checker set-piece; origin action when triggered by an action, no origin when triggered by a beat). Only learn is allowed, not arbitrary effects: set pieces do not go through the narrator's R1〜R7 / これを演じたとき誰が何を知るか（S-077 ⑪）：サーバーはこの演出と同じコミットの中で、直後に type learn のイベントを別に書く（actor = 最初に話す登場人物、地の文だけなら system。checker は set-piece。アクションがきっかけなら origin action、ビートがきっかけなら origin は書かない）。learn だけを許し、任意の effects は許さない：固定演出はナレーターの R1〜R7 を通らない
    """
    inferred: Literal[True] = True
    note: str | None = None


class StateVarValueRequiresItem(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    value: Any
    """
    One value of this variable (an enum must be in values; otherwise it must match the type) / この変数の値の 1 つ（enum は values の中、それ以外は型に合うこと）
    """
    when: Annotated[list[Condition], Field(min_length=1)]
    """
    All must hold before the variable can be changed to value; same Condition and evaluation function as beat preconditions / すべて成り立つときだけ value に変更できる。ビートの前提条件と同じ Condition と評価関数を使う
    """
    note: Annotated[str, Field(min_length=1)]
    """
    Why this condition exists (in Japanese); when it fails, the narrator's reason includes the variable, value and this note / この条件がある理由（日本語）。成り立たないとき、ナレーターの reason に変数、value とこれを含める
    """
    inferred: Literal[True] = True
    cite: list[Cite] | None = None


class StateVar(BaseModel):
    """
    State variable (2.6) / 状態変数（2.6）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    id: VarId
    type: Literal["enum", "int", "bool", "place", "minutes"]
    values: list[str] | None = None
    min: float | None = None
    max: float | None = None
    default: Any
    """
    The initial values of var.player.location and var.act.current are set by the role / var.player.location と var.act.current の初期値は身分で決まる
    """
    keyMoment: bool | None = None
    """
    A variable that decides the ending / エンディングを決める変数
    """
    visibleToPlayer: bool | None = None
    """
    Whether changes may be shown to the player; default false / 変化をプレイヤーに表示してよいか。既定は false
    """
    valueLabels: dict[str, str] | None = None
    """
    Value → a Japanese sentence that can be shown directly / 値 → そのまま表示できる日本語の一文
    """
    valueRequires: list[StateVarValueRequiresItem] | None = None
    """
    (1.6, C-16) Conditions that must hold to change a variable to a given value (2.6). ① Applies only to events the narrator commits; scheduled beats and deadlines (origin = schedule) are not checked, since beat outcomes are governed by beat preconditions; ② checked only when the value actually changes, not when set to its current value; ③ evaluated against the state before this effect, with earlier effects in the same event already applied; ④ a failing when reports R2; ⑤ if the condition stops holding after the value is set, it is not reverted automatically and is not a violation / （1.6、C-16）変数をある値に変えるときに満たすべき条件（2.6）。① ナレーターがコミットするイベントだけが対象で、予定時刻のビートと期限（origin = schedule）は判定しない。ビートの結果はビートの前提条件が管理する。② 値が実際に変わるときだけ判定し、現在の値に設定する場合は判定しない。③ この effect の直前の状態で判定する（同じイベント内の前の effect は適用済み）。④ when が成り立たなければ R2 を報告する。⑤ 設定後に条件が成り立たなくなっても自動で元に戻さず、違反ともみなさない
    """
    description: str


class StoryPromiseDue(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    t: StoryTime | None = None
    beat: BeatId | None = None


class StoryPromise(BaseModel):
    """
    (1.1) Promise, derived from promise effects, not written separately (3.1). Called StoryPromise in the generated code to avoid JS's Promise / （1.1）約束。promise エフェクトから導き、別には書かない（3.1）。生成コードでは JS の Promise を避けて StoryPromise と呼ぶ
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    promiseId: PromiseId
    from_: Annotated[Literal["player"] | CharacterId, Field(alias="from")]
    """
    The party who made the promise / 約束した側
    """
    to: Literal["player"] | CharacterId
    """
    The other party / 相手
    """
    text: str
    """
    What was promised (Japanese, neutral, not the verbatim words) / 約束の内容（日本語、中立的、発言そのものではない）
    """
    due: Annotated[StoryPromiseDue | None, Field(title="StoryPromiseDue")] = None
    template: PromiseTemplateId | None = None
    status: Literal["open", "kept", "broken", "voided"]
    """
    Open / kept / broken / voided (まだ / 果たされた / 破られた / 無効) / まだ / 果たされた / 破られた / 無効
    """
    madeBy: EventId
    """
    The event that made it / 成立したイベント
    """
    resolvedBy: EventId | None = None
    """
    The event that kept, broke or voided it / 果たされた、破られた、または無効になったイベント
    """


class Utterance(BaseModel):
    """
    Verbatim utterances of the player and characters, stored separately and deletable (section 3) / プレイヤーと登場人物の発言そのもの。別に保存し、削除できる（第 3 節）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    utteranceId: UtteranceId
    playthroughId: PlaythroughId
    turnId: TurnId
    """
    Cleared per turn when deleted from the 記憶帳 (section 4) / 記憶帳から削除するとターン単位で消去する（第 4 節）
    """
    speaker: Literal["player"] | CharacterId
    text: str
    """
    Recognized text (audio is not stored); cleared after deletion / 認識後のテキスト（音声は保存しない）。削除後は空にする
    """
    t: StoryTime
    recordedAt: RecordedAt
    deletedAt: RecordedAt | None = None
    """
    text is cleared after deletion / 削除後は text を空にする
    """


class WorldEnding(BaseModel):
    """
    Baseline classes of world endings (2.9, S-007) / 世界のエンディングの基本分類（2.9、S-007）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    id: WorldEndingId
    """
    Written into Ending.world.outcome / Ending.world.outcome に書き込む
    """
    order: Annotated[int, Field(ge=1)]
    """
    Evaluation order: starting at 1, the first whose conditions are all met is this playthrough's world ending / 判定順：1 から始め、条件をすべて満たす最初のものがこのプレイの世界のエンディングになる
    """
    label: str
    """
    Japanese, shown on the ending card / 日本語。エンディングカードに表示する
    """
    when: list[Condition]
    """
    Evaluated against the WorldState at the ending / エンディング時の WorldState で判定する
    """
    inferred: Literal[True] = True
    note: str | None = None


class WorldModelEndingsTemplatesItem(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    outcome: WorldEndingId
    when: list[Condition] | None = None
    subtitle: Annotated[str, Field(min_length=1)]
    """
    Where the world ends up (card subtitle), ≤ 26 characters / 世界の行く末（カードの副題）。26 字以内
    """
    title: Annotated[str, Field(min_length=1)]
    """
    Title, containing one {role} (replaced with the starting role name); ≤ 9 characters without {role} / 称号。{role} を 1 つ含む（開始時の身分名に置き換える）。{role} を除いて 9 字以内
    """
    fate: Annotated[str | None, Field(min_length=1)] = None
    """
    行方 (whereabouts). Omitted = taken from endings.fates by fate.id / 行方。省略 = fate.id で endings.fates から取る
    """
    lines: Annotated[list[WorldModelEndingsTemplatesItemLinesItem], Field(min_length=1)]
    """
    Assigned to rank 1, 2… in order / 順に rank 1、2… に割り当てる
    """
    contrast: Annotated[str, Field(min_length=1)]
    """
    「原作との違い」 (difference from the original), ≤ 48 characters / 「原作との違い」。48 字以内
    """
    note: str | None = None


class WorldModelEndings(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    world: list[WorldEnding]
    """
    Baseline classes of world endings (S-007, S-034) / 世界のエンディングの基本分類（S-007、S-034）
    """
    signature: EndingSignature | None = None
    """
    (1.1) What counts as "substantively different endings"; see 2.9.1 / （1.1）「エンディングが実質的に異なる」とは何か。2.9.1 を参照
    """
    characters: list[CharacterId] | None = None
    """
    (1.11, B-9) The characters whose endings the ending page lists; the order is the tie-break order. Omitted = the talkable characters / （1.11、B-9）エンディングページで結末を並べる登場人物。並び順が同点時の順序になる。省略 = talkable の登場人物
    """
    templates: list[WorldModelEndingsTemplatesItem] | None = None
    """
    (1.11, B-9, S-065) Sentences used when the ending goes through a template (ux-design 11.4). When one outcome has several entries, the first whose when holds is taken; the last entry has no when / （1.11、B-9、S-065）エンディングがテンプレートを使うときの文（ux-design 11.4）。同じ outcome に複数あるときは when が成り立つ最初のものを取る。最後の 1 件には when を付けない
    """
    fates: Annotated[WorldModelEndingsFates | None, Field(title="WorldModelEndingsFates")] = None
    """
    (1.11, B-9) The 行方 used when the template has no fate, taken by Ending.player.fate.id: witness if present at the ending's place, elsewhere if not (ux-design 11.4) / （1.11、B-9）テンプレートに fate がないときの行方。Ending.player.fate.id で取る：エンディングの地点に居合わせたら witness、いなければ elsewhere（ux-design 11.4）
    """


class WorldState(BaseModel):
    """
    The current state derived from events, not a second source of truth (3.1): the world model's initial values + the effects of all events applied in seq order / イベントから導いた現在の状態で、2 つ目の事実ではない（3.1）：世界モデルの初期値 + 全イベントの effects を seq の順に適用したもの
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    playthroughId: PlaythroughId
    asOfSeq: Annotated[int, Field(ge=0)]
    """
    Up to which event it has been derived / どのイベントまで導出したか
    """
    t: StoryTime
    """
    Clock = max(t + dt) over all events / 時計 = 全イベントの max(t + dt)
    """
    vars: dict[VarId, Any]
    """
    Current values of all stateVars / すべての stateVar の現在の値
    """
    beats: dict[BeatId, Literal["pending", "happened", "prevented", "delayed", "hastened", "altered"]]
    schedule: dict[BeatId, StoryTime]
    """
    This playthrough's scheduled times for beats that have no outcome yet (2.5.1) / まだ結果の出ていないビートの、このプレイでの予定時刻（2.5.1）
    """
    knowledge: dict[CharacterId, list[FactId | RunFactId]]
    """
    Character → facts newly learned at runtime / 登場人物 → 実行時に新たに知った fact
    """
    locations: dict[CharacterId, PlaceId]
    """
    Character → place / 登場人物 → 地点
    """
    spots: dict[CharacterId, SpotId] | None = None
    """
    (1.7) Character → assigned spot: present only when a relocate specified a spot; removed when moving to another place. Characters without one are placed by the backend using the layout's placement rules (section 3.1) / （1.7）登場人物 → 指定された位置点：relocate に spot が書かれたときだけある。別の地点に移ると取り除く。ない場合はバックエンドがレイアウトの立ち位置の規則で配置する（第 3.1 節）
    """
    promises: dict[PromiseId, StoryPromise] | None = None
    """
    (1.1) promiseId → promise / （1.1）promiseId → 約束
    """
    runFacts: dict[RunFactId, RunFact] | None = None
    """
    (1.1) factId → improvised fact / （1.1）factId → 即興の設定
    """
    holdings: dict[ItemId, Literal["player"] | CharacterId | None] | None = None
    """
    (1.3) Portable item → who holds it now / （1.3）portable なアイテム → いま誰が持っているか
    """


class ActEndLinesItem(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    when: list[Condition] | None = None
    """
    The state of this playthrough must meet this; omitted = always / このプレイの状態が満たすべき条件。省略 = 常に
    """
    line: Annotated[str, Field(min_length=1)]
    """
    Japanese, 地の文 (narration) / 日本語、地の文
    """


class CharacterTraitsItem(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    text: str
    cite: list[Cite]
    since: BeatId | None = None
    """
    Used only from when that beat happens (1.1) / そのビートが起きてから使う（1.1）
    """
    until: BeatId | None = None
    """
    No longer used after that beat happens (1.1) / そのビートが起きた後は使わない（1.1）
    """
    when: list[Condition] | None = None
    """
    Used only when the current WorldState meets these conditions (1.4); when since / until / when are all given, all three must hold / 現時点の WorldState がこれらの条件を満たすときだけ使う（1.4）。since / until / when を同時に書いた場合は 3 つすべてを満たす必要がある
    """


class CharacterGoalsItem(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    text: str
    cite: list[Cite]
    since: BeatId | None = None
    """
    Used only from when that beat happens (1.1) / そのビートが起きてから使う（1.1）
    """
    until: BeatId | None = None
    """
    No longer used after that beat happens (1.1) / そのビートが起きた後は使わない（1.1）
    """
    when: list[Condition] | None = None
    """
    Used only when the current WorldState meets these conditions (1.4); when since / until / when are all given, all three must hold / 現時点の WorldState がこれらの条件を満たすときだけ使う（1.4）。since / until / when を同時に書いた場合は 3 つすべてを満たす必要がある
    """


class CharacterSpeechSampleLinesItem(BaseModel):
    """
    Lines from the original, quoted directly. The contract writes this as Cite & { since?, until?, when? }: here it is a plain closed object whose source / para / quote reference Cite's fields by JSON pointer (so the constraints live in one place); allOf is not used, so the generated type is closed too / 原文のセリフをそのまま引用する。契約上は Cite & { since?, until?, when? } と書く：ここでは閉じた普通のオブジェクトとし、source / para / quote は JSON ポインタで Cite のフィールドを参照する（制約は 1 か所だけ）。allOf は使わないので、生成される型も閉じている
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    source: str
    """
    Original-text version ID, e.g. "aozora:1567_ruby_4948@sha256:2a437c047d7f" (hash of the normalized full text) / 原文のバージョン ID。例："aozora:1567_ruby_4948@sha256:2a437c047d7f"（正規化した全文のハッシュ）
    """
    para: Annotated[int, Field(ge=1)]
    """
    Paragraph number in the normalized text, starting at 1 / 正規化テキスト内の段落番号。1 から始まる
    """
    quote: Annotated[str, Field(max_length=80, min_length=1)]
    """
    Excerpt from the original, ≤ 80 characters. Must be an exact substring of that paragraph (a cross-field rule, checked by build_world, not in the Schema) / 原文の抜粋。80 字以内。その段落の正確な部分文字列でなければならない（フィールドをまたぐ規則なので build_world が検証し、Schema には含めない）
    """
    since: BeatId | None = None
    """
    Used only from when that beat happens (1.1) / そのビートが起きてから使う（1.1）
    """
    until: BeatId | None = None
    """
    No longer used after that beat happens (1.1) / そのビートが起きた後は使わない（1.1）
    """
    when: list[Condition] | None = None
    """
    Used only when the current WorldState meets these conditions (1.4); when since / until / when are all given, all three must hold / 現時点の WorldState がこれらの条件を満たすときだけ使う（1.4）。since / until / when を同時に書いた場合は 3 つすべてを満たす必要がある
    """


class CharacterSpeech(BaseModel):
    """
    Way of speaking, for the character agent and evals / 話し方。キャラクター Agent と評価で使う
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    firstPerson: str | None = None
    """
    「私」「わし」… / 「私」「わし」…
    """
    register_: Annotated[str, Field(alias="register")]
    sampleLines: list[CharacterSpeechSampleLinesItem]
    """
    Lines from the original, quoted directly / 原文のセリフをそのまま引用
    """
    designLines: list[DesignLine] | None = None
    """
    (1.4) Sample lines not in the original, written for the game / （1.4）原文にはなく、ゲームのために書いたセリフ例
    """


class ActPlan(BaseModel):
    """
    (1.7, C-19) Where the player lands when the plan they state at the end of the act is carried out (2.8.1 step 2): the event that carries it out writes the next act, place, time, landing spot and landing from here. Omitted = the narrator decides from the world model (set in M3) / （1.7、C-19）幕末でプレイヤーが述べたプランが実行されたとき、どこに降り立つか（2.8.1 第 2 段階）：実行のイベントは、次の幕、地点、時刻、降り立つ位置、降り立ちをここに従って書く。省略 = ナレーターが世界モデルに基づいて判断する（M3 で決定）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    toAct: ActId
    place: PlaceId
    """
    Where the next act starts / 次の幕の開始地点
    """
    t: StoryTime
    """
    What time the next act starts / 次の幕が始まる時刻
    """
    spot: SpotId | None = None
    """
    Which spot in place the player lands on; omitted = this place's starting point (startSpots) / プレイヤーが place のどの位置点に降り立つか。省略 = この地点の開始位置（startSpots）
    """
    effects: list[Effect]
    """
    Fixed effects of carrying out the plan itself (e.g. a character's relocate); the plan's own effects are extracted by the narrator from what the player says, checked as usual, and added to the same event / プラン実行そのものに伴う固定のエフェクト（例：登場人物の relocate）。プラン自体のエフェクトはナレーターがプレイヤーの発言から抽出し、通常どおり検査してから同じイベントに加える
    """
    arrival: Annotated[ActPlanArrival | None, Field(title="ActPlanArrival")] = None
    """
    Landing, same as ActExit.arrival / 降り立ち。ActExit.arrival と同じ
    """


class Act(BaseModel):
    """
    Act (2.8, S-004) / 幕（2.8、S-004）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    id: ActId
    order: Annotated[int, Field(ge=1)]
    title: str
    start: Annotated[ActStart, Field(title="ActStart")]
    """
    The earliest time this act can start / この幕が最も早く始まる時刻
    """
    end: Annotated[ActEnd, Field(title="ActEnd")]
    scenes: list[SceneId]
    """
    Scenes this act may use (the frontend preloads them based on this) / この幕で使う可能性のあるシーン（フロントエンドはこれをもとに先読みする）
    """
    exits: list[ActExit]
    """
    End-of-act destinations; empty for the last act, where closing the act goes straight to the ending / 幕末の行き先。最後の幕は空で、幕を閉じるとそのままエンディングに入る
    """
    endLines: list[ActEndLinesItem] | None = None
    """
    (1.15, UX copy-ja 6.1) The first line of the end-of-act page: the first entry (in order) whose when is met; if none is met (e.g. a beat was rewritten) the narrator writes it. Only states what the player can know at this moment / （1.15、UX copy-ja 6.1）幕末ページの最初の行：when を満たす最初の項目を順に取る。どれも満たさない場合（例：ビートが書き換えられた）はナレーターが書く。プレイヤーがこの時点で知り得ることだけを書く
    """
    closingLine: Annotated[str | None, Field(min_length=1)] = None
    """
    (1.15, UX copy-ja 6.1, ux-design 4.3) A one-line preview the server sends when the act is about to end (in Japanese) / （1.15、UX copy-ja 6.1、ux-design 4.3）幕がもうすぐ終わるときにサーバーが送る 1 行の予告（日本語）
    """
    stops: list[PlaceId] | None = None
    """
    (1.14, S-081) Places where Melos stops in this act (stops on the way back). A player following him (companionOf = char.melos) moves with him from other places; when he leaves a stop he does not take the player along. Omitted = no stops / （1.14、S-081）この幕でメロスが立ち止まる地点（帰路の立ち寄り先）。彼についているプレイヤー（companionOf = char.melos）は、ほかの地点では彼と一緒に移動する。立ち寄り先を離れるときはプレイヤーを連れていかない。省略 = 立ち寄り先なし
    """
    plan: Annotated[ActPlan | None, Field(title="ActPlan")] = None
    """
    (1.7, C-19) Where the player lands when the plan they state at the end of the act is carried out (2.8.1 step 2): the event that carries it out writes the next act, place, time, landing spot and landing from here. Omitted = the narrator decides from the world model (set in M3) / （1.7、C-19）幕末でプレイヤーが述べたプランが実行されたとき、どこに降り立つか（2.8.1 第 2 段階）：実行のイベントは、次の幕、地点、時刻、降り立つ位置、降り立ちをここに従って書く。省略 = ナレーターが世界モデルに基づいて判断する（M3 で決定）
    """
    inferred: Literal[True] = True
    note: str | None = None


class ActExit(BaseModel):
    """
    Suggested end-of-act destination (2.8) / 幕末のおすすめの行き先（2.8）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    id: ExitId
    label: str
    """
    The option the player sees (in Japanese) / プレイヤーに見える選択肢（日本語）
    """
    toAct: ActId
    place: PlaceId
    """
    Where the next act starts / 次の幕の開始地点
    """
    t: StoryTime
    """
    What time the next act starts / 次の幕が始まる時刻
    """
    alignTo: BeatId | None = None
    """
    Follows a beat: t shifts by however much that beat was delayed/advanced in this playthrough / あるビートに合わせる：このプレイでそのビートが遅れた／早まった分だけ t をずらす
    """
    roles: list[RoleId] | None = None
    """
    Open only to these roles; omitted = all / これらの身分にだけ開放する。省略 = すべて
    """
    requires: list[Condition] | None = None
    """
    The state when the act closes must meet this / 幕を閉じるときの状態が満たすべき条件
    """
    effects: list[Effect]
    """
    Effects of the choice itself / 選択そのもののエフェクト
    """
    enRoute: EnRoute | None = None
    """
    (1.4) When the skipped stretch of road contains a beat that can be changed, the transition page offers a choice between two / （1.4）飛ばした道のりに変えられるビートがあるとき、場面転換ページで二択を出す
    """
    sub: Annotated[str | None, Field(max_length=16, min_length=1)] = None
    """
    (1.7) The second half of this destination's subtitle on the end-of-act page (in Japanese, narrative tone, no minute counts); the first half 「{place}・{day}の{time of day}」 is computed by the server from place's Place.name and t (day and time of day per clock.labels, without applying its format) and sent together with the second half (ux-design 4.4). Omitted = first half only / （1.7）幕末ページでのこの行き先の副題の後半（日本語、語りの口調、分数は書かない）。前半「{地点}・{日}の{時間帯}」はサーバーが place の Place.name と t から算出し（日と時間帯は clock.labels に従い、その format は適用しない）、後半と一緒に送る（ux-design 4.4）。省略 = 前半のみ
    """
    spot: SpotId | None = None
    """
    (1.7) Which spot in place the player lands on; omitted = the frontend uses this place's starting point (startSpots in layout.json) / （1.7）プレイヤーが place のどの位置点に降り立つか。省略 = フロントエンドがこの地点の開始位置（layout.json の startSpots）を使う
    """
    arrival: Annotated[ActExitArrival | None, Field(title="ActExitArrival")] = None
    """
    (1.7) Landing: the first line of narration and the character who speaks first (ux/slice/jump-transition.md, "Landing") / （1.7）降り立ち：最初の語りと最初に口を開く登場人物（ux/slice/jump-transition.md の「降り立ち」）
    """


class Affordance(BaseModel):
    """
    (1.1) Affordance (situational action) (2.10) / （1.1）状況アクション（2.10）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    id: AffordanceId
    kind: Literal["examine", "give", "follow", "block", "help", "wait", "go", "shortcut", "run-together", "hasten"]
    label: str
    """
    Verb phrase on the button (in Japanese), without the time it takes / ボタン上の動詞句（日本語）。所要時間は書かない
    """
    pastLabel: Annotated[str, Field(max_length=30, min_length=1, pattern="^[^。]*[ただ]$")]
    """
    (1.8) The event sentence once done (Japanese, past tense, with the object, without the subject or 「。」), e.g. 「老爺を家まで送った」. The narrator writes the summary as 「{Role.name}は、{pastLabel}」, and the server replaces it with 「あなた」 when sending it to the player / （1.8）やり終えた後のイベント文（日本語、過去形、目的語あり、主語と「。」なし）。例「老爺を家まで送った」。ナレーターは summary を「{Role.name}は、{pastLabel}」と書き、プレイヤーに送るときサーバーが「あなた」に置き換える
    """
    place: PlaceId
    """
    Which place it appears in / どの地点に現れるか
    """
    act: ActId | None = None
    """
    Only in this act / この幕のみ
    """
    roles: list[RoleId] | None = None
    """
    Only for these roles; omitted = all / これらの身分のみ。省略 = すべて
    """
    target: CharacterId | None = None
    """
    Target character / 対象の登場人物
    """
    item: ItemId | None = None
    """
    Required when kind = give: the item handed over / kind = give のときは必須：渡すアイテム
    """
    minutes: Annotated[int, Field(ge=0)]
    """
    Story time the player spends (= the event's dt) / プレイヤーが費やす物語時間（= イベントの dt）
    """
    melos: Literal["delay", "hasten"] | None = None
    """
    Effect on Melos in the fourth act / 第四幕でのメロスへの影響
    """
    melosMinutes: int | None = None
    """
    (1.4) Required when melos is present: how many minutes later (+) or earlier (−) Melos reaches the execution ground / （1.4）melos があるときは必須：メロスが刑場に何分遅く（+）／早く（−）着くか
    """
    when: list[Condition] | None = None
    """
    Conditions for it to appear / 出現条件
    """
    aid: AidId | None = None
    """
    If it succeeds, this aid is fulfilled (MutualAid.id of a fromYou entry) / 成功したらこの助け合いを果たしたことになる（fromYou の MutualAid.id）
    """
    playerSpot: SpotId | None = None
    """
    (1.7) Which spot in place the player stands on afterwards (layout spots); omitted = does not move. Applies only to the player; characters use relocate's spot / （1.7）やり終えた後にプレイヤーが place のどの位置点に立つか（レイアウトの spots）。省略 = 動かない。プレイヤーにのみ適用し、登場人物は relocate の spot を使う
    """
    effects: list[Effect]
    """
    Effect templates: effects committed when the check passes; empty = affects relationships only / エフェクトのテンプレート：判定に通ったときにコミットするエフェクト。空 = 関係にだけ影響する
    """
    inferred: Literal[True] = True
    note: str | None = None
    cite: list[Cite] | None = None


class Beat(BaseModel):
    """
    Plot beat (2.4) / 筋のビート（2.4）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    id: BeatId
    order: float
    """
    Order in the original (may be fractional, to sit between two beats) / 原作での順序（小数でもよく、2 つのビートの間に挟める）
    """
    title: str
    summary: str
    window: Annotated[BeatWindow, Field(title="BeatWindow")]
    """
    Story minutes; in the original it happens at canonical; after latest it can no longer happen / 物語上の分。原作では canonical に起きる。latest を過ぎるともう起こり得ない
    """
    place: PlaceId
    participants: list[CharacterId]
    kind: Literal["anchor", "mutable"]
    """
    anchor: cannot be prevented or rewritten; mutable: can be moved earlier, delayed, prevented, or have its outcome changed / anchor：阻止も書き換えもできない。mutable：早める、遅らせる、阻止する、結果を変えることができる
    """
    preconditions: list[Condition]
    """
    Preconditions for it to happen, referencing stateVars / 発生の前提条件。stateVars を参照する
    """
    outcomes: list[Effect]
    """
    Effect on the state after it happens in the original / 原作で起きた後の状態への影響
    """
    activities: list[BeatActivitiesItem] | None = None
    """
    (1.1) What this character is doing after the beat happens / （1.1）ビートが起きた後にこの登場人物が何をしているか
    """
    variants: list[BeatVariant] | None = None
    """
    (1.4) When it happens on schedule, swapped for another way of playing it out based on this playthrough's state / （1.4）予定時刻に起きるとき、このプレイの状態に応じて別の演じ方に差し替える
    """
    arriveBefore: Annotated[int | None, Field(ge=1)] = None
    """
    (1.14) How many minutes before this playthrough's scheduled time the participating characters arrive at this beat's place (stops on the way back: Melos arrives first, and the player can see him there); omitted = they arrive at the scheduled time / （1.14）参加する登場人物が、このプレイの予定時刻より何分早くこのビートの地点に着くか（帰路の立ち寄り先：メロスが先に着き、プレイヤーはそこに彼がいるのを見られる）。省略 = 予定時刻ちょうどに着く
    """
    cite: list[Cite]


class BeatVariant(BaseModel):
    """
    (1.4, S-064) Another way of playing out a beat, swapped in based on this playthrough's state when the beat happens on schedule (2.4) / （1.4、S-064）ビートが予定時刻に起きるとき、このプレイの状態に応じて差し替える別の演じ方（2.4）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    id: BeatId
    """
    E.g. "beat.25.v-no-doubt" / 例："beat.25.v-no-doubt"
    """
    when: list[Condition]
    """
    When the beat is due and its preconditions hold, the first variant (in order) whose when is fully met is taken / ビートが予定時刻になり前提条件が成り立つとき、when をすべて満たす最初のバリアントを順に取る
    """
    summary: str
    """
    How it plays out in this playthrough (in Japanese) / このプレイでの演じ方（日本語）
    """
    outcomes: list[Effect]
    """
    Replaces the beat's outcomes / ビートの outcomes の代わりになる
    """
    inferred: Literal[True] = True
    note: str | None = None
    cite: list[Cite] | None = None


class Character(BaseModel):
    """
    Character (2.1) / 登場人物（2.1）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    id: CharacterId
    name: str
    reading: str | None = None
    """
    How the name is read: katakana copied as is, kanji written in hiragana, e.g. 「おうディオニス」. (1.10) The manifest needs one for every character; build_world checks that every character has it and that it contains no kanji / 名前の読み方：カタカナはそのまま、漢字はひらがなで書く。例「おうディオニス」。（1.10）manifest では全登場人物に必要。build_world が全員分埋まっていて漢字を含まないことを検査する
    """
    summary: str
    """
    One or two sentences, neutral description / 1〜2 文の中立的な説明
    """
    traits: list[CharacterTraitsItem]
    """
    Personality traits, each with a source / 性格。各項目に出典がある
    """
    goals: list[CharacterGoalsItem]
    """
    Motivations (= the "current goal" of S-030) / 動機（= S-030 の「当面の目標」）
    """
    speech: Annotated[CharacterSpeech, Field(title="CharacterSpeech")]
    """
    Way of speaking, for the character agent and evals / 話し方。キャラクター Agent と評価で使う
    """
    knows: list[CharacterKnowsItem]
    """
    Which facts they know, and from which beat / どの fact を、どの beat から知っているか
    """
    initialPlace: PlaceId
    talkable: bool
    """
    Whether free conversation is available in the first version (S-003) / 最初の版で自由に会話できるか（S-003）
    """
    group: Literal[True] | None = None
    """
    (1.7) A group of people (crowd, officers, bandits, a band of travelers): does not occupy layout spots; the frontend places them as a group by place (placement rules in section 3.1 WorldState.spots) / （1.7）集団（群衆、警吏、山賊、旅人の一団）：レイアウトの位置点を占有せず、フロントエンドが地点ごとにまとめて配置する（立ち位置の規則は第 3.1 節 WorldState.spots を参照）
    """
    voiceRef: str | None = None
    """
    Reference to the voice configuration; the actual values are managed by backend/UX / 音声設定への参照。具体的な値はバックエンド／UX が管理する
    """
    initialActivity: Activity | None = None
    """
    (1.1) What they are doing at the start (default idle) / （1.1）開始時に何をしているか（既定は idle）
    """
    items: list[ItemId] | None = None
    """
    (1.3) Items carried at the start (Item IDs of portable items) / （1.3）開始時に身に付けているアイテム（portable な Item の ID）
    """
    cite: list[Cite]
    mutualAid: list[MutualAid] | None = None
    """
    (1.1) Aid: what they can do for you, and what you can do for them / （1.1）助け合い：相手があなたにできること、あなたが相手にできること
    """
    promiseTemplates: list[PromiseTemplate] | None = None
    """
    (1.1) Promises typical for this character / （1.1）この登場人物によくある約束
    """
    plans: list[CharacterPlansItem] | None = None
    """
    (1.1) For each act, their "plan when left alone" / （1.1）各幕の「誰も関わらないときのプラン」
    """
    originalEnding: Annotated[CharacterOriginalEnding | None, Field(title="CharacterOriginalEnding")] = None
    """
    (1.11, B-9) The 「原作では」 line on the ending page, which is also Melos's line on the card when no character was affected; required for every character in endings.characters / （1.11、B-9）エンディングページの「原作では」の一文。どの登場人物にも影響が及ばなかったときにカードに出るメロスの行でもある。endings.characters の登場人物には必須
    """


class ClockOnDeadlineItem(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    if_: Annotated[list[Condition], Field(alias="if")]
    then: list[Effect]
    note: str
    cite: list[Cite]


class Clock(BaseModel):
    """
    Clock: start time, deadline, names of times of day (2.6) / 時計：開始時刻、期限、時間帯の呼び方（2.6）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    startT: StoryTime
    """
    Default start time (for each role, see Role.startT) / 既定の開始時刻（各身分は Role.startT を参照）
    """
    deadline: Annotated[ClockDeadline, Field(title="ClockDeadline")]
    sunsetMinuteOfDay: Annotated[int, Field(ge=0, le=1439)]
    """
    Time of sunset; default 1140 (19:00) / 日没の時刻。既定は 1140（19:00）
    """
    onDeadline: list[ClockOnDeadlineItem]
    """
    Executed automatically when the deadline arrives (actor: "system"); every if is evaluated against the state at the moment of the deadline / 期限が来たら自動で実行する（actor: "system"）。if はすべて期限の時点の状態で判定する
    """
    labels: Annotated[ClockLabels, Field(title="ClockLabels")]
    """
    Rules for generating tLabel / tLabel の生成規則
    """


type Effect = Annotated[
    EffectSet | EffectInc | EffectBeat | EffectLearn | EffectRelocate | EffectPromise | EffectImprov | EffectHold,
    Field(discriminator="op", title="Effect"),
]
"""
Effect: 8 kinds distinguished by op (section 3). Shared by events, beat outcomes, destinations, affordances, aid and deadline rules / エフェクト：op で区別する 8 種類（第 3 節）。イベント、ビートの結果、行き先、状況アクション、助け合い、期限の規則で共用する
"""


class EffectBeat(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    op: Literal["beat"] = "beat"
    beat: BeatId
    to: Literal["happened", "prevented", "delayed", "hastened", "altered"]
    minutes: Annotated[int | None, Field(ge=0)] = None
    outcomes: list[Effect] | None = None
    """
    When altered = the changed outcomes (replacing the outcomes in the world model) / altered のとき = 変更後の結果（世界モデルの outcomes の代わり）
    """
    note: str | None = None


class EnRoute(BaseModel):
    """
    (1.4) A choice between two in the transition (2.8) / （1.4）場面転換での二択（2.8）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    beat: BeatId
    """
    The beat in the skipped stretch that can be changed / 飛ばした区間で変えられるビート
    """
    line: str
    """
    One line of narration on the transition page (in Japanese) / 場面転換ページの語りの一文（日本語）
    """
    choices: Annotated[list[EnRouteChoice], Field(max_length=2, min_length=2)]
    """
    Exactly two; the last one is "as in the original", with empty effects / ちょうど 2 つ。最後の 1 つは「原作どおり」で、effects は空
    """
    inferred: Literal[True] = True
    note: str | None = None
    cite: list[Cite] | None = None


class EnRouteChoice(BaseModel):
    """
    (1.5) One option of the transition choice (2.8) / （1.5）場面転換の二択の選択肢 1 つ（2.8）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    label: str
    """
    The verb on the button (in Japanese), without minute counts / ボタン上の動詞（日本語）。分数は書かない
    """
    effects: list[Effect]
    melosMinutes: int | None = None
    """
    (1.5) Required when effects include one that changes a beat: how many minutes earlier (−) or later (+) Melos reaches the execution ground / （1.5）effects にビートを変えるものがあるときは必須：メロスが刑場に何分早く（−）／遅く（+）着くか
    """
    after: str | None = None
    """
    (1.5) If this option is chosen, one more line on the transition page before entering the next act (in Japanese) / （1.5）この選択肢を選んだら、次の幕に入る前に場面転換ページにもう一文出す（日本語）
    """


class Event(BaseModel):
    """
    Runtime event, append-only (section 3). The narrator is the only writer / 実行時のイベント。追記のみ（第 3 節）。書き込むのはナレーターだけ
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    schemaVersion: SchemaVersion
    eventId: EventId
    playthroughId: PlaythroughId
    seq: Annotated[int, Field(ge=1)]
    """
    Strictly increasing within the playthrough, starting at 1; replay goes by seq / プレイ内で狭義単調増加、1 から始まる。リプレイは seq の順に行う
    """
    turnId: TurnId | None = None
    """
    Which turn it came from; system events have none / どのターンから来たか。system のイベントにはない
    """
    idempotencyKey: Annotated[str, Field(min_length=1)]
    """
    Prevents a duplicate write when a turn's commit is retried (generated by the backend and used for deduplication; must not be an empty string) / 同じターンのコミットを再試行しても重複して書かない（バックエンドが生成し、重複排除に使う。空文字列は不可）
    """
    worldModelVersion: str
    t: StoryTime
    """
    Story time when it happened; non-decreasing by seq / 起きた時点の物語時間。seq の順で減少しない
    """
    dt: Annotated[int, Field(ge=0)]
    """
    Story minutes this takes; after this event the clock = max(previous clock, t + dt) / この出来事が費やす物語上の分。このイベントの後の時計 = max(それまでの時計, t + dt)
    """
    recordedAt: RecordedAt
    actor: Actor
    type: Literal["say", "action", "move", "beat", "learn", "act-transition", "correction", "ending", "forget"]
    origin: Literal["turn", "action", "schedule", "plan", "director", "act", "memory"] | None = None
    """
    (1.1) Where the event came from; only for evals, Trace and ordering 「その頃」, not pushed to the frontend / （1.1）イベントの出どころ。評価、Trace、「その頃」の並べ替えにのみ使い、フロントエンドには送らない
    """
    beneficiary: Literal["player"] | CharacterId | None = None
    """
    (1.1) For whom this was done / （1.1）この出来事が誰のために行われたか
    """
    confirmed: Literal[True] | None = None
    """
    (1.1) Went through an in-story intent confirmation before commit (S-040) / （1.1）コミット前に物語内での意図確認を経た（S-040）
    """
    place: PlaceId
    summary: str
    """
    Neutral Japanese summary written by the narrator: only actions within the story, no verbatim player words, no real-world personal information / ナレーターが書く中立的な日本語の要約：物語内の行為だけを書き、プレイヤーの発言そのものや現実の個人情報は含めない
    """
    utteranceRefs: list[UtteranceId] | None = None
    """
    Related verbatim utterances (deletable; after deletion the IDs stay here but the content can no longer be retrieved) / 関連する発言そのもの（削除可能。削除後も ID はここに残るが、内容は取得できない）
    """
    causes: list[EventId | BeatId]
    """
    Which events (ev_…) or beats (beat.…) caused it / どのイベント（ev_…）またはビート（beat.…）が原因か
    """
    effects: list[Effect]
    """
    In committed events, promise effects must carry a promiseId (see Effect's promise branch) / コミットされたイベントの promise エフェクトには promiseId が必須（Effect の promise 分岐を参照）
    """
    keyMoment: bool
    """
    Computed at commit; (1.1) per the four rules of S-041 / コミット時に算出する。（1.1）S-041 の 4 条件に従う
    """
    check: CheckResult
    supersedes: EventId | None = None
    """
    Only for type=correction: which event is corrected / type=correction のみ：どのイベントを修正するか
    """
    exitId: ExitId | None = None
    """
    Only for type=act-transition (actor=player) and the action events of the transition choice / type=act-transition（actor=player）と場面転換の二択の action イベントのみ
    """
    plan: Annotated[EventPlan | None, Field(title="EventPlan")] = None
    """
    (1.2, S-031 ③) Only for type=act-transition (actor=player) when the player stated their own plan / （1.2、S-031 ③）type=act-transition（actor=player）で、プレイヤーが自分のプランを述べた場合のみ
    """


class MutualAid(BaseModel):
    """
    (1.1) Aid: what they can do for you, and what you can do for them (2.1) / （1.1）助け合い：相手があなたにできること、あなたが相手にできること（2.1）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    id: AidId
    direction: Literal["forYou", "fromYou"]
    """
    forYou = what they can do for you; fromYou = what you can do for them / forYou = 相手があなたにできること。fromYou = あなたが相手にできること
    """
    text: str
    """
    One Japanese sentence, for the narrator and character prompts; not shown directly to the player / 日本語の一文。ナレーターとキャラクタープロンプト用で、プレイヤーには直接表示しない
    """
    when: list[Condition] | None = None
    """
    Only possible under these conditions / これらの条件下でのみ可能
    """
    opening: RoleId | None = None
    """
    This entry is the role's "opening aid" for the first act (S-048) / この項目はその身分の第一幕の「開始時の助け合い」（S-048）
    """
    major: Literal[True] | None = None
    """
    forYou only: counts as a key moment when fulfilled (S-041) / forYou のみ：果たされたときに重要な瞬間として数える（S-041）
    """
    gives: ItemId | None = None
    """
    (1.3) forYou only: items the character hands you when it is fulfilled / （1.3）forYou のみ：果たされたときに登場人物があなたに渡すアイテム
    """
    effects: list[Effect] | None = None
    """
    (1.4) Effect templates committed when fulfilled (same as Affordance.effects) / （1.4）果たされたときにコミットするエフェクトのテンプレート（Affordance.effects と同じ）
    """
    inferred: Literal[True] = True
    cite: list[Cite] | None = None
    """
    Source, when there is support in the original text / 原文に根拠があるときは出典を示す
    """


class WorldModel(BaseModel):
    """
    World model (section 2): static, versioned per book; generated by the original-text extraction pipeline, published after human proofreading, read-only at runtime / 世界モデル（第 2 節）：静的で、本ごとにバージョン管理する。原文抽出パイプラインが生成し、人手で校正してから公開する。実行時は読み取り専用
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    schemaVersion: SchemaVersion
    worldModelVersion: str
    """
    Content version, e.g. "hashire-merosu@1.0.0" / 内容のバージョン。例："hashire-merosu@1.0.0"
    """
    book: Annotated[WorldModelBook, Field(title="WorldModelBook")]
    characters: list[Character]
    places: list[Place]
    facts: list[Fact]
    beats: list[Beat]
    causal: list[CausalEdge]
    anchors: list[FactId | BeatId]
    """
    Fact / beat IDs that cannot be overturned (anchors) / 覆せない fact / beat の ID（アンカー）
    """
    globalRules: list[WorldModelGlobalRulesItem]
    """
    The dead do not come back, no miracles, time does not run backwards, no modern objects, characters make their own decisions / 死者は生き返らない、奇跡は起きない、時間は巻き戻らない、現代の物はない、登場人物は自分で決める
    """
    clock: Clock
    stateVars: list[StateVar]
    roles: list[Role]
    """
    Roles the player can choose / プレイヤーが選べる身分
    """
    scenes: list[Scene]
    """
    3D scenes (S-001) / 3D シーン（S-001）
    """
    acts: list[Act]
    """
    Acts (S-004) / 幕（S-004）
    """
    endings: Annotated[WorldModelEndings, Field(title="WorldModelEndings")]
    pacing: dict[str, PacingAdditionalProperty] | None = None
    """
    Time-cost parameters (S-005, S-038); keys in 2.6.1; values are story minutes / 時間消費のパラメータ（S-005、S-038）。キーは 2.6.1 を参照。値は物語上の分
    """
    pacingNote: str | None = None
    """
    (1.1) Explanation of pacing (in Japanese) / （1.1）pacing の説明（日本語）
    """
    affordances: list[Affordance] | None = None
    """
    (1.1) Affordances (situational actions); see 2.10 / （1.1）状況アクション。2.10 を参照
    """
    items: list[Item] | None = None
    """
    (1.1) Items in the story; see 2.10 / （1.1）物語に登場するアイテム。2.10 を参照
    """
    setPieces: list[SetPiece] | None = None
    """
    (1.7, S-080 ④) Set pieces: narration (地の文) and pre-recorded lines attached to a beat or a player action; see 2.11 / （1.7、S-080 ④）固定演出：ビートやプレイヤーのアクションに結び付いた地の文と事前収録セリフ。2.11 を参照
    """
    objects: list[WorldObject] | None = None
    """
    (1.7) Things in a scene the player can 「調べる」 (inspect); see 2.12 / （1.7）シーン内で「調べる」ことができるもの。2.12 を参照
    """
    ruby: list[WorldModelRubyItem] | None = None
    """
    (1.10) Ruby glossary: readings of proper nouns and hard-to-read words in subtitles (frontend-design 7.5, UX 13), sent as is in the manifest. Omitted = none / （1.10）ルビ辞書：字幕に出る固有名詞や難読語の読み（frontend-design 7.5、UX 13）。manifest でそのまま配信する。省略 = なし
    """


ActPlan.model_rebuild()
Act.model_rebuild()
ActExit.model_rebuild()
Affordance.model_rebuild()
Beat.model_rebuild()
BeatVariant.model_rebuild()
Character.model_rebuild()
ClockOnDeadlineItem.model_rebuild()
EnRoute.model_rebuild()
