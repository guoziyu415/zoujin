# 生成的文件，不要手改：改 packages/contracts/schemas/ 后跑 `uv run contracts-gen`。

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from zoujin_contracts.generated.data import (
    ActId,
    Activity,
    Actor,
    BeatId,
    CharacterEnding,
    CharacterId,
    EndingId,
    Event,
    EventId,
    ExitId,
    ItemId,
    MemoryId,
    PlaceId,
    PlaythroughId,
    PromiseId,
    RecordedAt,
    RoleId,
    SceneId,
    StoryTime,
    TLabel,
    TurnId,
    VarId,
)

type RecapLine = Annotated[str, Field(min_length=1)]


type Because = Annotated[str, Field(min_length=1)]
"""
条件出现的理由，如「王があなたを覚えている」
"""


type NarrationItem = Annotated[str, Field(min_length=1)]


type ActionId = Annotated[str, Field(max_length=128, min_length=1, title="ActionId")]
"""
快照里情境动作的 ID（2.3），例 act_help_old-man_cart；服务端生成，前端原样回传
"""


class ActionMessageParams(BaseModel):
    """
    give 时 params.item 是交出的物品
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    item: ItemId | None = None


class ActivePlaythrough(BaseModel):
    """
    进行中的局（1、2.2 的 409）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    playthroughId: PlaythroughId
    roleId: RoleId
    roleName: Annotated[str, Field(min_length=1)]
    actId: ActId
    tLabel: TLabel
    updatedAt: RecordedAt


class ApproachArrivedMessage(BaseModel):
    """
    走过来的人物到了 2.5 m 内（3.10）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    type: Literal["approach_arrived"] = "approach_arrived"
    character: CharacterId


class ApproachDismissMessage(BaseModel):
    """
    「いまは、いい」、走开，或等了 20 秒（3.10）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    type: Literal["approach_dismiss"] = "approach_dismiss"
    character: CharacterId
    reason: Literal["dismissed", "walked_away", "timeout"]


class ApproachMessage(BaseModel):
    """
    人物要走过来找你（3.10）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    type: Literal["approach"] = "approach"
    character: CharacterId
    kind: Literal["request", "news"]


type AssetPath = Annotated[str, Field(min_length=1, pattern="^/[^\\s?#]*$", title="AssetPath")]
"""
同源的静态资源路径（第 0 节「来源」），以 / 开头，文件名带 hash
"""


type BeatChange = Annotated[
    Literal["happened", "prevented", "delayed", "hastened", "altered"],
    Field(title="BeatChange"),
]
"""
节拍的走向，和数据契约 Effect（op = beat）的 to 同一组值
"""


type BookId = Annotated[str, Field(min_length=1, pattern="^[a-z0-9]+(?:-[a-z0-9]+)*$", title="BookId")]
"""
书的 ID（manifest 路径里的 bookId），例 hashire-merosu
"""


type ClientMsgId = Annotated[str, Field(max_length=64, min_length=1, title="ClientMsgId")]
"""
前端生成的动作 ID（第 0 节「幂等」），例 UUID
"""


type ClientTurnSeq = Annotated[int, Field(ge=1, le=2147483647, title="ClientTurnSeq")]
"""
前端分配的 turnSeq（3.1）：每条连接从 1 起，最高位为 0
"""


class ClockPatch(BaseModel):
    """
    commit.patch.clock（3.4）：t、tLabel 必填，deadlineT 可选（C-1 评审定）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    t: StoryTime
    tLabel: TLabel
    deadlineT: StoryTime | None = None


type OptionId = Annotated[str, Field(min_length=1)]
"""
null = 当作「不是」
"""


