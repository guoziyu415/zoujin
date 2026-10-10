# 生成的文件，不要手改：改 packages/contracts/schemas/ 后跑 `uv run contracts-gen`。

from __future__ import annotations

from typing import Annotated, Any, Literal, TypeAliasType

from pydantic import BaseModel, ConfigDict, Field

type ActId = Annotated[str, Field(pattern="^act\\.[a-z0-9]+(?:[.-][a-z0-9]+)*$", title="ActId")]
"""
幕：`act.` 加小写 slug（可以有 `.` 和 `-`）
"""


type Activity = Annotated[
    Literal["idle", "walk", "run", "talk", "work", "sleep", "absent"],
    Field(title="Activity"),
]
"""
（1.1）人物此刻在做什么，同 api-contract 2.3；前端不认识的按 idle（2.4）
"""


type AffordanceId = Annotated[str, Field(pattern="^aff\\.[a-z0-9]+(?:[.-][a-z0-9]+)*$", title="AffordanceId")]
"""
情境动作（1.1）：`aff.` 加小写 slug（可以有 `.` 和 `-`）
"""


type AidId = Annotated[str, Field(pattern="^aid\\.[a-z0-9]+(?:[.-][a-z0-9]+)*$", title="AidId")]
"""
互助（1.1）：`aid.` 加小写 slug（可以有 `.` 和 `-`）
"""


type BeatId = Annotated[str, Field(pattern="^beat\\.[a-z0-9]+(?:[.-][a-z0-9]+)*$", title="BeatId")]
"""
节拍：`beat.` 加小写 slug（可以有 `.` 和 `-`）；节拍的变体也用这个前缀（`beat.25.v-no-doubt`）
"""


type Rank = Annotated[int, Field(ge=1)]
"""
受影响深浅，从 1 起；unchanged 时 null
"""


type CharacterId = Annotated[str, Field(pattern="^char\\.[a-z0-9]+(?:[.-][a-z0-9]+)*$", title="CharacterId")]
"""
人物：`char.` 加小写 slug（可以有 `.` 和 `-`）
"""


class CheckResult(BaseModel):
    """
    自检结果（第 3 节）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    status: Literal["passed", "rewritten", "downgraded", "rejected"]
    attempts: Annotated[int, Field(ge=1, le=3)]
    """
    共尝试几次（改写上限 2 次，即最多 3）
    """
    failedRules: list[
        Literal["R1-anchor", "R2-precondition", "R3-time", "R4-knowledge", "R5-persona", "R6-safety", "R7-capability"]
    ]
    reason: str | None = None
    """
    给「なぜこうなった？」和评审看的一句日语
    """
    checker: str
    """
    自检用的模型/规则版本
    """


class Cite(BaseModel):
    """
    原文出处，可以被机器校验（第 0 节）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    source: str
    """
    原文版本 ID，如 "aozora:1567_ruby_4948@sha256:2a437c047d7f"（对规范化全文求哈希）
    """
    para: Annotated[int, Field(ge=1)]
    """
    规范化文本里的段落号，从 1 开始
    """
    quote: Annotated[str, Field(max_length=80, min_length=1)]
    """
    原文片段，≤ 80 字。必须是该段的精确子串（跨字段的规矩，由 build_world 校验，不在 Schema 里）
    """


class ClockDeadlineEarliestArrivalCue(BaseModel):
    """
    （1.5，S-066 ①）本局第一次到下限时说一次的话
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


class ClockLabels(BaseModel):
    """
    tLabel 的生成规则
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    days: list[str]
    """
    下标 = Day（S-037）
    """
    bands: list[Band]
    """
    一天内的时段起点（分钟）和叫法，如 [1140,"日没"]；从 0 开始严格递增
    """
    format: str
    """
    （1.1）模板，含 {day} 和 {band}
    """
    inferred: Literal[True] = True
    note: str | None = None
    cite: list[Cite] | None = None
    """
    （1.1）时段叫法的原文依据
    """


type EdgeId = Annotated[str, Field(pattern="^edge\\.[a-z0-9]+(?:[.-][a-z0-9]+)*$", title="EdgeId")]
"""
因果边：`edge.` 加小写 slug（可以有 `.` 和 `-`）
"""


class EndingWorldContrast(BaseModel):
    """
    （1.1，S-026）「原作では…／あなたの世界では…」
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
    ≤ 40 字
    """