class ConfirmOption(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    optionId: Annotated[str, Field(min_length=1)]
    """
    例 yes、no
    """
    label: Annotated[str, Field(min_length=1)]


class CreatePlaythroughRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    bookId: BookId
    roleId: RoleId


type CueKind = Annotated[Literal["arrival_capped"], Field(title="CueKind")]
"""
固定台词的种类；也是 manifest 里 prerecorded.cues 的键
"""


class Deadline(BaseModel):
    """
    期限（2.3）：玩家知道约定（契约 1.7 knows(player, fact.promise)）之前 shown = false、没有 line；之后一直 shown = true、带 line（S-077 ⑫，v1.0.3）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    shown: bool
    line: Annotated[str | None, Field(min_length=1)] = None
    """
    期限那一行，例「期限　三日目の日没／遅れれば、身代わりが死ぬ」
    """


class DegradedMessage(BaseModel):
    """
    降级为文字回答
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    type: Literal["degraded"] = "degraded"
    voice: Literal[False] = False
    reason: Literal["budget", "service", "daily"]


type DraftId = Annotated[
    str,
    Field(min_length=1, pattern="^draft_[0-7][0-9A-HJKMNP-TV-Z]{25}$", title="DraftId"),
]
"""
待确认的举动（3.9），draft_ 加 ULID（大写 Crockford base32，第一位 0〜7，同数据契约的运行时 ID）
"""


type AfterLine = Annotated[str, Field(min_length=1)]
"""
选了以后过场页多显示的一句
"""


class EnRouteOption(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    index: Annotated[int, Field(ge=0, le=1)]
    """
    在 choices 里的序号
    """
    label: Annotated[str, Field(min_length=1)]
    melosMinutes: int | None
    """
    最后一项（照原作）为 null
    """
    afterLine: AfterLine | None
    """
    不加时为 null
    """


class EndingCardViewCharacterLinesItem(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    character: CharacterId
    line: Annotated[str, Field(max_length=40, min_length=1)]
    """
    ≤ 40 字
    """


class EndingCardView(BaseModel):
    """
    结局卡（2.8）：Ending.card 加 fallbackImageUrl
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
    characterLines: Annotated[list[EndingCardViewCharacterLinesItem], Field(max_length=3, min_length=1)]
    """
    （1.6 起 1〜3 人）影响最深的 1〜3 人，一个也没排上名时是梅洛斯一句（卡片按最多 3 行排）
    """
    contrast: Annotated[str, Field(max_length=48, min_length=1)]
    """
    「原作との違い」≤ 48 字
    """
    fallbackImageUrl: AssetPath
    """
    截帧失败时用的预画插画（每类底线结局一张）
    """


class EndingPending(BaseModel):
    """
    还没生成（202）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    status: Literal["pending"] = "pending"
    etaSeconds: Annotated[int, Field(ge=0)]


class EndingReadyMessage(BaseModel):
    """
    结局已生成，用 2.8 取
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    type: Literal["ending_ready"] = "ending_ready"
    endingId: EndingId


class EndingWorldViewEpilogueItem(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    sentence: Annotated[str, Field(min_length=1)]
    cites: Annotated[list[EventId], Field(min_length=1)]
    """
    至少引用一个本局事件
    """


class EndingWorldViewContrast(BaseModel):
    """
    （1.1，S-026）「原作では…／あなたの世界では…」
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    original: Annotated[str, Field(min_length=1)]
    yours: Annotated[str, Field(min_length=1)]
    beat: BeatId | None = None


class EndingWorldView(BaseModel):
    """
    结局的世界层（2.8）。contrast 和数据契约一样可选
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    outcomeId: Annotated[str, Field(min_length=1)]
    """
    variant?.id ?? outcome
    """
    baseline: bool
    """
    true = 5 类底线结局之一（没有 variant）
    """
    title: Annotated[str, Field(min_length=1)]
    """
    variant?.title ?? title
    """
    epilogue: list[EndingWorldViewEpilogueItem]
    """
    每句至少引用一个事件
    """
    contrast: Annotated[EndingWorldViewContrast | None, Field(title="EndingWorldViewContrast")] = None
    """
    （1.1，S-026）「原作では…／あなたの世界では…」
    """


class EndingYouViewDidForYouItem(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    sentence: Annotated[str, Field(min_length=1)]
    cites: Annotated[list[EventId], Field(min_length=1)]
    """
    至少引用一个本局事件
    """


class EndingYouViewYouDidItem(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    sentence: Annotated[str, Field(min_length=1)]
    cites: Annotated[list[EventId], Field(min_length=1)]
    """
    至少引用一个本局事件
    """


class EndingYouView(BaseModel):
    """
    结局的「你」层（2.8）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    title: Annotated[str, Field(min_length=1)]
    fate: Annotated[str, Field(min_length=1)]
    didForYou: list[EndingYouViewDidForYouItem]
    """
    （1.1，D-012）人物为你做的事
    """
    youDid: list[EndingYouViewYouDidItem]
    """
    （1.1）你为人物做的事
    """


type RetryAfterSeconds = Annotated[int, Field(ge=0)]
"""
rate_limited、daily_limit 时给
"""


type ErrorCode = Annotated[
    Literal[
        "invalid_request",
        "unauthenticated",
        "forbidden",
        "not_found",
        "invalid_invite",
        "active_playthrough_exists",
        "idempotency_conflict",
        "rate_limited",
        "daily_limit",
        "voice_unavailable",
        "invalid_choice",
        "internal",
    ],
    Field(title="ErrorCode"),
]
"""
第 5 节的错误码，加第 1 节的 invalid_invite（登录 401）和 invalid_request（400：请求体、参数或 WebSocket 消息不合 Schema，是前端的毛病，不给玩家具体原因）（C-1 评审定）
"""


class EventRejectedMessage(BaseModel):
    """
    非生产（hello.debug = true）：候选事件被否决
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    type: Literal["event_rejected"] = "event_rejected"
    turnId: TurnId
    candidate: Event
    """
    被否决的候选事件，就是写进事件流的那条 rejected 事件：完整的 Event，check.status = rejected、effects 为空、dt = 0（数据契约第 3 节）。导演事件不过 3.2 节的规矩时直接丢掉，不发 event_rejected（C-1 评审定）
    """
    failedRules: list[
        Literal["R1-anchor", "R2-precondition", "R3-time", "R4-knowledge", "R5-persona", "R6-safety", "R7-capability"]
    ]
    reason: Annotated[str, Field(min_length=1)]


class FarMessage(BaseModel):
    """
    离开 12 m
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    type: Literal["far"] = "far"
    character: CharacterId


class FocusMessage(BaseModel):
    """
    玩家点了这个人物
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    type: Literal["focus"] = "focus"
    character: CharacterId


class Forecast(BaseModel):
    """
    梅洛斯预计到达刑场的时刻（2.3）；玩家知道约定之前整个为 null（防剧透，条件和 Deadline.shown 一样）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    melosEtaT: StoryTime
    beforeDeadline: bool
    """
    false 时地图顶部写「このままでは、日没に間に合わない」
    """


class Freeform(BaseModel):
    """
    幕末能不能自己说打算（3.11），同一次幕末最多试 2 次
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    allowed: bool
    triesLeft: Annotated[int, Field(ge=0, le=2)]


class GoawayMessage(BaseModel):
    """
    服务端要关闭连接，前端按第 4 节重连
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    type: Literal["goaway"] = "goaway"
    reason: Literal["deploy", "maintenance"]
    reconnectAfterMs: Annotated[int, Field(ge=0)]


type InputMode = Annotated[Literal["voice", "text"], Field(title="InputMode")]


type InteractableId = Annotated[str, Field(max_length=128, min_length=1, title="InteractableId")]
"""
场景里可「調べる」的东西或场景出口（2.3），例 obj.market-stall
"""


class InterruptedMessage(BaseModel):
    """
    服务端确认打断：人物还在说时被新的一轮打断。被打断的轮没有 turn_complete，照常交给叙事者（v1.0.3）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    type: Literal["interrupted"] = "interrupted"
    turnId: TurnId


type LastSeq = Annotated[int, Field(ge=0, title="LastSeq")]
"""
前端已应用的最后一个序号；还没有事件时为 0
"""


type PlayerText = Annotated[str, Field(min_length=1)]
"""
原话已清空的轮次为 null
"""


type CharacterText = Annotated[str, Field(min_length=1)]
"""
原话已清空、或人物的文字没收到时为 null
"""


class LastTurn(BaseModel):
    """
    断线前的最后一轮（第 4 节）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    turnId: TurnId
    character: CharacterId | None
    """
    和谁说的；幕末用声音说打算的一轮（activity_start purpose = act_plan）没有人物，为 null（C-1 评审定）
    """
    status: Literal["settled", "pending", "lost"]
    """
    settled / pending（叙事者还在判）/ lost（断线时人物还没说完：不判、没有 turn_settled，v1.0.3）
    """
    playerText: PlayerText | None
    """
    原话已清空的轮次为 null
    """
    characterText: CharacterText | None
    """
    原话已清空、或人物的文字没收到时为 null
    """


class LoginRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    inviteCode: Annotated[str, Field(max_length=64, min_length=1)]
    """
    邀请码，不限格式（≤ 64 字），前端只去掉前后空格（C-1 评审定）
    """


class ManifestParams(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    bookId: BookId


class ManifestResponseBook(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    id: BookId
    title: Annotated[str, Field(min_length=1)]
    author: Annotated[str, Field(min_length=1)]


class ManifestResponseRolesItem(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    roleId: RoleId
    name: Annotated[str, Field(min_length=1)]
    summary: Annotated[str, Field(min_length=1)]
    startSceneId: SceneId
    startActId: ActId


class ManifestResponseScenesItem(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    sceneId: SceneId
    places: Annotated[list[PlaceId], Field(min_length=1)]
    assetUrl: AssetPath
    assetVersion: Annotated[str, Field(min_length=1)]


class ManifestResponseActsItem(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    actId: ActId
    title: Annotated[str, Field(min_length=1)]
    sceneIds: Annotated[list[SceneId], Field(min_length=1)]


type Day = Annotated[str, Field(min_length=1)]


class ManifestResponseClock(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    deadlineT: StoryTime
    sunsetMinuteOfDay: Annotated[int, Field(ge=0, le=1439)]
    days: Annotated[list[Day], Field(min_length=1)]


class ManifestResponseRubyItem(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    word: Annotated[str, Field(min_length=1)]
    reading: Annotated[str, Field(min_length=1)]


class MeResponseUser(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    userRef: str
    """
    邀请码账号的匿名 ID（S-020），不是邮箱、不是姓名
    """


class MemoryBookCharacterDidForYouItem(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    eventId: EventId
    text: Annotated[str, Field(min_length=1)]


class MemoryBookCharacterYouDidItem(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    eventId: EventId
    text: Annotated[str, Field(min_length=1)]


class MemoryChange(BaseModel):
    """
    commit.memories[]（3.4）；前端据此让記憶帳的查询失效重拉。added、updated 必带 text 和 kind，deleted 不带（C-1 评审定）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    character: CharacterId
    change: Literal["added", "updated", "deleted"]
    memoryId: MemoryId
    text: str | None = None
    """
    角色视角的一句日语，給記憶帳显示；不含现实个人信息；删除后清空
    """
    kind: Literal["promise", "help", "harm", "shared-moment", "claim", "impression"] | None = None
    relationLabel: str
    """
    由 trust 区间映射（第 4 节的表）
    """
    relationLevel: Literal[1, 2, 3, 4, 5]
    """
    （1.5）同一区间的档位，接口里叫 relationLevel
    """


class MemoryDeleteResponse(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    memoryId: MemoryId
    deleted: Literal[True] = True
    character: CharacterId
    relationLabel: str
    """
    由 trust 区间映射（第 4 节的表）
    """
    relationLevel: Literal[1, 2, 3, 4, 5]
    """
    （1.5）同一区间的档位，接口里叫 relationLevel
    """
    promiseVoided: PromiseId | None
    """
    作废了约定时给它的 ID
    """
    sessionRebuilt: bool


type Keeps = Annotated[str, Field(min_length=1)]
"""
已经发生、删除也不撤销的后果，一句话
"""


class MemoryImpactResponse(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    keeps: Keeps | None
    """
    没有就是 null
    """
    voidsPromise: bool
    """
    true = 删除后这条记忆所属的约定变成 voided
    """


class MemoryPathParams(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    id: PlaythroughId
    memoryId: MemoryId


class MemoryView(BaseModel):
    """
    記憶帳里的一条记忆（2.7）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    memoryId: MemoryId
    kind: Literal["promise", "help", "harm", "shared-moment", "claim", "impression"]
    text: str
    """
    角色视角的一句日语，給記憶帳显示；不含现实个人信息；删除后清空
    """
    t: StoryTime
    tLabel: TLabel
    via: Literal["witnessed", "told", "rumor"]
    """
    （1.1）見た / 聞いた / 噂で
    """
    promiseId: PromiseId | None


type Minutes = Annotated[int, Field(ge=0, title="Minutes")]
"""
故事分钟数
"""


class NarrationMessage(BaseModel):
    """
    不随事件的叙事一行（灰色地の文）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    type: Literal["narration"] = "narration"
    line: Annotated[str, Field(min_length=1)]
    ref: Annotated[str | None, Field(max_length=128, min_length=1)] = None
    """
    服务端内部的来源标记（例：节拍 ID、离题提示的规则名），只给日志和评测对照；前端不用、不显示（C-1 评审定）
    """


class NearMessage(BaseModel):
    """
    玩家进入某个可对话人物 8 m 内：服务端预热会话
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    type: Literal["near"] = "near"
    character: CharacterId


class PendingApproach(BaseModel):
    """
    续玩时正走过来的人物：和 approach（3.10）同形
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    character: CharacterId
    kind: Literal["request", "news"]


class PendingConfirm(BaseModel):
    """
    续玩时还没回答的意图确认：confirm（3.9）的字段加剩余秒数 remainingSec（第 4 节「含剩余秒数」），timeoutSec 照样给（C-1 评审定）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    draftId: DraftId
    character: CharacterId
    prompt: Annotated[str, Field(min_length=1)]
    options: Annotated[list[ConfirmOption], Field(min_length=2)]
    timeoutSec: Annotated[int, Field(ge=1)]
    remainingSec: Annotated[int, Field(ge=0)]


class PingMessage(BaseModel):
    """
    每 20 秒一次
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    type: Literal["ping"] = "ping"


class PlaceAccess(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    id: PlaceId
    enabled: bool
    """
    false 时前端提前把那条路挡住
    """
    reason: Annotated[str | None, Field(min_length=1)] = None
    """
    进不去的理由，一句故事里的说明；只在 enabled = false 时给
    """


type PlanOptionId = Annotated[
    str,
    Field(min_length=1, pattern="^plan_[0-7][0-9A-HJKMNP-TV-Z]{25}$", title="PlanOptionId"),
]
"""
幕末说出打算后的替代去处（3.11 alternative.optionId）：plan_ 加 ULID，和别的运行时 ID 一样（C-1 评审定）
"""


class PlaythroughPathParams(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    id: PlaythroughId


class PongMessage(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    type: Literal["pong"] = "pong"


class PromiseChange(BaseModel):
    """
    这个事件让一个约定成立、兑现、违背或作废（2.4）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    promiseId: PromiseId
    change: Literal["made", "kept", "broken", "voided"]
    """
    和数据契约 Effect（op = promise）的 change 同一组值
    """


type PromiseDirection = Annotated[Literal["playerToCharacter", "characterToPlayer"], Field(title="PromiseDirection")]
"""
playerToCharacter = Promise.from 是 player；characterToPlayer = Promise.to 是 player
"""


class PromiseUpdate(BaseModel):
    """
    commit.promises[]（3.4）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    promiseId: PromiseId
    character: CharacterId
    text: str
    """
    约定的内容（日语，中性，不是原话）
    """
    direction: PromiseDirection
    status: Literal["open", "kept", "broken", "voided"]
    """
    まだ / 果たされた / 破られた / 作废
    """


class PromiseView(BaseModel):
    """
    記憶帳里的一条约定（2.7）。voided 照给，前端不显示
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    promiseId: PromiseId
    text: str
    """
    约定的内容（日语，中性，不是原话）
    """
    direction: PromiseDirection
    status: Literal["open", "kept", "broken", "voided"]
    """
    まだ / 果たされた / 破られた / 作废
    """
    eventId: EventId
    """
    约定成立的事件（Promise.madeBy）
    """


type QualityLevel = Annotated[Literal["L0", "L1", "L2", "L3"], Field(title="QualityLevel")]
"""
画质级（D-019）
"""


class RecapItem(BaseModel):
    """
    「その頃」的一件（3.11）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    eventId: EventId
    line: Annotated[str, Field(min_length=1)]
    promise: Literal["kept", "broken"] | None = None
    """
    这件事是一个约定的兑现或违背时给
    """


type RevealId = Annotated[
    str,
    Field(min_length=1, pattern="^rev_[0-7][0-9A-HJKMNP-TV-Z]{25}$", title="RevealId"),
]
"""
关键时刻（3.4），rev_ 加 ULID（大写 Crockford base32，第一位 0〜7，同数据契约的运行时 ID）
"""


class SafetyHintMessage(BaseModel):
    """
    不暂停的小提示（S-069），一局最多一次
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    type: Literal["safety_hint"] = "safety_hint"


class SafetyPauseMessage(BaseModel):
    """
    出戏卡（3.12）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    type: Literal["safety_pause"] = "safety_pause"


class SafetyResumeMessage(BaseModel):
    """
    玩家在出戏卡上选了「物語に戻る」（3.12）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    type: Literal["safety_resume"] = "safety_resume"


class SafetyResumedMessage(BaseModel):
    """
    回到故事
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    type: Literal["safety_resumed"] = "safety_resumed"


type Seq = Annotated[int, Field(ge=1, title="Seq")]
"""
一局里的事件序号（2.4）
"""


type ServerTurnSeq = Annotated[int, Field(ge=2147483649, le=4294967295, title="ServerTurnSeq")]
"""
服务端发起的轮次的 turnSeq（3.1）：最高位为 1，从 0x80000001 起
"""


class SessionPreparingMessage(BaseModel):
    """
    需要等待演出（人物转身、吸气）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    type: Literal["session_preparing"] = "session_preparing"
    character: CharacterId
    reason: Literal["switch", "rebuild", "reconnect"]
    etaMs: Annotated[int, Field(ge=0)]


class SessionReadyMessage(BaseModel):
    """
    这个人物可以说话了
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    type: Literal["session_ready"] = "session_ready"
    character: CharacterId
    voiceAvailable: bool


class SituationalAction(BaseModel):
    """
    此刻能做的情境动作（2.3、3.8）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    actionId: ActionId
    kind: Literal["examine", "give", "follow", "block", "help", "wait", "go", "shortcut", "run-together", "hasten"]
    target: CharacterId | None = None
    """
    对象人物；没有对象的动作（wait 这类，世界模型 Affordance.target 可选）省略，不给 null（C-1 评审定）
    """
    label: str
    """
    按钮上的动词短语（日语），不写耗时
    """
    estimatedMinutes: Minutes
    melos: Literal["delay", "hasten"] | None
    """
    第四幕对梅洛斯的影响（S-036、S-038）；没有为 null
    """
    melosMinutes: int | None
    """
    没有 melos 的动作为 null
    """
    melosInTime: bool | None
    """
    没有 melos 的动作为 null
    """
    enabled: bool


class SnapshotClock(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    t: StoryTime
    tLabel: TLabel
    deadlineT: StoryTime


type Speaker = Annotated[Literal["player"] | CharacterId, Field(title="Speaker")]
"""
说话的人：玩家或人物
"""


type Spot = Annotated[str, Field(max_length=64, min_length=1, title="Spot")]
"""
场景里的位置点（第 0 节），前端在 3D 场景里定义，例 fountain-east
"""


type StagingState = Annotated[
    Literal["present", "in-crowd", "on-cross", "freed", "arriving", "approaching", "collapsed", "absent"],
    Field(title="StagingState"),
]
"""
ux-design 11.1 的 8 个状态；前端遇到不认识的按 present 演
"""


class SuggestionsMessageItemsItem(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    text: Annotated[str, Field(min_length=1)]
    kind: Literal["ask", "act", "accept", "decline"]


class SuggestionsMessage(BaseModel):
    """
    候选话语 2〜3 个（3.5）；新的一条替换旧的
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    type: Literal["suggestions"] = "suggestions"
    turnId: TurnId | None = None
    character: CharacterId
    items: Annotated[list[SuggestionsMessageItemsItem], Field(max_length=3, min_length=2)]


class TelemetryActPlanResultProps(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    actId: ActId
    accepted: bool
    try_: Annotated[int, Field(alias="try", ge=1, le=2)]
    inputMode: InputMode


class TelemetryActPlanResult(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    name: Literal["act_plan_result"] = "act_plan_result"
    playthroughId: PlaythroughId | None = None
    """
    没有局时省略
    """
    clientTs: RecordedAt
    """
    真实时间：设备的钟，ISO 8601 UTC，以 Z 结尾（data-design 9.3）
    """
    t: StoryTime | None = None
    """
    故事时间，有的话
    """
    props: Annotated[TelemetryActPlanResultProps, Field(title="TelemetryActPlanResultProps")]


class TelemetryAppOpenProps(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    entry: Literal["direct", "line", "other"]
    inAppBrowser: bool


class TelemetryAppOpen(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    name: Literal["app_open"] = "app_open"
    playthroughId: PlaythroughId | None = None
    """
    没有局时省略
    """
    clientTs: RecordedAt
    """
    真实时间：设备的钟，ISO 8601 UTC，以 Z 结尾（data-design 9.3）
    """
    t: StoryTime | None = None
    """
    故事时间，有的话
    """
    props: Annotated[TelemetryAppOpenProps, Field(title="TelemetryAppOpenProps")]


class TelemetryAppResumedProps(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    awayMs: Annotated[int, Field(ge=0)]
    discarded: bool
    resumeMs: Annotated[int, Field(ge=0)]
    contextLost: bool


class TelemetryAppResumed(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    name: Literal["app_resumed"] = "app_resumed"
    playthroughId: PlaythroughId | None = None
    """
    没有局时省略
    """
    clientTs: RecordedAt
    """
    真实时间：设备的钟，ISO 8601 UTC，以 Z 结尾（data-design 9.3）
    """
    t: StoryTime | None = None
    """
    故事时间，有的话
    """
    props: Annotated[TelemetryAppResumedProps, Field(title="TelemetryAppResumedProps")]


class TelemetryApproachEndedProps(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    character: CharacterId
    result: Literal["talked", "dismissed", "walked_away"]


class TelemetryApproachEnded(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    name: Literal["approach_ended"] = "approach_ended"
    playthroughId: PlaythroughId | None = None
    """
    没有局时省略
    """
    clientTs: RecordedAt
    """
    真实时间：设备的钟，ISO 8601 UTC，以 Z 结尾（data-design 9.3）
    """
    t: StoryTime | None = None
    """
    故事时间，有的话
    """
    props: Annotated[TelemetryApproachEndedProps, Field(title="TelemetryApproachEndedProps")]


class TelemetryApproachShownProps(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    character: CharacterId


class TelemetryApproachShown(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    name: Literal["approach_shown"] = "approach_shown"
    playthroughId: PlaythroughId | None = None
    """
    没有局时省略
    """
    clientTs: RecordedAt
    """
    真实时间：设备的钟，ISO 8601 UTC，以 Z 结尾（data-design 9.3）
    """
    t: StoryTime | None = None
    """
    故事时间，有的话
    """
    props: Annotated[TelemetryApproachShownProps, Field(title="TelemetryApproachShownProps")]


class TelemetryCommon(BaseModel):
    """
    公共属性（data-design 9.3），只有粗粒度的设备信息；每批带一次，服务端入库时抄到这一批的每条（C-1 评审定）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    deviceClass: Annotated[str, Field(max_length=64, min_length=1)]
    """
    屏幕尺寸类：逻辑像素加 DPR，如 ios-390x844@3
    """
    os: Annotated[str, Field(max_length=32, min_length=1)]
    browser: Annotated[str, Field(max_length=64, min_length=1)]
    """
    含 App 内浏览器名
    """
    appVersion: Annotated[str, Field(max_length=64, min_length=1)]


class TelemetryConfirmAnsweredProps(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    answer: Literal["yes", "no", "timeout"]


class TelemetryConfirmAnswered(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    name: Literal["confirm_answered"] = "confirm_answered"
    playthroughId: PlaythroughId | None = None
    """
    没有局时省略
    """
    clientTs: RecordedAt
    """
    真实时间：设备的钟，ISO 8601 UTC，以 Z 结尾（data-design 9.3）
    """
    t: StoryTime | None = None
    """
    故事时间，有的话
    """
    props: Annotated[TelemetryConfirmAnsweredProps, Field(title="TelemetryConfirmAnsweredProps")]


class TelemetryConnectionLostProps(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    reason: Annotated[str, Field(max_length=64, min_length=1)]


class TelemetryConnectionLost(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    name: Literal["connection_lost"] = "connection_lost"
    playthroughId: PlaythroughId | None = None
    """
    没有局时省略
    """
    clientTs: RecordedAt
    """
    真实时间：设备的钟，ISO 8601 UTC，以 Z 结尾（data-design 9.3）
    """
    t: StoryTime | None = None
    """
    故事时间，有的话
    """
    props: Annotated[TelemetryConnectionLostProps, Field(title="TelemetryConnectionLostProps")]


class TelemetryConnectionRestoredProps(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    downMs: Annotated[int, Field(ge=0)]


class TelemetryConnectionRestored(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    name: Literal["connection_restored"] = "connection_restored"
    playthroughId: PlaythroughId | None = None
    """
    没有局时省略
    """
    clientTs: RecordedAt
    """
    真实时间：设备的钟，ISO 8601 UTC，以 Z 结尾（data-design 9.3）
    """
    t: StoryTime | None = None
    """
    故事时间，有的话
    """
    props: Annotated[
        TelemetryConnectionRestoredProps,
        Field(title="TelemetryConnectionRestoredProps"),
    ]


class TelemetryContinueStartedProps(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    awayMs: Annotated[int, Field(ge=0)]


class TelemetryContinueStarted(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    name: Literal["continue_started"] = "continue_started"
    playthroughId: PlaythroughId | None = None
    """
    没有局时省略
    """
    clientTs: RecordedAt
    """
    真实时间：设备的钟，ISO 8601 UTC，以 Z 结尾（data-design 9.3）
    """
    t: StoryTime | None = None
    """
    故事时间，有的话
    """
    props: Annotated[TelemetryContinueStartedProps, Field(title="TelemetryContinueStartedProps")]


class TelemetryDegradedShownProps(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    reason: Literal["budget", "service", "daily"]


class TelemetryDegradedShown(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    name: Literal["degraded_shown"] = "degraded_shown"
    playthroughId: PlaythroughId | None = None
    """
    没有局时省略
    """
    clientTs: RecordedAt
    """
    真实时间：设备的钟，ISO 8601 UTC，以 Z 结尾（data-design 9.3）
    """
    t: StoryTime | None = None
    """
    故事时间，有的话
    """
    props: Annotated[TelemetryDegradedShownProps, Field(title="TelemetryDegradedShownProps")]


class TelemetryEndingCardSavedProps(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    endingId: EndingId


class TelemetryEndingCardSaved(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    name: Literal["ending_card_saved"] = "ending_card_saved"
    playthroughId: PlaythroughId | None = None
    """
    没有局时省略
    """
    clientTs: RecordedAt
    """
    真实时间：设备的钟，ISO 8601 UTC，以 Z 结尾（data-design 9.3）
    """
    t: StoryTime | None = None
    """
    故事时间，有的话
    """
    props: Annotated[TelemetryEndingCardSavedProps, Field(title="TelemetryEndingCardSavedProps")]


class TelemetryEndingClosedProps(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    endingId: EndingId
    dwellMs: Annotated[int, Field(ge=0)]


class TelemetryEndingClosed(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    name: Literal["ending_closed"] = "ending_closed"
    playthroughId: PlaythroughId | None = None
    """
    没有局时省略
    """
    clientTs: RecordedAt
    """
    真实时间：设备的钟，ISO 8601 UTC，以 Z 结尾（data-design 9.3）
    """
    t: StoryTime | None = None
    """
    故事时间，有的话
    """
    props: Annotated[TelemetryEndingClosedProps, Field(title="TelemetryEndingClosedProps")]


class TelemetryEndingSharedProps(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    endingId: EndingId
    completed: bool | None = None


class TelemetryEndingShared(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    name: Literal["ending_shared"] = "ending_shared"
    playthroughId: PlaythroughId | None = None
    """
    没有局时省略
    """
    clientTs: RecordedAt
    """
    真实时间：设备的钟，ISO 8601 UTC，以 Z 结尾（data-design 9.3）
    """
    t: StoryTime | None = None
    """
    故事时间，有的话
    """
    props: Annotated[TelemetryEndingSharedProps, Field(title="TelemetryEndingSharedProps")]


class TelemetryEndingViewedProps(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    endingId: EndingId
    outcome: Annotated[str, Field(max_length=64, min_length=1)]


class TelemetryEndingViewed(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    name: Literal["ending_viewed"] = "ending_viewed"
    playthroughId: PlaythroughId | None = None
    """
    没有局时省略
    """
    clientTs: RecordedAt
    """
    真实时间：设备的钟，ISO 8601 UTC，以 Z 结尾（data-design 9.3）
    """
    t: StoryTime | None = None
    """
    故事时间，有的话
    """
    props: Annotated[TelemetryEndingViewedProps, Field(title="TelemetryEndingViewedProps")]


class TelemetryGlContextLostProps(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    restored: bool


class TelemetryGlContextLost(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    name: Literal["gl_context_lost"] = "gl_context_lost"
    playthroughId: PlaythroughId | None = None
    """
    没有局时省略
    """
    clientTs: RecordedAt
    """
    真实时间：设备的钟，ISO 8601 UTC，以 Z 结尾（data-design 9.3）
    """
    t: StoryTime | None = None
    """
    故事时间，有的话
    """
    props: Annotated[TelemetryGlContextLostProps, Field(title="TelemetryGlContextLostProps")]


class TelemetryMapOpenedProps(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    from_: Annotated[Literal["hud", "sonokoro", "ending"], Field(alias="from")]


class TelemetryMapOpened(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    name: Literal["map_opened"] = "map_opened"
    playthroughId: PlaythroughId | None = None
    """
    没有局时省略
    """
    clientTs: RecordedAt
    """
    真实时间：设备的钟，ISO 8601 UTC，以 Z 结尾（data-design 9.3）
    """
    t: StoryTime | None = None
    """
    故事时间，有的话
    """
    props: Annotated[TelemetryMapOpenedProps, Field(title="TelemetryMapOpenedProps")]


class TelemetryMemoryBookOpened(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    name: Literal["memory_book_opened"] = "memory_book_opened"
    playthroughId: PlaythroughId | None = None
    """
    没有局时省略
    """
    clientTs: RecordedAt
    """
    真实时间：设备的钟，ISO 8601 UTC，以 Z 结尾（data-design 9.3）
    """
    t: StoryTime | None = None
    """
    故事时间，有的话
    """
    props: Annotated[dict[str, Any], Field(max_length=0, title="TelemetryMemoryBookOpenedProps")]


class TelemetryMemoryDeletedProps(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    character: CharacterId


class TelemetryMemoryDeleted(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    name: Literal["memory_deleted"] = "memory_deleted"
    playthroughId: PlaythroughId | None = None
    """
    没有局时省略
    """
    clientTs: RecordedAt
    """
    真实时间：设备的钟，ISO 8601 UTC，以 Z 结尾（data-design 9.3）
    """
    t: StoryTime | None = None
    """
    故事时间，有的话
    """
    props: Annotated[TelemetryMemoryDeletedProps, Field(title="TelemetryMemoryDeletedProps")]


class TelemetryMemorySectionViewedProps(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    section: Literal["promises", "didForYou", "youDid", "memories"]


class TelemetryMemorySectionViewed(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    name: Literal["memory_section_viewed"] = "memory_section_viewed"
    playthroughId: PlaythroughId | None = None
    """
    没有局时省略
    """
    clientTs: RecordedAt
    """
    真实时间：设备的钟，ISO 8601 UTC，以 Z 结尾（data-design 9.3）
    """
    t: StoryTime | None = None
    """
    故事时间，有的话
    """
    props: Annotated[
        TelemetryMemorySectionViewedProps,
        Field(title="TelemetryMemorySectionViewedProps"),
    ]


class TelemetryMicPermissionProps(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    result: Literal["granted", "denied", "unavailable"]
    reason: Annotated[str | None, Field(max_length=64, min_length=1)] = None
    afterPrimer: bool


class TelemetryMicPermission(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    name: Literal["mic_permission"] = "mic_permission"
    playthroughId: PlaythroughId | None = None
    """
    没有局时省略
    """
    clientTs: RecordedAt
    """
    真实时间：设备的钟，ISO 8601 UTC，以 Z 结尾（data-design 9.3）
    """
    t: StoryTime | None = None
    """
    故事时间，有的话
    """
    props: Annotated[TelemetryMicPermissionProps, Field(title="TelemetryMicPermissionProps")]


type FrameTimeHistogramItem = Annotated[int, Field(ge=0)]


class TelemetryPerfSampleProps(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    frameTimeHistogram: Annotated[list[FrameTimeHistogramItem], Field(max_length=9, min_length=9)]
    """
    10 秒的帧时间直方图，固定 9 格，每格是帧数（data-design 9.3）。第 i 格数「上一格上界 < 帧时间 ≤ 这一格上界」的帧，上界依次是 8.5、12、17、20、26、34、51、101 ms，最后一格是 > 101 ms。边界都放在刷新间隔整数倍稍上，同一种掉帧不会拆到两格。格子固定，不同版本前端发来的直方图才能相加；要换边界就另起一个字段
    """
    longTasks: Annotated[int, Field(ge=0)]
    jsHeapMb: Annotated[float | None, Field(ge=0.0)] = None
    renderer: Literal["webgl", "webgpu"]
    qualityLevel: QualityLevel
    assetTier: Literal["standard", "high"]
    dpr: Annotated[float, Field(gt=0.0)]
    drawCalls: Annotated[int, Field(ge=0)]
    lowPower: bool


class TelemetryPerfSample(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    name: Literal["perf_sample"] = "perf_sample"
    playthroughId: PlaythroughId | None = None
    """
    没有局时省略
    """
    clientTs: RecordedAt
    """
    真实时间：设备的钟，ISO 8601 UTC，以 Z 结尾（data-design 9.3）
    """
    t: StoryTime | None = None
    """
    故事时间，有的话
    """
    props: Annotated[TelemetryPerfSampleProps, Field(title="TelemetryPerfSampleProps")]


class TelemetryQualityChangedProps(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    from_: Annotated[QualityLevel | None, Field(alias="from")] = None
    to: QualityLevel
    reason: Literal["start", "down", "up", "lowPower", "locked"]
    probeGpuMs: Annotated[float | None, Field(ge=0.0)] = None
    """
    起始档自测的一帧 GPU 耗时（ms），reason = start 时带；取到 0.1 ms（防设备指纹，data-design 9.3）
    """
    assetMbps: Annotated[int | None, Field(ge=0)] = None


class TelemetryQualityChanged(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    name: Literal["quality_changed"] = "quality_changed"
    playthroughId: PlaythroughId | None = None
    """
    没有局时省略
    """
    clientTs: RecordedAt
    """
    真实时间：设备的钟，ISO 8601 UTC，以 Z 结尾（data-design 9.3）
    """
    t: StoryTime | None = None
    """
    故事时间，有的话
    """
    props: Annotated[TelemetryQualityChangedProps, Field(title="TelemetryQualityChangedProps")]


class TelemetryReplayStartedProps(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    fromEndingId: EndingId
    roleId: RoleId


class TelemetryReplayStarted(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    name: Literal["replay_started"] = "replay_started"
    playthroughId: PlaythroughId | None = None
    """
    没有局时省略
    """
    clientTs: RecordedAt
    """
    真实时间：设备的钟，ISO 8601 UTC，以 Z 结尾（data-design 9.3）
    """
    t: StoryTime | None = None
    """
    故事时间，有的话
    """
    props: Annotated[TelemetryReplayStartedProps, Field(title="TelemetryReplayStartedProps")]


class TelemetryRoleSelectedProps(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    roleId: RoleId


class TelemetryRoleSelected(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    name: Literal["role_selected"] = "role_selected"
    playthroughId: PlaythroughId | None = None
    """
    没有局时省略
    """
    clientTs: RecordedAt
    """
    真实时间：设备的钟，ISO 8601 UTC，以 Z 结尾（data-design 9.3）
    """
    t: StoryTime | None = None
    """
    故事时间，有的话
    """
    props: Annotated[TelemetryRoleSelectedProps, Field(title="TelemetryRoleSelectedProps")]


class TelemetrySceneReadyProps(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    sceneId: SceneId
    loadMs: Annotated[int, Field(ge=0)]
    fromTap: Annotated[int | None, Field(ge=0)] = None
    """
    点「はじめる」到能走（毫秒）
    """


class TelemetrySceneReady(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    name: Literal["scene_ready"] = "scene_ready"
    playthroughId: PlaythroughId | None = None
    """
    没有局时省略
    """
    clientTs: RecordedAt
    """
    真实时间：设备的钟，ISO 8601 UTC，以 Z 结尾（data-design 9.3）
    """
    t: StoryTime | None = None
    """
    故事时间，有的话
    """
    props: Annotated[TelemetrySceneReadyProps, Field(title="TelemetrySceneReadyProps")]


class TelemetrySonokoroViewedProps(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    count: Annotated[int, Field(ge=0, le=3)]
    tappedMap: bool


class TelemetrySonokoroViewed(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    name: Literal["sonokoro_viewed"] = "sonokoro_viewed"
    playthroughId: PlaythroughId | None = None
    """
    没有局时省略
    """
    clientTs: RecordedAt
    """
    真实时间：设备的钟，ISO 8601 UTC，以 Z 结尾（data-design 9.3）
    """
    t: StoryTime | None = None
    """
    故事时间，有的话
    """
    props: Annotated[TelemetrySonokoroViewedProps, Field(title="TelemetrySonokoroViewedProps")]


class TelemetryTalkTurnProps(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    turnId: TurnId
    character: CharacterId
    inputMode: InputMode
    clientReleaseToAudibleMs: Annotated[int | None, Field(ge=0)] = None
    """
    松手到听到声音（毫秒），和 turn_complete.metrics 按 turnId 对齐
    """
    interrupted: bool
    noResponse: bool


class TelemetryTalkTurn(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    name: Literal["talk_turn"] = "talk_turn"
    playthroughId: PlaythroughId | None = None
    """
    没有局时省略
    """
    clientTs: RecordedAt
    """
    真实时间：设备的钟，ISO 8601 UTC，以 Z 结尾（data-design 9.3）
    """
    t: StoryTime | None = None
    """
    故事时间，有的话
    """
    props: Annotated[TelemetryTalkTurnProps, Field(title="TelemetryTalkTurnProps")]


class TelemetryTranscriptCorrectedProps(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    turnId: TurnId


class TelemetryTranscriptCorrected(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    name: Literal["transcript_corrected"] = "transcript_corrected"
    playthroughId: PlaythroughId | None = None
    """
    没有局时省略
    """
    clientTs: RecordedAt
    """
    真实时间：设备的钟，ISO 8601 UTC，以 Z 结尾（data-design 9.3）
    """
    t: StoryTime | None = None
    """
    故事时间，有的话
    """
    props: Annotated[
        TelemetryTranscriptCorrectedProps,
        Field(title="TelemetryTranscriptCorrectedProps"),
    ]


class TelemetryTurnRetractedProps(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    turnId: TurnId
    kind: Literal["cancel", "redo", "timeout", "correction"]
    result: Literal["retracted", "too_late"]


class TelemetryTurnRetracted(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    name: Literal["turn_retracted"] = "turn_retracted"
    playthroughId: PlaythroughId | None = None
    """
    没有局时省略
    """
    clientTs: RecordedAt
    """
    真实时间：设备的钟，ISO 8601 UTC，以 Z 结尾（data-design 9.3）
    """
    t: StoryTime | None = None
    """
    故事时间，有的话
    """
    props: Annotated[TelemetryTurnRetractedProps, Field(title="TelemetryTurnRetractedProps")]


class TelemetryWebVitalsProps(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    lcp: Annotated[float | None, Field(ge=0.0)] = None
    inp: Annotated[float | None, Field(ge=0.0)] = None
    cls: Annotated[float | None, Field(ge=0.0)] = None
    inpTarget: Annotated[str | None, Field(max_length=128, min_length=1)] = None
    loafScript: Annotated[str | None, Field(max_length=256, min_length=1)] = None


class TelemetryWebVitals(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    name: Literal["web_vitals"] = "web_vitals"
    playthroughId: PlaythroughId | None = None
    """
    没有局时省略
    """
    clientTs: RecordedAt
    """
    真实时间：设备的钟，ISO 8601 UTC，以 Z 结尾（data-design 9.3）
    """
    t: StoryTime | None = None
    """
    故事时间，有的话
    """
    props: Annotated[TelemetryWebVitalsProps, Field(title="TelemetryWebVitalsProps")]


class TelemetryWhyOpenedProps(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    target: Literal["event", "beat", "reveal", "forecast"]
    """
    和 api-contract 2.6 /why 的 target 一一对应（data-design 9.3）：reveal = 关键时刻卡上的「なぜ」，forecast = 地图顶部「間に合わない」那一行的「なぜ」
    """
    fromKeyMoment: bool


class TelemetryWhyOpened(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    name: Literal["why_opened"] = "why_opened"
    playthroughId: PlaythroughId | None = None
    """
    没有局时省略
    """
    clientTs: RecordedAt
    """
    真实时间：设备的钟，ISO 8601 UTC，以 Z 结尾（data-design 9.3）
    """
    t: StoryTime | None = None
    """
    故事时间，有的话
    """
    props: Annotated[TelemetryWhyOpenedProps, Field(title="TelemetryWhyOpenedProps")]


class TestAdvanceRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    minutes: Annotated[int, Field(ge=1, le=5460)]


type Text200 = Annotated[str, Field(max_length=200, min_length=1, title="Text200")]
"""
玩家输入的文字，≤ 200 字（3.2）
"""


class TextMessage(BaseModel):
    """
    文字输入，代替一轮语音
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    type: Literal["text"] = "text"
    turnId: TurnId
    turnSeq: ClientTurnSeq
    text: Text200
    via: Literal["typed", "chip", "correction"]
    replaces: TurnId | None = None
    """
    识别改正时被改正的那一轮（3.6）；只在 via = correction 时给
    """


class TimelineBeatItem(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    kind: Literal["beat"] = "beat"
    beatId: BeatId
    t: StoryTime
    tLabel: TLabel
    title: Annotated[str | None, Field(min_length=1)] = None
    status: Literal["canon", "hastened", "delayed", "prevented", "altered", "pending"] | None = None
    """
    canon = 数据契约 WorldState.beats 的 happened
    """
    known: bool
    """
    还没到、或玩家还不知道的节拍为 false，只给时刻
    """


class TimelineEventItem(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    kind: Literal["event"] = "event"
    eventId: EventId
    t: StoryTime
    tLabel: TLabel
    summary: Annotated[str, Field(min_length=1)]
    place: PlaceId
    style: Literal["player", "caused", "character", "system"]
    causedByPlayer: bool
    forPlayer: bool
    knownBy: list[CharacterId]
    """
    只列玩家见过的人物
    """


type TimelineItem = Annotated[
    TimelineEventItem | TimelineBeatItem,
    Field(discriminator="kind", title="TimelineItem"),
]


class TimelineResponseDaysItem(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    day: Annotated[int, Field(ge=0)]
    label: Annotated[str, Field(min_length=1)]
    items: list[TimelineItem]


class TimelineResponse(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    days: list[TimelineResponseDaysItem]
    lastSeq: LastSeq


type Text = Annotated[str, Field(min_length=1)]
"""
只有补转写也失败的人物定稿为 null
"""


class TranscriptMessage(BaseModel):
    """
    字幕。人物每一轮恰好一条 final = true，没回答的轮、出戏卡停下的轮、一个字没说就被打断的轮除外；定稿可能晚于 turn_complete
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    type: Literal["transcript"] = "transcript"
    turnId: TurnId
    speaker: Speaker
    text: Text | None
    """
    只有补转写也失败的人物定稿为 null
    """
    final: bool
    source: Literal["live", "script", "fallback"] | None = None
    """
    只在人物的 final = true 上给（S-071）
    """


type ServerReleaseToFirstAudioMs = Annotated[int, Field(ge=0)]
"""
收到 activity_end 到发出第一个音频分片（第 6 节）
"""


class TurnCompleteMessageMetrics(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    serverReleaseToFirstAudioMs: ServerReleaseToFirstAudioMs | None
    """
    audio = false 时没有第一个音频分片，给 null（C-1 评审定）
    """


class TurnCompleteMessage(BaseModel):
    """
    人物这一轮说完；被打断的轮没有这条（v1.0.3）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    type: Literal["turn_complete"] = "turn_complete"
    turnId: TurnId
    audio: bool
    """
    false = 人物这一轮没有出声，前端立即进入 no-response
    """
    metrics: Annotated[TurnCompleteMessageMetrics, Field(title="TurnCompleteMessageMetrics")]


class TurnRetractMessage(BaseModel):
    """
    作废一轮（3.6）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    type: Literal["turn_retract"] = "turn_retract"
    turnId: TurnId


class TurnRetractResultMessage(BaseModel):
    """
    「取り消す」「言い直す」的结果（3.6）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    type: Literal["turn_retract_result"] = "turn_retract_result"
    turnId: TurnId
    status: Literal["retracted", "too_late"]


type TurnSeq = Annotated[int, Field(ge=1, le=4294967295, title="TurnSeq")]
"""
二进制帧和 turn 消息里的 turnSeq：uint32，前端分配的或服务端分配的
"""


class TurnSettledMessage(BaseModel):
    """
    每一轮判完都推（3.4）；之后这一轮不能再作废
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    type: Literal["turn_settled"] = "turn_settled"
    turnId: TurnId
    outcome: Literal["committed", "no_change", "rejected", "retracted", "no_response", "paused"]
    eventIds: list[EventId]
    minutes: Minutes


class TurnStartedMessage(BaseModel):
    """
    服务端发起的一轮：人物先开口（3.9、3.10）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    type: Literal["turn_started"] = "turn_started"
    turnId: TurnId
    turnSeq: ServerTurnSeq
    speaker: CharacterId
    reason: Literal["approach", "leaving", "confirm"]


class UnfocusMessage(BaseModel):
    """
    离开对话
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    type: Literal["unfocus"] = "unfocus"
    reason: Literal["walk_away", "silence", "menu", "dismiss"]


class VisibleBeatEffect(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    kind: Literal["beat"] = "beat"
    beat: BeatId
    change: BeatChange
    label: Annotated[str, Field(min_length=1)]


class VisibleVarEffect(BaseModel):
    """
    变量这一种只给标签、不给原值（第 0 节）：kind、var、label（C-1 评审定）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    kind: Literal["var"] = "var"
    var: VarId
    label: Annotated[str, Field(min_length=1)]
    """
    StateVar.valueLabels 里这个取值的文字
    """


class Voice(BaseModel):
    """
    语音状态（2.3、第 4 节 welcome）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    enabled: bool
    degraded: bool
    minutesLeftToday: Minutes


class VoiceClip(BaseModel):
    """
    一句预录台词（2.1）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    url: AssetPath
    text: Annotated[str, Field(min_length=1)]
    """
    剧本原文，字幕用它（source = script）
    """
    durationMs: Annotated[int, Field(ge=1)]
    """
    实际音频长度
    """


class WhyBeatStep(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    beatId: BeatId
    tLabel: TLabel
    summary: Annotated[str, Field(min_length=1)]
    change: BeatChange


class WhyEventStep(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    eventId: EventId
    seq: Seq
    tLabel: TLabel
    summary: Annotated[str, Field(min_length=1)]
    actor: Actor
    forPlayer: bool | None = None
    """
    角色为玩家做的事；文档的例子只在 true 时给
    """


class WhyQuery(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    target: EventId | BeatId | RevealId | Literal["forecast"]
    """
    事件、节拍、关键时刻的 ID，或 forecast
    """


type WhyStep = Annotated[WhyEventStep | WhyBeatStep, Field(title="WhyStep")]
"""
因果链的一步：事件或节拍（2.6）
"""


class ActChooseMessage(BaseModel):
    """
    幕末选给定的去处（3.11）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    type: Literal["act_choose"] = "act_choose"
    clientMsgId: ClientMsgId
    optionId: ExitId | PlanOptionId
    """
    act_ended 的去处，或 act_plan_result 的替代去处
    """
    enRouteChoice: Annotated[int | None, Field(ge=0, le=1)] = None
    """
    过场二选一选的那一项的 index；不带 = 选最后一个（照原作）
    """


class ActOptionEnRoute(BaseModel):
    """
    过场里的二选一（3.11，契约 1.4）：choices 正好两个，最后一个是「照原作」
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    line: Annotated[str, Field(min_length=1)]
    choices: Annotated[list[EnRouteOption], Field(max_length=2, min_length=2)]


class ActProposeMessage(BaseModel):
    """
    幕末用文字说出自己的打算（3.11）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    type: Literal["act_propose"] = "act_propose"
    clientMsgId: ClientMsgId
    text: Text200


class ActionMessage(BaseModel):
    """
    身体动作，先判后演（3.8）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    type: Literal["action"] = "action"
    clientMsgId: ClientMsgId
    actionId: ActionId | None = None
    """
    快照 actions 里的动作带它；move 和「調べる」不带
    """
    kind: Literal[
        "examine", "give", "follow", "block", "help", "wait", "go", "shortcut", "run-together", "hasten", "move"
    ]
    """
    3.8 的清单：世界模型 Affordance.kind 加上 move
    """
    target: Annotated[str | None, Field(max_length=128, min_length=1)] = None
    """
    对象：人物 ID、地点 ID（move）或 interactable 的 ID。快照里这个动作有 target 就原样带；wait 这类没有对象的动作省略（服务端按 actionId 找回）。move、examine、go 必带（C-1 评审定）
    """
    params: Annotated[ActionMessageParams | None, Field(title="ActionMessageParams")] = None
    """
    give 时 params.item 是交出的物品
    """


class ActionResultMessage(BaseModel):
    """
    动作的判定结果（3.8）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    type: Literal["action_result"] = "action_result"
    clientMsgId: ClientMsgId
    status: Literal["done", "refused", "partial"]
    eventIds: list[EventId]
    narration: Annotated[str, Field(min_length=1)]
    """
    一句故事里的说明；拒绝也在故事里说
    """
    minutes: Minutes


class ActionsPatch(BaseModel):
    """
    commit.patch.actions（3.4）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    add: list[SituationalAction] | None = None
    remove: list[ActionId] | None = None


class ActivityEndMessage(BaseModel):
    """
    松开
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    type: Literal["activity_end"] = "activity_end"
    turnId: TurnId
    turnSeq: ClientTurnSeq


class ActivityStartMessage(BaseModel):
    """
    按下说话；人物正在说话时也是打断
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    type: Literal["activity_start"] = "activity_start"
    turnId: TurnId
    turnSeq: ClientTurnSeq
    purpose: Literal["act_plan"] | None = None
    """
    幕末说出打算（3.11）时给，其他情况省略
    """


class CharacterPresence(BaseModel):
    """
    当前场景在场的人物（2.3）；还没有关系的人物两个 relation 字段都省略
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    id: CharacterId
    place: PlaceId
    spot: Spot
    activity: Activity
    talkable: bool
    relationLabel: str | None = None
    """
    由 trust 区间映射（第 4 节的表）
    """
    relationLevel: Literal[1, 2, 3, 4, 5] | None = None
    """
    （1.5）同一区间的档位，接口里叫 relationLevel
    """


class CharacterPresencePatch(BaseModel):
    """
    commit.patch.characters[]（3.4）：按 id 合并，只给变了的字段。人物进场（之前不在当前场景）时带完整的 CharacterPresence 字段；离场就是 place 变成不在当前场景里的地点
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    id: CharacterId
    place: PlaceId | None = None
    spot: Spot | None = None
    activity: Activity | None = None
    talkable: bool | None = None
    relationLabel: str | None = None
    """
    由 trust 区间映射（第 4 节的表）
    """
    relationLevel: Literal[1, 2, 3, 4, 5] | None = None
    """
    （1.5）同一区间的档位，接口里叫 relationLevel
    """


class ConfirmAnswerMessage(BaseModel):
    """
    回答意图确认（3.9）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    type: Literal["confirm_answer"] = "confirm_answer"
    draftId: DraftId
    optionId: Annotated[str, Field(min_length=1)]


class ConfirmClosedMessage(BaseModel):
    """
    确认结束
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    type: Literal["confirm_closed"] = "confirm_closed"
    draftId: DraftId
    optionId: OptionId | None
    """
    null = 当作「不是」
    """
    by: Literal["button", "voice", "timeout"]


class ConfirmMessage(BaseModel):
    """
    意图确认（3.9）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    type: Literal["confirm"] = "confirm"
    draftId: DraftId
    character: CharacterId
    prompt: Annotated[str, Field(min_length=1)]
    options: Annotated[list[ConfirmOption], Field(min_length=2)]
    timeoutSec: Annotated[int, Field(ge=1)]


class Cue(BaseModel):
    """
    服务端在某个时刻触发的一句固定台词（3.4）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    kind: CueKind
    speaker: CharacterId | None
    """
    梅洛斯和玩家在同一个地点时是他；不在时为 null，text 按 narration 显示
    """
    text: Annotated[str, Field(min_length=1)]


class EndingView(BaseModel):
    """
    结局（2.8）：world → you → characters 三层
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    endingId: EndingId
    world: EndingWorldView
    you: EndingYouView
    characters: list[CharacterEnding]
    """
    （1.1，D-015、S-032）7 个可对话人物都在
    """
    card: EndingCardView
    """
    每一局都有（S-076，数据契约 1.6 第 5 节）：生成的结局取 rank 最前的 1〜3 人，一个也没排上名时放梅洛斯一句；模板尾声的局用 ux-design 11.4 那一组预写的句子
    """


class ErrorBody(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    code: ErrorCode
    message: Annotated[str, Field(min_length=1)]
    """
    可以直接给玩家看的日语短句
    """
    retryable: bool
    retryAfterSeconds: RetryAfterSeconds | None
    """
    rate_limited、daily_limit 时给
    """


class ErrorMessage(BaseModel):
    """
    不致命的错误（第 5 节的形状）；致命错误后服务端关闭连接
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    type: Literal["error"] = "error"
    error: ErrorBody


class ErrorResponse(BaseModel):
    """
    REST 的错误响应（第 5 节）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    error: ErrorBody
    activePlaythrough: ActivePlaythrough | None = None
    """
    只在 active_playthrough_exists（409）时给，同 /v1/me，放在 error 外面（C-1 评审定）
    """


class EventsQuery(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    afterSeq: LastSeq
    limit: Annotated[int | None, Field(ge=1, le=50)] = None


class HelloMessage(BaseModel):
    """
    连接后第一条；服务端补发 lastSeq 之后的 commit
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    type: Literal["hello"] = "hello"
    lastSeq: LastSeq
    clientVersion: Annotated[str, Field(max_length=64, min_length=1)]
    debug: bool | None = None
    """
    非生产：打开 event_rejected 调试消息
    """
    fakeVoice: bool | None = None
    """
    非生产：服务端用录好的音频回答，不调用 Live（第 7 节）
    """


class Interactable(BaseModel):
    """
    场景里可「調べる」的东西（2.3，estimatedMinutes 为 0）和场景出口（3.8）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    id: InteractableId
    kind: Literal["examine", "go"]
    """
    examine = 調べる；go = 场景出口（3.8）
    """
    spot: Spot
    label: Annotated[str, Field(min_length=1)]
    enabled: bool
    estimatedMinutes: Minutes


class InteractablesPatch(BaseModel):
    """
    commit.patch.interactables：可调查物和场景出口（3.8）的增减，形状同 actions。add 里的 id 已经有了就整条替换（例：enabled 变了）（C-1 评审加）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    add: list[Interactable] | None = None
    remove: list[InteractableId] | None = None


class LimitsMessage(BaseModel):
    """
    今天的语音时间剩 5 分钟时推一次
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    type: Literal["limits"] = "limits"
    voiceMinutesLeft: Minutes


class MeResponseLimits(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    runsToday: Annotated[int, Field(ge=0)]
    runsPerDay: Annotated[int, Field(ge=1)]
    voiceMinutesLeft: Minutes


class MeResponse(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    user: Annotated[MeResponseUser, Field(title="MeResponseUser")]
    limits: Annotated[MeResponseLimits, Field(title="MeResponseLimits")]
    activePlaythrough: ActivePlaythrough | None
    """
    没有进行中的局时为 null
    """


class MemoryBookCharacter(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    character: CharacterId
    relationLabel: str
    """
    由 trust 区间映射（第 4 节的表）
    """
    relationLevel: Literal[1, 2, 3, 4, 5]
    """
    （1.5）同一区间的档位，接口里叫 relationLevel
    """
    promises: list[PromiseView]
    didForYou: list[MemoryBookCharacterDidForYouItem]
    youDid: list[MemoryBookCharacterYouDidItem]
    memories: list[MemoryView]


class PlanAlternative(BaseModel):
    """
    说出的打算不成行时最接近的替代去处（3.11）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    optionId: PlanOptionId
    label: Annotated[str, Field(min_length=1)]
    sceneId: SceneId
    tLabel: TLabel


class PlayerPosition(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    roleId: RoleId
    place: PlaceId
    spot: Spot


class PlayerPositionPatch(BaseModel):
    """
    commit.patch.player（3.4）：只给变了的字段
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    place: PlaceId | None = None
    spot: Spot | None = None


class PrerecordedCues(BaseModel):
    """
    服务端在某个时刻触发的固定台词，键是 commit.cue.kind；没有就是空对象
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    arrival_capped: VoiceClip | None = None


class Prerecorded(BaseModel):
    """
    ux-design 16.2 的 6 句加固定台词（2.1）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    aizuchi: Annotated[list[VoiceClip], Field(max_length=3, min_length=3)]
    """
    相槌 3 句
    """
    unheard: Annotated[list[VoiceClip], Field(max_length=2, min_length=2)]
    """
    听不清 2 句
    """
    wait: VoiceClip
    cues: Annotated[PrerecordedCues, Field(title="PrerecordedCues")]
    """
    服务端在某个时刻触发的固定台词，键是 commit.cue.kind；没有就是空对象
    """


class Reveal(BaseModel):
    """
    关键时刻（3.4、3.4.1），直接带因果链
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    revealId: RevealId
    kind: Literal["beat", "eta", "ending", "favor"]
    """
    3.4.1 的四种
    """
    line: Annotated[str, Field(min_length=1)]
    chain: Annotated[list[WhyStep], Field(max_length=12)]
    collapsed: Annotated[int | None, Field(ge=1)] = None
    """
    链超过 12 步时中间折叠了几步，同 /why 的 collapsed（2.6）；没折叠时省略（C-1 评审加）
    """


class SnapshotPatch(BaseModel):
    """
    commit.patch（3.4）：快照字段的增量，按 id 合并。voice、status 不走 patch（C-1 评审定）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    clock: ClockPatch | None = None
    deadline: Deadline | None = None
    forecast: Forecast | None = None
    characters: list[CharacterPresencePatch] | None = None
    places: list[PlaceAccess] | None = None
    actions: ActionsPatch | None = None
    interactables: InteractablesPatch | None = None
    player: PlayerPositionPatch | None = None


class StagingCharacter(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    id: Literal["player"] | CharacterId
    """
    人物 ID，或 player（玩家也在里面）
    """
    state: StagingState


type TelemetryEvent = Annotated[
    TelemetryAppOpen
    | TelemetryMicPermission
    | TelemetryRoleSelected
    | TelemetrySceneReady
    | TelemetryWebVitals
    | TelemetryPerfSample
    | TelemetryQualityChanged
    | TelemetryGlContextLost
    | TelemetryTalkTurn
    | TelemetryTurnRetracted
    | TelemetryTranscriptCorrected
    | TelemetryConfirmAnswered
    | TelemetryApproachShown
    | TelemetryApproachEnded
    | TelemetryActPlanResult
    | TelemetrySonokoroViewed
    | TelemetryMapOpened
    | TelemetryWhyOpened
    | TelemetryMemoryBookOpened
    | TelemetryMemorySectionViewed
    | TelemetryMemoryDeleted
    | TelemetryAppResumed
    | TelemetryContinueStarted
    | TelemetryConnectionLost
    | TelemetryConnectionRestored
    | TelemetryEndingViewed
    | TelemetryEndingClosed
    | TelemetryEndingCardSaved
    | TelemetryEndingShared
    | TelemetryReplayStarted
    | TelemetryDegradedShown,
    Field(discriminator="name", title="TelemetryEvent"),
]
"""
一条遥测事件，按 name 区分（data-design 9.3）
"""


type VisibleEffect = Annotated[
    VisibleBeatEffect | VisibleVarEffect,
    Field(discriminator="kind", title="VisibleEffect"),
]
"""
玩家可见的变化（2.4）：StateVar.visibleToPlayer 的变量和节拍走向，label 可直接显示
"""


class VisibleEvent(BaseModel):
    """
    推给前端的事件：数据契约 Event 的玩家可见投影（2.4）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    eventId: EventId
    seq: Annotated[int, Field(ge=1)]
    """
    本局内严格递增，从 1 开始；重放按 seq
    """
    turnId: TurnId | None = None
    """
    来自哪一轮；到点的节拍、人物的打算这类事件没有，照数据契约 Event.turnId 可选（C-1 评审定）
    """
    t: StoryTime
    """
    发生时的故事时间；按 seq 不递减
    """
    dt: Annotated[int, Field(ge=0)]
    """
    这件事消耗的故事分钟；本事件之后时钟 = max(之前的时钟, t + dt)
    """
    tLabel: TLabel
    type: Literal["say", "action", "move", "beat", "learn", "act-transition", "correction", "ending", "forget"]
    actor: Actor
    forPlayer: bool
    """
    角色为玩家做的事（Event.beneficiary = player）
    """
    place: PlaceId
    summary: str
    """
    叙事者写的中性日语摘要：只写故事里的行为，不含玩家原话，不含现实个人信息
    """
    causes: list[EventId | BeatId]
    """
    因为哪些事件（ev_…）或节拍（beat.…）
    """
    visibleEffects: list[VisibleEffect]
    promise: PromiseChange | None
    keyMoment: bool
    """
    提交时算出，（1.1）按 S-041 的四条
    """
    supersedes: EventId | None
    """
    只有 type = correction 时有
    """


class WhyResponse(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    target: EventId | BeatId | RevealId | Literal["forecast"]
    """
    同 query 的 target
    """
    chain: Annotated[list[WhyStep], Field(max_length=12)]
    """
    按时间正序，最长 12 步
    """
    collapsed: Annotated[int, Field(ge=0)]
    """
    中间折叠了几步
    """


class ActOption(BaseModel):
    """
    幕末的一个去处（3.11，来自世界模型的 ActExit）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    optionId: ExitId
    label: Annotated[str, Field(min_length=1)]
    sceneId: SceneId
    tLabel: TLabel
    with_: Annotated[list[CharacterId], Field(alias="with")]
    because: Because | None
    enRoute: ActOptionEnRoute | None = None


class ActPlanResultMessage(BaseModel):
    """
    幕末说出的打算能不能成行（3.11）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    type: Literal["act_plan_result"] = "act_plan_result"
    clientMsgId: ClientMsgId | None = None
    """
    用文字说打算时：act_propose 的 clientMsgId。和 turnId 正好有一个（C-1 评审定）
    """
    turnId: TurnId | None = None
    """
    用声音说打算时（activity_start purpose = act_plan）：那一轮的 turnId，前端按它对上语音那一轮、丢掉已作废那一轮的结果（C-1 评审加）
    """
    accepted: bool
    narration: Annotated[list[NarrationItem], Field(min_length=1)]
    alternative: PlanAlternative | None = None
    triesLeft: Annotated[int, Field(ge=0, le=2)]


type ClientMessage = Annotated[
    HelloMessage
    | NearMessage
    | FarMessage
    | FocusMessage
    | UnfocusMessage
    | ActivityStartMessage
    | ActivityEndMessage
    | TextMessage
    | TurnRetractMessage
    | ActionMessage
    | ConfirmAnswerMessage
    | ApproachArrivedMessage
    | ApproachDismissMessage
    | ActChooseMessage
    | ActProposeMessage
    | SafetyResumeMessage
    | PingMessage,
    Field(discriminator="type", title="ClientMessage"),
]
"""
WebSocket 客户端 → 服务端的 JSON 消息（api-contract 3.2），按 type 区分
"""


class CommitMessage(BaseModel):
    """
    叙事者的一次提交，前端一次原子地应用（3.4）；覆盖 fromSeq〜seq（含两端）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    type: Literal["commit"] = "commit"
    fromSeq: Seq
    seq: Seq
    turnId: TurnId | None = None
    """
    没有 turnId 的 commit 来自到点的节拍、人物的打算、导演事件或幕切换
    """
    events: list[VisibleEvent]
    patch: SnapshotPatch
    memories: list[MemoryChange]
    promises: list[PromiseUpdate]
    narration: list[NarrationItem]
    cue: Cue | None
    reveal: Reveal | None


class EventsResponse(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    events: Annotated[list[VisibleEvent], Field(max_length=50)]
    lastSeq: LastSeq


class ManifestResponseCharactersItem(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    id: CharacterId
    name: Annotated[str, Field(min_length=1)]
    reading: Annotated[str, Field(min_length=1)]
    talkable: bool
    prerecorded: Prerecorded | None = None
    """
    声音定了以后才有（Q-004）；不能对话的人物没有
    """


class ManifestResponse(BaseModel):
    """
    不变的内容（2.1），构建时由世界模型和资源清单生成
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    manifestVersion: Annotated[str, Field(min_length=1)]
    book: Annotated[ManifestResponseBook, Field(title="ManifestResponseBook")]
    roles: Annotated[list[ManifestResponseRolesItem], Field(min_length=1)]
    scenes: Annotated[list[ManifestResponseScenesItem], Field(min_length=1)]
    characters: list[ManifestResponseCharactersItem]
    acts: list[ManifestResponseActsItem]
    clock: Annotated[ManifestResponseClock, Field(title="ManifestResponseClock")]
    ruby: list[ManifestResponseRubyItem]


class MemoriesResponse(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    characters: list[MemoryBookCharacter]


class Staging(BaseModel):
    """
    结局演出里谁在哪、什么状态（3.13）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    place: PlaceId
    characters: Annotated[list[StagingCharacter], Field(min_length=1)]


class TelemetryBatch(BaseModel):
    """
    POST /v1/telemetry 的请求体：一批 ≤ 50 条。不含音频、原话、记忆文本
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    common: TelemetryCommon
    events: Annotated[list[TelemetryEvent], Field(max_length=50, min_length=1)]


class ActEnd(BaseModel):
    """
    幕末的去处（3.11）；act_ended 和 pending.actEnd 同形
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    actId: ActId
    recapLines: Annotated[list[RecapLine], Field(max_length=4, min_length=2)]
    """
    「この幕であなたが動かしたこと」
    """
    options: Annotated[list[ActOption], Field(min_length=1)]
    freeform: Freeform


class ActEndedMessage(BaseModel):
    """
    幕结束，给出去处（3.11）；除 type 外和 ActEnd 同形
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    type: Literal["act_ended"] = "act_ended"
    actId: ActId
    recapLines: Annotated[list[RecapLine], Field(max_length=4, min_length=2)]
    options: Annotated[list[ActOption], Field(min_length=1)]
    freeform: Freeform


class EndingStartedMessage(BaseModel):
    """
    进入结局演出（3.13）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    type: Literal["ending_started"] = "ending_started"
    trigger: Literal["deadline", "story-closed"]
    staging: Staging


class Pending(BaseModel):
    """
    续玩时还没处理完的东西（第 4 节）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    reveal: Reveal | None
    confirm: PendingConfirm | None
    actEnd: ActEnd | None
    safetyPause: bool
    approach: PendingApproach | None


class Snapshot(BaseModel):
    """
    当前场景的世界投影（2.3），≤ 10 KB
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    playthroughId: PlaythroughId
    lastSeq: LastSeq
    status: Literal["active", "ended", "abandoned", "deleted"]
    actId: ActId
    sceneId: SceneId
    clock: SnapshotClock
    deadline: Deadline
    forecast: Forecast | None
    player: PlayerPosition
    places: list[PlaceAccess]
    characters: list[CharacterPresence]
    interactables: list[Interactable]
    actions: list[SituationalAction]
    pending: Pending
    voice: Voice


class WelcomeMessage(BaseModel):
    """
    回应 hello（第 4 节）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )
    type: Literal["welcome"] = "welcome"
    lastSeq: LastSeq
    voice: Voice
    lastTurn: LastTurn | None
    """
    这一局还没有对话时为 null
    """
    pending: Pending


class ActTransitionMessage(BaseModel):
    """
    进入下一幕：「その頃」（≤ 3 件）和新场景的快照（3.11）
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    type: Literal["act_transition"] = "act_transition"
    fromActId: ActId
    toActId: ActId
    recap: Annotated[list[RecapItem], Field(max_length=3)]
    snapshot: Snapshot


class CreatePlaythroughResponse(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        arbitrary_types_allowed=True,
    )
    playthroughId: PlaythroughId
    snapshot: Snapshot


type ServerMessage = Annotated[
    WelcomeMessage
    | SessionPreparingMessage
    | SessionReadyMessage
    | TurnStartedMessage
    | TranscriptMessage
    | InterruptedMessage
    | TurnCompleteMessage
    | SuggestionsMessage
    | TurnSettledMessage
    | CommitMessage
    | NarrationMessage
    | ConfirmMessage
    | ConfirmClosedMessage
    | ApproachMessage
    | ActionResultMessage
    | ActEndedMessage
    | ActPlanResultMessage
    | ActTransitionMessage
    | SafetyPauseMessage
    | SafetyHintMessage
    | SafetyResumedMessage
    | EndingStartedMessage
    | EndingReadyMessage
    | TurnRetractResultMessage
    | LimitsMessage
    | DegradedMessage
    | GoawayMessage
    | ErrorMessage
    | PongMessage
    | EventRejectedMessage,
    Field(discriminator="type", title="ServerMessage"),
]
"""
WebSocket 服务端 → 客户端的 JSON 消息（api-contract 3.3），按 type 区分
"""