class EndingCard(BaseModel):
    """
    （1.1，S-049、S-051）结局卡，字数由这里保证。1.6 起每一局都生成：生成的结局取 rank 最前的 1〜3 人，一个也没排上名时放梅洛斯一句（按他的 original）；校验两次不过、改用模板尾声的局，字段取 ux-design 11.4 对应那一组的预写句子
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    title: Annotated[str, Field(max_length=14, min_length=1)]
    """
    称号 ≤ 14 字
    """
    subtitle: Annotated[str, Field(max_length=26, min_length=1)]
    """
    世界的去向 ≤ 26 字
    """
    contrast: Annotated[str, Field(max_length=48, min_length=1)]
    """
    「原作との違い」≤ 48 字
    """
    characterLines: Annotated[list[EndingCardCharacterLinesItem], Field(max_length=3, min_length=1)]
    """
    （1.6 起 1〜3 人）影响最深的 1〜3 人，一个也没排上名时是梅洛斯一句（卡片按最多 3 行排）
    """


class EndingShare(BaseModel):
    """
    生成产物的存储引用
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
结局：`end_` 加 ULID（26 位 Crockford base32，大写）
"""


type EventId = Annotated[str, Field(pattern="^ev_[0-7][0-9A-HJKMNP-TV-Z]{25}$", title="EventId")]
"""
事件：`ev_` 加 ULID（26 位 Crockford base32，大写）
"""


type ExitId = Annotated[str, Field(pattern="^exit\\.[a-z0-9]+(?:[.-][a-z0-9]+)*$", title="ExitId")]
"""
幕末去处：`exit.` 加小写 slug（可以有 `.` 和 `-`）
"""


type FactId = Annotated[str, Field(pattern="^fact\\.[a-z0-9]+(?:[.-][a-z0-9]+)*$", title="FactId")]
"""
事实：`fact.` 加小写 slug（可以有 `.` 和 `-`）
"""


type ItemId = Annotated[str, Field(pattern="^item\\.[a-z0-9]+(?:[.-][a-z0-9]+)*$", title="ItemId")]
"""
物品（1.1）：`item.` 加小写 slug（可以有 `.` 和 `-`）
"""


type MemoryId = Annotated[str, Field(pattern="^mem_[0-7][0-9A-HJKMNP-TV-Z]{25}$", title="MemoryId")]
"""
记忆：`mem_` 加 ULID（26 位 Crockford base32，大写）
"""


class PlaceCrossing(BaseModel):
    """
    有河的地点
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
地点：`place.` 加小写 slug（可以有 `.` 和 `-`）
"""


type PlaythroughId = Annotated[str, Field(pattern="^pt_[0-7][0-9A-HJKMNP-TV-Z]{25}$", title="PlaythroughId")]
"""
一局：`pt_` 加 ULID（26 位 Crockford base32，大写）
"""


type PromiseId = Annotated[str, Field(pattern="^prm_[0-7][0-9A-HJKMNP-TV-Z]{25}$", title="PromiseId")]
"""
约定（1.1）：`prm_` 加 ULID（26 位 Crockford base32，大写）
"""


type PromiseTemplateId = Annotated[
    str,
    Field(pattern="^promise\\.[a-z0-9]+(?:[.-][a-z0-9]+)*$", title="PromiseTemplateId"),
]
"""
约定模板（1.1）：`promise.` 加小写 slug（可以有 `.` 和 `-`）
"""


type RecordedAt = Annotated[
    str,
    Field(
        pattern="^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\\.[0-9]{1,9})?Z$",
        title="RecordedAt",
    ),
]
"""
真实时间，ISO 8601 UTC，以 Z 结尾（第 0 节）。只用于审计和分析，不参与故事逻辑。用 pattern 校验，不靠 format
"""


class Relationship(BaseModel):
    """
    关系，不单独存，按记忆推出（第 4 节）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    character: CharacterId
    trust: Annotated[int, Field(ge=-100, le=100)]
    """
    初值 + 未删除记忆的 trustDelta 之和，截断到 -100..100
    """
    label: str
    """
    由 trust 区间映射（第 4 节的表）
    """
    level: Literal[1, 2, 3, 4, 5]
    """
    （1.5）同一区间的档位，接口里叫 relationLevel
    """


type RoleId = Annotated[str, Field(pattern="^role\\.[a-z0-9]+(?:[.-][a-z0-9]+)*$", title="RoleId")]
"""
玩家身份：`role.` 加小写 slug（可以有 `.` 和 `-`）
"""


type RuleId = Annotated[str, Field(pattern="^rule\\.[a-z0-9]+(?:[.-][a-z0-9]+)*$", title="RuleId")]
"""
全局规则（globalRules）：`rule.` 加小写 slug（可以有 `.` 和 `-`）
"""


type RunFactId = Annotated[str, Field(pattern="^rf_[0-7][0-9A-HJKMNP-TV-Z]{25}$", title="RunFactId")]
"""
本局即兴设定（1.1）：`rf_` 加 ULID（26 位 Crockford base32，大写）
"""


type SceneId = Annotated[str, Field(pattern="^scene\\.[a-z0-9]+(?:[.-][a-z0-9]+)*$", title="SceneId")]
"""
3D 场景：`scene.` 加小写 slug（可以有 `.` 和 `-`）
"""


type SchemaVersion = Annotated[
    Literal["1.0", "1.1", "1.2", "1.3", "1.4", "1.5", "1.6", "1.7"],
    Field(title="SchemaVersion"),
]
"""
写入时的契约版本（第 0 节「版本」）。1.5 冻结，以后只做加法，每个新版本往这里加一个值。1.6：StateVar.valueRequires（C-16）、结局卡 1〜3 人。1.7：位置点（relocate 和 ActExit 的 spot、WorldState.spots）、Character.group、ActExit.arrival
"""


type SpotId = Annotated[str, Field(max_length=64, pattern="^[a-z0-9]+(?:[.-][a-z0-9]+)*$", title="SpotId")]
"""
（1.7）场景布局里的位置点（api-contract 第 0 节 spot，assets/scenes/<场景>/layout.json 的 spots），小写 slug，例 stake-front、way.castle。不带类型前缀：名字由前端在布局里定
"""


type StoryTime = Annotated[int, Field(ge=0, title="StoryTime")]
"""
故事时间 t：从 Day 0（约束之日）00:00 起算的故事分钟数（第 0 节）
"""


type TLabel = Annotated[str, Field(title="TLabel")]
"""
时间的说法，按世界模型的 clock.labels 生成，如「約束の日・夜」（第 0 节）
"""


type TurnId = Annotated[str, Field(pattern="^turn_[0-7][0-9A-HJKMNP-TV-Z]{25}$", title="TurnId")]
"""
一轮：`turn_` 加 ULID（26 位 Crockford base32，大写）
"""


type UtteranceId = Annotated[str, Field(pattern="^utt_[0-7][0-9A-HJKMNP-TV-Z]{25}$", title="UtteranceId")]
"""
一句话：`utt_` 加 ULID（26 位 Crockford base32，大写）
"""


type VarId = Annotated[str, Field(pattern="^var\\.[a-zA-Z0-9]+(?:[.-][a-zA-Z0-9]+)*$", title="VarId")]
"""
状态变量：`var.` 加 slug（可以有 `.` 和 `-`），段里可以用驼峰（`var.player.companionOf`、`var.player.knowsShortcut`、`var.melos.knowsTyranny`），第 0 节（1.6 写清）
"""


type WorldEndingId = Annotated[str, Field(pattern="^[a-z0-9]+(?:-[a-z0-9]+)*$", title="WorldEndingId")]
"""
世界结局的底线类 ID，不带前缀的小写短横线 slug，如 `canon-reunion`
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
    取得原文的日期
    """
    license: Literal["public-domain"] = "public-domain"


class WorldModelBook(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    id: str
    """
    如 "hashire-merosu"
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
    有原文依据时（1.4）
    """


PacingAdditionalProperty = TypeAliasType("PacingAdditionalProperty", Annotated[int, Field(ge=0)])


class ActStart(BaseModel):
    """
    本幕最早从什么时候开始
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
    这些节拍任一有了结果就收幕
    """
    atLatest: StoryTime
    """
    最迟在这个时间收幕
    """


class ActExitArrival(BaseModel):
    """
    （1.7）落地：第一行叙事和先开口的人物（ux/slice/jump-transition.md「落地」）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    line: Annotated[str, Field(min_length=1)]
    """
    落地后的第一行叙事（地の文，日语），跳转之后显示
    """
    opener: CharacterId | None = None
    """
    落地后先开口的人物：服务端发起一轮，台词按人设生成，不是问句
    """


type Actor = Annotated[Literal["player", "system", "narrator"] | CharacterId, Field(title="Actor")]
"""
事件是谁做的（不是谁写的，写入方永远是叙事者）：player 玩家，system 按时间表自然发生，narrator 只用于 correction，或人物 ID（第 0 节）
"""


class BeatWindow(BaseModel):
    """
    故事分钟；原著发生在 canonical；最晚 latest 之后就不可能再发生
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
    因果边（2.5）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    id: EdgeId
    from_: Annotated[BeatId | VarId, Field(alias="from")]
    """
    beat 或 stateVar
    """
    to: BeatId | VarId
    """
    beat 或 stateVar
    """
    type: Literal["enables", "requires", "prevents", "delays", "hastens"]
    timeLink: Literal["shift", "order"] | None = None
    """
    （1.1）只用于 enables / requires；默认 shift
    """
    minutes: Annotated[int | None, Field(ge=0)] = None
    """
    delays / hastens 必填：from 发生会让 to 推迟（提前）几分钟
    """
    note: str
    """
    为什么有这条边（日语）
    """
    cite: list[Cite] | None = None
    """
    原文能直接支持时给出处
    """
    inferred: bool
    """
    原文没明说、由人推断的为 true
    """


class CharacterKnowsItem(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    fact: FactId
    since: BeatId | Literal["pre"]
    """
    "pre" = 故事开始前就知道
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


class CharacterEndingYoursItem(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    sentence: Annotated[str, Field(min_length=1)]
    cites: Annotated[list[EventId], Field(min_length=1)]
    """
    至少引用一个本局事件
    """


class CharacterEnding(BaseModel):
    """
    （1.1）每个可对话人物的结局（第 5 节）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    character: CharacterId
    rank: Rank | None
    """
    受影响深浅，从 1 起；unchanged 时 null
    """
    unchanged: bool
    """
    玩家没碰过、世界变化也没波及到：只显示「原作どおり」，不生成句子
    """
    original: Annotated[str | None, Field(min_length=1)] = None
    """
    原作里他的结局，一句（日语）
    """
    yours: Annotated[list[CharacterEndingYoursItem] | None, Field(max_length=3, min_length=1)] = None
    """
    1〜3 句，「あなたの世界では」；unchanged 时省略
    """


class ClockDeadline(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    t: StoryTime
    label: str
    """
    如「三日目の日没」
    """
    cite: list[Cite]
    watchBeat: BeatId | None = None
    """
    （1.1）决定赶不赶得上的节拍
    """
    earliestArrival: StoryTime | None = None
    """
    （1.4，S-066）watchBeat 最早的时刻
    """
    earliestArrivalCue: Annotated[
        ClockDeadlineEarliestArrivalCue | None,
        Field(title="ClockDeadlineEarliestArrivalCue"),
    ] = None
    """
    （1.5，S-066 ①）本局第一次到下限时说一次的话
    """


class Condition(BaseModel):
    """
    条件：引用 stateVars（2.4）。节拍前提、变体、去处、情境动作、世界结局共用
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
    原文没写、为游戏设计的前提的说明
    """


class DesignLine(BaseModel):
    """
    （1.4）原文没有、为游戏写的示例台词（2.1）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    text: str
    """
    日语一句。角色提示里和 sampleLines 一样当示例用，不逐字照念
    """
    since: BeatId | None = None
    """
    从该节拍发生起才用（1.1）
    """
    until: BeatId | None = None
    """
    该节拍发生后不再用（1.1）
    """
    when: list[Condition] | None = None
    """
    此刻的 WorldState 满足这些条件才用（1.4）；since / until / when 同时写时三者都要满足
    """
    inferred: Literal[True] = True
    note: str | None = None
    """
    什么场合说
    """
    cite: list[Cite] | None = None
    """
    依据的原文
    """


class EffectHold(BaseModel):
    """
    （1.3）物品换手；只用于 portable 的物品
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    op: Literal["hold"] = "hold"
    item: ItemId
    to: Literal["player"] | CharacterId | None
    """
    新的持有者；null = 被拿走、用掉
    """
    from_: Annotated[Literal["player"] | CharacterId | None, Field(alias="from")] = None


class EffectImprov(BaseModel):
    """
    （1.1）即兴设定（S-030 ②），见 3.1 的 RunFact
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
    某角色知道了某事实；（1.1）fact 也可以是 rf_…（别人的即兴设定）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    op: Literal["learn"] = "learn"
    character: CharacterId
    fact: FactId | RunFactId


class EffectPromiseDue(BaseModel):
    """
    期限（时刻或节拍）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    t: StoryTime | None = None
    beat: BeatId | None = None


class EffectPromise(BaseModel):
    """
    （1.1）约定，见 3.1 的 Promise
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    op: Literal["promise"] = "promise"
    promiseId: PromiseId | None = None
    """
    可选（1.6 契约第 3 节写清）：世界模型的效果模板（2.10）和候选事件（evals/s2/README.md）不写，提交时由叙事者分配 prm_…。提交的事件另外要求必带（Event.effects）
    """
    change: Literal["made", "kept", "broken", "voided"]
    from_: Annotated[Literal["player"] | CharacterId | None, Field(alias="from")] = None
    """
    change = made 时必填
    """
    to: Literal["player"] | CharacterId | None = None
    """
    change = made 时必填
    """
    text: str | None = None
    """
    change = made 时必填
    """
    due: Annotated[EffectPromiseDue | None, Field(title="EffectPromiseDue")] = None
    """
    期限（时刻或节拍）
    """
    template: PromiseTemplateId | None = None
    """
    模板 ID（可选）
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
    （1.7）站在这个地点的哪个位置点；省略 = 由后端按布局的站位规则排（第 3.1 节 WorldState.spots）
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
    （1.1，S-031 ①）这一局生成的世界结局；没有 = 就是底线类本身
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    id: Annotated[str, Field(min_length=1)]
    """
    本局内唯一，如 "gen.king-abdicates"（API 的 outcomeId）
    """
    title: Annotated[str, Field(min_length=1)]
    summary: Annotated[str, Field(min_length=1)]
    claims: list[EndingWorldVariantClaimsItem]
    """
    它主张的最终状态，必须和 finalVars 一致
    """
    causedBy: Annotated[list[EventId], Field(min_length=2)]
    """
    至少 2 个本局事件（「讲得通」）
    """


class EndingWorld(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    outcome: WorldEndingId
    """
    WorldModel.endings.world[].id（底线类）
    """
    summary: Annotated[str, Field(min_length=1)]
    """
    日语
    """
    changedBeats: list[EndingWorldChangedBeatsItem]
    """
    和原著不同的节拍，各自指回事件
    """
    finalVars: dict[VarId, Any]
    title: Annotated[str | None, Field(min_length=1)] = None
    """
    （1.1）世界结局的一句标题。1.6 起必写：模板尾声的局写世界模型 endings.world 里这一类的 label（api-contract 2.8 的 world.title）
    """
    variant: Annotated[EndingWorldVariant | None, Field(title="EndingWorldVariant")] = None
    """
    （1.1，S-031 ①）这一局生成的世界结局；没有 = 就是底线类本身
    """
    signature: dict[VarId | BeatId, Any] | None = None
    """
    （1.1）按 endings.signature 算出的署名（2.9.1）：变量 → 最终值，节拍 → 是否照原著发生
    """
    contrast: Annotated[EndingWorldContrast | None, Field(title="EndingWorldContrast")] = None
    """
    （1.1，S-026）「原作では…／あなたの世界では…」
    """


class EndingPlayerFate(BaseModel):
    """
    顾问、人质、同行者、目击者、被处刑…
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
    初值 + 未删除记忆的 trustDelta 之和，截断到 -100..100
    """
    label: Annotated[str, Field(min_length=1)]
    line: Annotated[str | None, Field(min_length=1)] = None
    memoryIds: list[MemoryId]


class EndingPlayerTitle(BaseModel):
    """
    如「王に信を説いた旅人」
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
    至少引用一个本局事件
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
    （1.1）结局演出里在场的人物（S-053）
    """


class EndingPlayerDidForYouItem(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    sentence: Annotated[str, Field(min_length=1)]
    cites: Annotated[list[EventId], Field(min_length=1)]
    """
    至少引用一个本局事件
    """


class EndingPlayerYouDidItem(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    sentence: Annotated[str, Field(min_length=1)]
    cites: Annotated[list[EventId], Field(min_length=1)]
    """
    至少引用一个本局事件
    """


class EndingPlayer(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    fate: Annotated[EndingPlayerFate, Field(title="EndingPlayerFate")]
    """
    顾问、人质、同行者、目击者、被处刑…
    """
    relationships: list[EndingPlayerRelationshipsItem]
    title: Annotated[EndingPlayerTitle, Field(title="EndingPlayerTitle")]
    """
    如「王に信を説いた旅人」
    """
    epilogue: list[EndingPlayerEpilogueItem]
    """
    每句至少引用一个事件
    """
    lastScene: Annotated[EndingPlayerLastScene, Field(title="EndingPlayerLastScene")]
    didForYou: list[EndingPlayerDidForYouItem] | None = None
    """
    （1.1，D-012）人物为你做的事
    """
    youDid: list[EndingPlayerYouDidItem] | None = None
    """
    （1.1）你为人物做的事
    """


class Ending(BaseModel):
    """
    结局（第 5 节）。1.6 起写入的结局，world.title、player.didForYou / youDid（可以是空数组）、characters、card 必写
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
    story-closed = 最后一幕的收幕节拍有了结果
    """
    t: StoryTime
    decidedAt: RecordedAt
    world: Annotated[EndingWorld, Field(title="EndingWorld")]
    player: Annotated[EndingPlayer, Field(title="EndingPlayer")]
    characters: list[CharacterEnding] | None = None
    """
    （1.1，D-015、S-032）7 个可对话人物都在
    """
    card: Annotated[EndingCard | None, Field(title="EndingCard")] = None
    """
    （1.1，S-049、S-051）结局卡，字数由这里保证。1.6 起每一局都生成：生成的结局取 rank 最前的 1〜3 人，一个也没排上名时放梅洛斯一句（按他的 original）；校验两次不过、改用模板尾声的局，字段取 ux-design 11.4 对应那一组的预写句子
    """
    share: Annotated[EndingShare | None, Field(title="EndingShare")] = None
    """
    生成产物的存储引用
    """


class EndingSignature(BaseModel):
    """
    （1.1）结局署名：什么叫「世界结局实质不同」（2.9.1）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    vars: list[VarId]
    """
    这些变量的最终值
    """
    beats: list[BeatId]
    """
    这些节拍是否照原著发生
    """
    inferred: Literal[True] = True
    note: str | None = None


class EventPlan(BaseModel):
    """
    （1.2，S-031 ③）只用于 type=act-transition（actor=player）且玩家说出了自己的打算
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    label: str
    """
    叙事者的日语转述；不逐字引用玩家原话
    """
    toAct: ActId
    place: PlaceId
    t: StoryTime
    """
    不早于 Act.start.t
    """
    with_: Annotated[list[CharacterId] | None, Field(alias="with")] = None
    """
    同行的人物
    """


class Fact(BaseModel):
    """
    事实（2.3）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    id: FactId
    statement: str
    """
    中性陈述（日语）
    """
    trueFrom: BeatId | Literal["pre"]
    """
    从哪个 beat 起成立；"pre" = 开场前已成立
    """
    visibility: Literal["public", "private"]
    """
    public：在场的人都会知道；private：只有 knows 里的人知道
    """
    spoilerTerms: list[str] | None = None
    """
    说出这个事实时常用的词和别名（日语）
    """
    cite: list[Cite]


class Item(BaseModel):
    """
    （1.1）故事里的物品（2.10）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    id: ItemId
    name: str
    """
    日语
    """
    at: list[PlaceId]
    """
    在这些地点随手可得；能带在身上的物品写 []
    """
    portable: Literal[True] | None = None
    """
    （1.3）一件实物：同一时刻只在一个人手里
    """
    inferred: Literal[True] = True
    note: str | None = None
    cite: list[Cite] | None = None


class MemoryItem(BaseModel):
    """
    角色对玩家的记忆，可删除（第 4 节）。只由已提交的事件生成
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
    谁记得
    """
    kind: Literal["promise", "help", "harm", "shared-moment", "claim", "impression"]
    text: str
    """
    角色视角的一句日语，給記憶帳显示；不含现实个人信息；删除后清空
    """
    fromEvents: Annotated[list[EventId], Field(min_length=1)]
    """
    来自哪些事件；记忆只由已提交的事件生成（第 4 节），所以至少一个
    """
    t: StoryTime
    trustDelta: Annotated[int, Field(ge=-20, le=20)]
    """
    这条记忆对信任的影响，-20..+20
    """
    salience: Annotated[float, Field(ge=0.0, le=1.0)]
    """
    0..1，检索排序用
    """
    via: Literal["witnessed", "told", "rumor"] | None = None
    """
    （1.1）見た / 聞いた / 噂で
    """
    promiseId: PromiseId | None = None
    """
    （1.1）这条记忆属于哪个约定
    """
    createdAt: RecordedAt
    deletedAt: RecordedAt | None = None
    """
    删除后：text 清空，只留 ID 和删除时间（审计用）
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
    地点（2.2）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    id: PlaceId
    name: str
    description: str
    adjacent: list[PlaceAdjacentItem]
    """
    步行分钟；跑步等节奏由叙事者按系数换算
    """
    crossing: Annotated[PlaceCrossing | None, Field(title="PlaceCrossing")] = None
    """
    有河的地点
    """
    sceneRef: SceneId | None
    """
    对应的 3D 场景；null = 第一版没有场景
    """
    inferred: bool | None = None
    """
    原文没有这个场景、为游戏设计的地点
    """
    note: str | None = None
    cite: list[Cite]


class Playthrough(BaseModel):
    """
    一局游戏（第 1 节）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    schemaVersion: SchemaVersion
    playthroughId: PlaythroughId
    userRef: str
    """
    邀请码账号的匿名 ID（S-020），不是邮箱、不是姓名
    """
    worldModelVersion: str
    """
    开局时锁定，整局不变
    """
    roleId: RoleId
    """
    玩家选的身份
    """
    playerAlias: str | None = None
    """
    S-010：默认不填，第一版没有任何界面入口
    """
    ageBand: Literal["under13", "13to17", "18plus", "unknown"] | None = None
    """
    S-010：默认不收集
    """
    status: Literal["active", "ended", "abandoned", "deleted"]
    startedAt: RecordedAt
    endedAt: RecordedAt | None = None
    lastActiveAt: RecordedAt
    """
    最后一次有玩家操作的真实时间；默认保留期按它算
    """
    lastSeq: Annotated[int, Field(ge=0)]
    """
    最后一个事件的序号
    """


class PromiseTemplate(BaseModel):
    """
    （1.1）这个人物常见的约定；叙事者写 promise 效果时引用（2.1）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    id: PromiseTemplateId
    by: Literal["player"] | CharacterId
    """
    谁许下的；另一方是模板所属的人物（by 是人物自己时，另一方是玩家）
    """
    text: str
    """
    约定的内容（日语），如「必ず戻る」
    """
    inferred: Literal[True] | None = None
    cite: list[Cite] | None = None
    note: str | None = None
    """
    （1.4）语气、什么场合
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
    玩家身份（2.7）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    id: RoleId
    name: str
    release: Annotated[int, Field(ge=1)]
    """
    第几版开放
    """
    startAct: ActId
    startPlace: PlaceId
    startT: StoryTime
    knownCharacters: list[CharacterId]
    """
    一开始认识谁（这些角色开局信任 +10）
    """
    access: list[PlaceId]
    """
    能自由进出的地点
    """
    conditionalAccess: list[RoleConditionalAccessItem] | None = None
    """
    （1.1）条件满足时也能进
    """
    initialKnowledge: list[FactId]
    """
    身份自带知道的 fact
    """
    items: list[ItemId] | None = None
    """
    （1.3）开局带在身上的物品
    """
    inferred: Literal[True] = True
    note: str | None = None


class RunFact(BaseModel):
    """
    （1.1）本局即兴设定（3.1）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    factId: RunFactId
    character: CharacterId
    """
    谁说的（归属于谁）
    """
    statement: str
    """
    一句中性日语
    """
    madeBy: EventId
    """
    记下它的事件
    """


class Scene(BaseModel):
    """
    3D 场景（2.2）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    id: SceneId
    """
    ID 由前端提出（frontend-design 8.1）
    """
    name: str
    release: Annotated[int, Field(ge=1)]
    """
    第几版做
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
    这个变量的一个取值（enum 在 values 里，其余合类型）
    """
    when: Annotated[list[Condition], Field(min_length=1)]
    """
    全部成立才能改成 value；和节拍前提同一个 Condition 和求值函数
    """
    note: Annotated[str, Field(min_length=1)]
    """
    为什么有这个条件（日语）；不成立时叙事者的 reason 带上变量、value 和它
    """
    inferred: Literal[True] = True
    cite: list[Cite] | None = None


class StateVar(BaseModel):
    """
    状态变量（2.6）
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
    var.player.location、var.act.current 的初值由身份决定
    """
    keyMoment: bool | None = None
    """
    决定结局的变量
    """
    visibleToPlayer: bool | None = None
    """
    变化能不能显示给玩家；默认 false
    """
    valueLabels: dict[str, str] | None = None
    """
    取值 → 一句可直接显示的日语
    """
    valueRequires: list[StateVarValueRequiresItem] | None = None
    """
    （1.6，C-16）把变量改成某个值时要满足的条件（2.6）。① 只管叙事者提交的事件，到点的节拍和期限（origin = schedule）不判，节拍的结果由节拍前提管；② 值真的变了才判，设成现在的值不判；③ 按这个 effect 之前的状态判，同一事件里前面的 effect 已生效；④ when 不成立报 R2；⑤ 设好以后条件不再成立不自动改回、不算违规
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
    （1.1）约定，由 promise 效果推出，不单独写（3.1）。生成的代码里叫 StoryPromise，避开 JS 的 Promise
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    promiseId: PromiseId
    from_: Annotated[Literal["player"] | CharacterId, Field(alias="from")]
    """
    许下的一方
    """
    to: Literal["player"] | CharacterId
    """
    对方
    """
    text: str
    """
    约定的内容（日语，中性，不是原话）
    """
    due: Annotated[StoryPromiseDue | None, Field(title="StoryPromiseDue")] = None
    template: PromiseTemplateId | None = None
    status: Literal["open", "kept", "broken", "voided"]
    """
    まだ / 果たされた / 破られた / 作废
    """
    madeBy: EventId
    """
    成立的事件
    """
    resolvedBy: EventId | None = None
    """
    兑现、违背或作废的事件
    """


class Utterance(BaseModel):
    """
    玩家和角色的原话，单独存放，可删除（第 3 节）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    utteranceId: UtteranceId
    playthroughId: PlaythroughId
    turnId: TurnId
    """
    記憶帳删除时按轮清空（第 4 节）
    """
    speaker: Literal["player"] | CharacterId
    text: str
    """
    识别后的文字（不存音频）；删除后清空
    """
    t: StoryTime
    recordedAt: RecordedAt
    deletedAt: RecordedAt | None = None
    """
    删除后 text 清空
    """


class WorldEnding(BaseModel):
    """
    世界结局的底线分类（2.9，S-007）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    id: WorldEndingId
    """
    写进 Ending.world.outcome
    """
    order: Annotated[int, Field(ge=1)]
    """
    判定顺序：从 1 开始，第一个条件全满足的就是本局的世界结局
    """
    label: str
    """
    日语，结局卡上显示
    """
    when: list[Condition]
    """
    按结局时的 WorldState 判断
    """
    inferred: Literal[True] = True
    note: str | None = None


class WorldModelEndings(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    world: list[WorldEnding]
    """
    世界结局的底线分类（S-007、S-034）
    """
    signature: EndingSignature | None = None
    """
    （1.1）什么叫「结局实质不同」，见 2.9.1
    """


class WorldState(BaseModel):
    """
    由事件推出的当前状态，不是第二份事实（3.1）：世界模型初值 + 按 seq 依次应用全部事件的 effects
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    playthroughId: PlaythroughId
    asOfSeq: Annotated[int, Field(ge=0)]
    """
    推导到第几个事件
    """
    t: StoryTime
    """
    时钟 = 所有事件 max(t + dt)
    """
    vars: dict[VarId, Any]
    """
    所有 stateVar 的当前值
    """
    beats: dict[BeatId, Literal["pending", "happened", "prevented", "delayed", "hastened", "altered"]]
    schedule: dict[BeatId, StoryTime]
    """
    还没结果的节拍的本局排定时间（2.5.1）
    """
    knowledge: dict[CharacterId, list[FactId | RunFactId]]
    """
    角色 → 运行时新学到的 fact
    """
    locations: dict[CharacterId, PlaceId]
    """
    角色 → 地点
    """
    spots: dict[CharacterId, SpotId] | None = None
    """
    （1.7）角色 → 指定的位置点：relocate 写了 spot 才有；换到别的地点时去掉。没有的由后端按布局的站位规则排（第 3.1 节）
    """
    promises: dict[PromiseId, StoryPromise] | None = None
    """
    （1.1）promiseId → 约定
    """
    runFacts: dict[RunFactId, RunFact] | None = None
    """
    （1.1）factId → 即兴设定
    """
    holdings: dict[ItemId, Literal["player"] | CharacterId | None] | None = None
    """
    （1.3）portable 物品 → 现在谁拿着
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
    从该节拍发生起才用（1.1）
    """
    until: BeatId | None = None
    """
    该节拍发生后不再用（1.1）
    """
    when: list[Condition] | None = None
    """
    此刻的 WorldState 满足这些条件才用（1.4）；since / until / when 同时写时三者都要满足
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
    从该节拍发生起才用（1.1）
    """
    until: BeatId | None = None
    """
    该节拍发生后不再用（1.1）
    """
    when: list[Condition] | None = None
    """
    此刻的 WorldState 满足这些条件才用（1.4）；since / until / when 同时写时三者都要满足
    """


class CharacterSpeechSampleLinesItem(BaseModel):
    """
    原文台词，直接引用。契约写作 Cite & { since?, until?, when? }：这里写成关死的普通对象，source / para / quote 用 JSON 指针引 Cite 的字段（约束只有一份），不用 allOf，生成的类型也是关死的
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    source: str
    """
    原文版本 ID，如 "aozora:1567_ruby_4948@sha256:2a437c047d7f"（对规范化全文求哈希）
    """
    para: Annotated[int, Field(ge=1)]
    """
    规范化文本里的段落号，从 1 开始
    """
    quote: Annotated[str, Field(max_length=80, min_length=1)]
    """
    原文片段，≤ 80 字。必须是该段的精确子串（跨字段的规矩，由 build_world 校验，不在 Schema 里）
    """
    since: BeatId | None = None
    """
    从该节拍发生起才用（1.1）
    """
    until: BeatId | None = None
    """
    该节拍发生后不再用（1.1）
    """
    when: list[Condition] | None = None
    """
    此刻的 WorldState 满足这些条件才用（1.4）；since / until / when 同时写时三者都要满足
    """


class CharacterSpeech(BaseModel):
    """
    说话方式，给角色 Agent 和评测用
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    firstPerson: str | None = None
    """
    「私」「わし」…
    """
    register_: Annotated[str, Field(alias="register")]
    sampleLines: list[CharacterSpeechSampleLinesItem]
    """
    原文台词，直接引用
    """
    designLines: list[DesignLine] | None = None
    """
    （1.4）原文没有、为游戏写的示例台词
    """


class Act(BaseModel):
    """
    幕（2.8，S-004）
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
    本幕最早从什么时候开始
    """
    end: Annotated[ActEnd, Field(title="ActEnd")]
    scenes: list[SceneId]
    """
    本幕可能用到的场景（前端据此预加载）
    """
    exits: list[ActExit]
    """
    幕末去处；最后一幕为空，收幕即进入结局
    """
    inferred: Literal[True] = True
    note: str | None = None


class ActExit(BaseModel):
    """
    幕末推荐去处（2.8）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    id: ExitId
    label: str
    """
    玩家看到的选项（日语）
    """
    toAct: ActId
    place: PlaceId
    """
    下一幕的起点
    """
    t: StoryTime
    """
    下一幕从几点开始
    """
    alignTo: BeatId | None = None
    """
    跟着某个节拍走：该节拍本局被推迟/提前多少，t 就平移多少
    """
    roles: list[RoleId] | None = None
    """
    只对这些身份开放；省略 = 全部
    """
    requires: list[Condition] | None = None
    """
    收幕时的状态要满足
    """
    effects: list[Effect]
    """
    选择本身的效果
    """
    enRoute: EnRoute | None = None
    """
    （1.4）跳过的这段路上有一个能改的节拍时，过场页给一个二选一
    """
    spot: SpotId | None = None
    """
    （1.7）玩家落在 place 的哪个位置点；省略 = 前端按这个地点的起点（layout.json 的 startSpots）
    """
    arrival: Annotated[ActExitArrival | None, Field(title="ActExitArrival")] = None
    """
    （1.7）落地：第一行叙事和先开口的人物（ux/slice/jump-transition.md「落地」）
    """


class Affordance(BaseModel):
    """
    （1.1）情境动作（2.10）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    id: AffordanceId
    kind: Literal["examine", "give", "follow", "block", "help", "wait", "go", "shortcut", "run-together", "hasten"]
    label: str
    """
    按钮上的动词短语（日语），不写耗时
    """
    place: PlaceId
    """
    在哪个地点出现
    """
    act: ActId | None = None
    """
    只在这一幕
    """
    roles: list[RoleId] | None = None
    """
    只对这些身份；省略 = 全部
    """
    target: CharacterId | None = None
    """
    对象人物
    """
    item: ItemId | None = None
    """
    kind = give 时必填：交出的物品
    """
    minutes: Annotated[int, Field(ge=0)]
    """
    玩家花的故事时间（= 事件的 dt）
    """
    melos: Literal["delay", "hasten"] | None = None
    """
    第四幕对梅洛斯的影响
    """
    melosMinutes: int | None = None
    """
    （1.4）有 melos 时必填：梅洛斯到刑场会晚（+）或早（−）几分钟
    """
    when: list[Condition] | None = None
    """
    出现条件
    """
    aid: AidId | None = None
    """
    做成了就兑现这条互助（fromYou 的 MutualAid.id）
    """
    effects: list[Effect]
    """
    效果模板：判定通过时提交的效果；空 = 只影响关系
    """
    inferred: Literal[True] = True
    note: str | None = None
    cite: list[Cite] | None = None


class Beat(BaseModel):
    """
    情节节拍（2.4）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    id: BeatId
    order: float
    """
    原著顺序（可以有小数，插在两个节拍之间）
    """
    title: str
    summary: str
    window: Annotated[BeatWindow, Field(title="BeatWindow")]
    """
    故事分钟；原著发生在 canonical；最晚 latest 之后就不可能再发生
    """
    place: PlaceId
    participants: list[CharacterId]
    kind: Literal["anchor", "mutable"]
    """
    anchor：不能被阻止或改写；mutable：可被提前、推迟、阻止或改变结果
    """
    preconditions: list[Condition]
    """
    发生前提，引用 stateVars
    """
    outcomes: list[Effect]
    """
    原著里发生后对状态的影响
    """
    activities: list[BeatActivitiesItem] | None = None
    """
    （1.1）节拍发生后这个人物在做什么
    """
    variants: list[BeatVariant] | None = None
    """
    （1.4）到点发生时，按这一局的状态换成另一种演法
    """
    cite: list[Cite]


class BeatVariant(BaseModel):
    """
    （1.4，S-064）节拍到点发生时按这一局的状态换的另一种演法（2.4）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    id: BeatId
    """
    如 "beat.25.v-no-doubt"
    """
    when: list[Condition]
    """
    节拍到点、前提成立时，按顺序取第一个 when 全满足的变体
    """
    summary: str
    """
    这一局的演法（日语）
    """
    outcomes: list[Effect]
    """
    代替节拍的 outcomes
    """
    inferred: Literal[True] = True
    note: str | None = None
    cite: list[Cite] | None = None


class Character(BaseModel):
    """
    人物（2.1）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    id: CharacterId
    name: str
    reading: str | None = None
    summary: str
    """
    一两句，中性描述
    """
    traits: list[CharacterTraitsItem]
    """
    性格，每条有出处
    """
    goals: list[CharacterGoalsItem]
    """
    动机（= S-030 的「当下目标」）
    """
    speech: Annotated[CharacterSpeech, Field(title="CharacterSpeech")]
    """
    说话方式，给角色 Agent 和评测用
    """
    knows: list[CharacterKnowsItem]
    """
    知道哪个 fact，从哪个 beat 起
    """
    initialPlace: PlaceId
    talkable: bool
    """
    第一版能不能自由对话（S-003）
    """
    group: Literal[True] | None = None
    """
    （1.7）一群人（群众、警吏、山贼、一团旅人）：不占布局的位置点，前端按地点成群地放（站位规则见第 3.1 节 WorldState.spots）
    """
    voiceRef: str | None = None
    """
    声音配置的引用，具体值由后端/UX 管
    """
    initialActivity: Activity | None = None
    """
    （1.1）开局在做什么（默认 idle）
    """
    items: list[ItemId] | None = None
    """
    （1.3）开局带在身上的物品（portable 的 Item ID）
    """
    cite: list[Cite]
    mutualAid: list[MutualAid] | None = None
    """
    （1.1）互助：他能为你做的、你能为他做的
    """
    promiseTemplates: list[PromiseTemplate] | None = None
    """
    （1.1）这个人物常见的约定
    """
    plans: list[CharacterPlansItem] | None = None
    """
    （1.1）每一幕「没人管时的打算」
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
    时钟：开局时间、期限、时段叫法（2.6）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    startT: StoryTime
    """
    默认开局时间（各身份见 Role.startT）
    """
    deadline: Annotated[ClockDeadline, Field(title="ClockDeadline")]
    sunsetMinuteOfDay: Annotated[int, Field(ge=0, le=1439)]
    """
    日没是几点；默认 1140（19:00）
    """
    onDeadline: list[ClockOnDeadlineItem]
    """
    到期限时自动执行（actor: "system"）；所有 if 都按期限那一刻的状态判断
    """
    labels: Annotated[ClockLabels, Field(title="ClockLabels")]
    """
    tLabel 的生成规则
    """


type Effect = Annotated[
    EffectSet | EffectInc | EffectBeat | EffectLearn | EffectRelocate | EffectPromise | EffectImprov | EffectHold,
    Field(discriminator="op", title="Effect"),
]
"""
效果：按 op 区分的 8 种（第 3 节）。事件、节拍结果、去处、情境动作、互助、期限规则共用
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
    altered 时 = 改变后的结果（代替世界模型里的 outcomes）
    """
    note: str | None = None


class EnRoute(BaseModel):
    """
    （1.4）过场里的二选一（2.8）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    beat: BeatId
    """
    跳过的这段里能改的节拍
    """
    line: str
    """
    过场页上叙事的一句（日语）
    """
    choices: Annotated[list[EnRouteChoice], Field(max_length=2, min_length=2)]
    """
    正好两个；最后一个是「照原作」，effects 为空
    """
    inferred: Literal[True] = True
    note: str | None = None
    cite: list[Cite] | None = None


class EnRouteChoice(BaseModel):
    """
    （1.5）过场二选一的一个选项（2.8）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    label: str
    """
    按钮上的动词（日语），不写分钟数
    """
    effects: list[Effect]
    melosMinutes: int | None = None
    """
    （1.5）effects 里有改节拍的一条时必填：梅洛斯到刑场早（−）晚（+）几分钟
    """
    after: str | None = None
    """
    （1.5）选了这一项，进下一幕之前过场页再多一句（日语）
    """


class Event(BaseModel):
    """
    运行时事件，只追加（第 3 节）。叙事者是唯一写入方
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
    本局内严格递增，从 1 开始；重放按 seq
    """
    turnId: TurnId | None = None
    """
    来自哪一轮；system 事件没有
    """
    idempotencyKey: Annotated[str, Field(min_length=1)]
    """
    同一轮提交重试时不重复写（后端生成，靠它去重，不能是空串）
    """
    worldModelVersion: str
    t: StoryTime
    """
    发生时的故事时间；按 seq 不递减
    """
    dt: Annotated[int, Field(ge=0)]
    """
    这件事消耗的故事分钟；本事件之后时钟 = max(之前的时钟, t + dt)
    """
    recordedAt: RecordedAt
    actor: Actor
    type: Literal["say", "action", "move", "beat", "learn", "act-transition", "correction", "ending", "forget"]
    origin: Literal["turn", "action", "schedule", "plan", "director", "act", "memory"] | None = None
    """
    （1.1）事件从哪来；只给评测、Trace 和「その頃」排序，不推前端
    """
    beneficiary: Literal["player"] | CharacterId | None = None
    """
    （1.1）这件事是为谁做的
    """
    confirmed: Literal[True] | None = None
    """
    （1.1）提交前经过故事里的意图确认（S-040）
    """
    place: PlaceId
    summary: str
    """
    叙事者写的中性日语摘要：只写故事里的行为，不含玩家原话，不含现实个人信息
    """
    utteranceRefs: list[UtteranceId] | None = None
    """
    相关原话（可删除；删除后这里保留 ID 但内容取不到）
    """
    causes: list[EventId | BeatId]
    """
    因为哪些事件（ev_…）或节拍（beat.…）
    """
    effects: list[Effect]
    """
    提交的事件里 promise 效果必须带 promiseId（见 Effect 的 promise 分支）
    """
    keyMoment: bool
    """
    提交时算出，（1.1）按 S-041 的四条
    """
    check: CheckResult
    supersedes: EventId | None = None
    """
    只用于 type=correction：修正哪一条事件
    """
    exitId: ExitId | None = None
    """
    只用于 type=act-transition（actor=player）和过场二选一的 action 事件
    """
    plan: Annotated[EventPlan | None, Field(title="EventPlan")] = None
    """
    （1.2，S-031 ③）只用于 type=act-transition（actor=player）且玩家说出了自己的打算
    """


class MutualAid(BaseModel):
    """
    （1.1）互助：他能为你做的、你能为他做的（2.1）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    id: AidId
    direction: Literal["forYou", "fromYou"]
    """
    forYou = 他能为你做的；fromYou = 你能为他做的
    """
    text: str
    """
    日语一句，给叙事者和角色提示用，不直接显示给玩家
    """
    when: list[Condition] | None = None
    """
    只在这些条件下才可能
    """
    opening: RoleId | None = None
    """
    这一条是该身份第一幕的「开局互助」（S-048）
    """
    major: Literal[True] | None = None
    """
    只用于 forYou：兑现时算关键时刻（S-041）
    """
    gives: ItemId | None = None
    """
    （1.3）只用于 forYou：兑现时人物交给你的物品
    """
    effects: list[Effect] | None = None
    """
    （1.4）兑现时提交的效果模板（同 Affordance.effects）
    """
    inferred: Literal[True] = True
    cite: list[Cite] | None = None
    """
    有原文依据时给出处
    """


class WorldModel(BaseModel):
    """
    世界模型（第 2 节）：静态、按书版本化；由原文抽取流水线生成，人工校对后发布，运行时只读
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    schemaVersion: SchemaVersion
    worldModelVersion: str
    """
    内容版本，如 "hashire-merosu@1.0.0"
    """
    book: Annotated[WorldModelBook, Field(title="WorldModelBook")]
    characters: list[Character]
    places: list[Place]
    facts: list[Fact]
    beats: list[Beat]
    causal: list[CausalEdge]
    anchors: list[FactId | BeatId]
    """
    不能被推翻的 fact / beat ID（锚点）
    """
    globalRules: list[WorldModelGlobalRulesItem]
    """
    死者不复活、没有奇迹、时间不倒流、没有现代物品、人物自己做决定
    """
    clock: Clock
    stateVars: list[StateVar]
    roles: list[Role]
    """
    玩家可选身份
    """
    scenes: list[Scene]
    """
    3D 场景（S-001）
    """
    acts: list[Act]
    """
    幕（S-004）
    """
    endings: Annotated[WorldModelEndings, Field(title="WorldModelEndings")]
    pacing: dict[str, PacingAdditionalProperty] | None = None
    """
    时间消耗参数（S-005、S-038），键见 2.6.1；值是故事分钟
    """
    pacingNote: str | None = None
    """
    （1.1）pacing 的说明（日语）
    """
    affordances: list[Affordance] | None = None
    """
    （1.1）情境动作，见 2.10
    """
    items: list[Item] | None = None
    """
    （1.1）故事里的物品，见 2.10
    """


Act.model_rebuild()
ActExit.model_rebuild()
Affordance.model_rebuild()
Beat.model_rebuild()
BeatVariant.model_rebuild()
Character.model_rebuild()
ClockOnDeadlineItem.model_rebuild()
EnRoute.model_rebuild()
