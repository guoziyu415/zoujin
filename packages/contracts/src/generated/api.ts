// 生成的文件，不要手改：改 packages/contracts/schemas/ 后跑 `uv run contracts-gen`。
import type * as Data from "./data";

/**
 * 前端生成的动作 ID（第 0 节「幂等」），例 UUID
 */
export type ClientMsgId = string;
/**
 * 幕末说出打算后的替代去处（3.11 alternative.optionId）：plan_ 加 ULID，和别的运行时 ID 一样（C-1 评审定）
 */
export type PlanOptionId = string;
/**
 * 玩家输入的文字，≤ 200 字（3.2）
 */
export type Text200 = string;
/**
 * 前端已应用的最后一个序号；还没有事件时为 0
 */
export type LastSeq = number;
/**
 * 场景里的位置点（第 0 节），前端在 3D 场景里定义，例 fountain-east
 */
export type Spot = string;
/**
 * 场景里可「調べる」的东西或场景出口（2.3），例 obj.market-stall
 */
export type InteractableId = string;
/**
 * 故事分钟数
 */
export type Minutes = number;
/**
 * 快照里情境动作的 ID（2.3），例 act_help_old-man_cart；服务端生成，前端原样回传
 */
export type ActionId = string;
/**
 * 关键时刻（3.4），rev_ 加 ULID（大写 Crockford base32，第一位 0〜7，同数据契约的运行时 ID）
 */
export type RevealId = string;
/**
 * 因果链的一步：事件或节拍（2.6）
 */
export type WhyStep = WhyEventStep | WhyBeatStep;
/**
 * 一局里的事件序号（2.4）
 */
export type Seq = number;
/**
 * 节拍的走向，和数据契约 Effect（op = beat）的 to 同一组值
 */
export type BeatChange = "happened" | "prevented" | "delayed" | "hastened" | "altered";
/**
 * 待确认的举动（3.9），draft_ 加 ULID（大写 Crockford base32，第一位 0〜7，同数据契约的运行时 ID）
 */
export type DraftId = string;
/**
 * 前端分配的 turnSeq（3.1）：每条连接从 1 起，最高位为 0
 */
export type ClientTurnSeq = number;
/**
 * 同源的静态资源路径（第 0 节「来源」），以 / 开头，文件名带 hash
 */
export type AssetPath = string;
/**
 * 书的 ID（manifest 路径里的 bookId），例 hashire-merosu
 */
export type BookId = string;
/**
 * WebSocket 客户端 → 服务端的 JSON 消息（api-contract 3.2），按 type 区分
 */
export type ClientMessage =
  | HelloMessage
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
  | ActLandedMessage
  | SafetyResumeMessage
  | PingMessage;
/**
 * 玩家可见的变化（2.4）：StateVar.visibleToPlayer 的变量和节拍走向，label 可直接显示
 */
export type VisibleEffect = VisibleBeatEffect | VisibleVarEffect;
/**
 * playerToCharacter = Promise.from 是 player；characterToPlayer = Promise.to 是 player
 */
export type PromiseDirection = "playerToCharacter" | "characterToPlayer";
/**
 * 固定台词的种类；也是 manifest 里 prerecorded.cues 的键
 */
export type CueKind = "arrival_capped";
/**
 * ux-design 11.1 的 8 个状态；前端遇到不认识的按 present 演
 */
export type StagingState =
  "present" | "in-crowd" | "on-cross" | "freed" | "arriving" | "approaching" | "collapsed" | "absent";
/**
 * 第 5 节的错误码，加第 1 节的 invalid_invite（登录 401）和 invalid_request（400：请求体、参数或 WebSocket 消息不合 Schema，是前端的毛病，不给玩家具体原因）（C-1 评审定）
 */
export type ErrorCode =
  | "invalid_request"
  | "unauthenticated"
  | "forbidden"
  | "not_found"
  | "invalid_invite"
  | "active_playthrough_exists"
  | "idempotency_conflict"
  | "rate_limited"
  | "daily_limit"
  | "voice_unavailable"
  | "invalid_choice"
  | "internal";
export type InputMode = "voice" | "text";
/**
 * 画质级（D-019）
 */
export type QualityLevel = "L0" | "L1" | "L2" | "L3";
/**
 * WebSocket 服务端 → 客户端的 JSON 消息（api-contract 3.3），按 type 区分
 */
export type ServerMessage =
  | WelcomeMessage
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
  | SetPieceMessage
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
  | EventRejectedMessage;
/**
 * 服务端发起的轮次的 turnSeq（3.1）：最高位为 1，从 0x80000001 起
 */
export type ServerTurnSeq = number;
/**
 * 说话的人：玩家或人物
 */
export type Speaker = "player" | Data.CharacterId;
/**
 * （v1.0.4）固定演出的一行（3.14）：世界模型的 SetPiece.lines 原样下发。narration = 一行地の文；speaker + line = 这个人物的一句预录，字幕就是 line
 */
export type SetPieceLine =
  | {
      /**
       * 一行地の文（日语）
       */
      narration: string;
    }
  | {
      speaker: Data.CharacterId;
      /**
       * 预录句，也是字幕（日语）
       */
      line: string;
    };
/**
 * （v1.0.4）manifest.setPieceVoices 的键：「{固定演出 ID}/{序号}」，序号从 1 起，例 piece.gate-taken/2
 */
export type SetPieceVoiceKey = string;
/**
 * 一条遥测事件，按 name 区分（data-design 9.3）
 */
export type TelemetryEvent =
  | TelemetryAppOpen
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
  | TelemetryDegradedShown;
export type TimelineItem = TimelineEventItem | TimelineBeatItem;
/**
 * 二进制帧和 turn 消息里的 turnSeq：uint32，前端分配的或服务端分配的
 */
export type TurnSeq = number;

/**
 * 幕末选给定的去处（3.11）
 */
export interface ActChooseMessage {
  type: "act_choose";
  clientMsgId: ClientMsgId;
  /**
   * act_ended 的去处，或 act_plan_result 的替代去处
   */
  optionId: Data.ExitId | PlanOptionId;
  /**
   * 过场二选一选的那一项的 index；不带 = 选最后一个（照原作）
   */
  enRouteChoice?: number;
}
/**
 * 幕末的去处（3.11）；act_ended 和 pending.actEnd 同形
 */
export interface ActEnd {
  actId: Data.ActId;
  /**
   * 「この幕であなたが動かしたこと」。玩家这一幕什么都没动时为空，前端显示 actEnd.summary.empty（v1.0.5 放宽，原来 2〜4 条）
   *
   * @minItems 0
   * @maxItems 4
   */
  recapLines: string[];
  /**
   * @minItems 1
   */
  options: ActOption[];
  freeform: Freeform;
}
/**
 * 幕末的一个去处（3.11，来自世界模型的 ActExit）
 */
export interface ActOption {
  optionId: Data.ExitId;
  label: string;
  sceneId: Data.SceneId;
  /**
   * （v1.0.13）这个去处通往的幕（世界模型 ActExit.toAct；打算是它落地的那一幕）：幕末页一出现就能预取下一幕的场景包。老的服务端不给
   */
  toActId?: Data.ActId;
  tLabel: Data.TLabel;
  /**
   * （v1.0.4）副题的前半「{地点}・{日子}の{时段}」（ux-design 4.4）：服务端算好，地点是落点的 Place.name，日子和时段是落点时刻（和 tLabel 同一个时刻）在 clock.labels 的 days、bands 里的叫法，中间用「の」，不套 clock.labels.format。例「刑場・三日目の夕方」
   */
  where: string;
  /**
   * （v1.0.4）副题的后半：世界模型的 ActExit.sub（≤ 16 字），没有就省略。例「西の門が見える所で」
   */
  sub?: string;
  with: Data.CharacterId[];
  because: string | null;
  enRoute?: ActOptionEnRoute;
}
/**
 * 过场里的二选一（3.11，契约 1.4）：choices 正好两个，最后一个是「照原作」
 */
export interface ActOptionEnRoute {
  line: string;
  /**
   * @minItems 2
   * @maxItems 2
   */
  choices: EnRouteOption[];
}
export interface EnRouteOption {
  /**
   * 在 choices 里的序号
   */
  index: number;
  label: string;
  /**
   * 最后一项（照原作）为 null
   */
  melosMinutes: number | null;
  /**
   * 不加时为 null
   */
  afterLine: string | null;
}
/**
 * 幕末能不能自己说打算（3.11），同一次幕末最多试 2 次
 */
export interface Freeform {
  allowed: boolean;
  triesLeft: number;
}
/**
 * 幕结束，给出去处（3.11）；除 type 外和 ActEnd 同形。每个去处带副题的前半 where 和后半 sub（v1.0.4）
 */
export interface ActEndedMessage {
  type: "act_ended";
  actId: Data.ActId;
  /**
   * 玩家这一幕什么都没动时为空（v1.0.5 放宽，原来 2〜4 条）
   *
   * @minItems 0
   * @maxItems 4
   */
  recapLines: string[];
  /**
   * @minItems 1
   */
  options: ActOption[];
  freeform: Freeform;
}
/**
 * （v1.0.4）幕切换以后落地（3.11）：act_transition.arrival（或 pending.arrival）带 opener 时，前端显示完落地那一行、玩家能动的时候发一次；服务端收到才让 opener 先开口。actId 不是现在这一幕的、同一幕再发的，服务端忽略
 */
export interface ActLandedMessage {
  type: "act_landed";
  actId: Data.ActId;
}
/**
 * 幕末说出的打算能不能成行（3.11）
 */
export interface ActPlanResultMessage {
  type: "act_plan_result";
  /**
   * 用文字说打算时：act_propose 的 clientMsgId。和 turnId 正好有一个（C-1 评审定）
   */
  clientMsgId?: ClientMsgId;
  /**
   * 用声音说打算时（activity_start purpose = act_plan）：那一轮的 turnId，前端按它对上语音那一轮、丢掉已作废那一轮的结果（C-1 评审加）
   */
  turnId?: Data.TurnId;
  accepted: boolean;
  /**
   * @minItems 1
   */
  narration: string[];
  alternative?: PlanAlternative;
  triesLeft: number;
}
/**
 * 说出的打算不成行时最接近的替代去处（3.11）
 */
export interface PlanAlternative {
  /**
   * 另一个打算（plan_…），或某个给定去处的 ID（v1.0.5 放宽）。前端照旧回 act_choose { optionId }
   */
  optionId: PlanOptionId | Data.ExitId;
  label: string;
  sceneId: Data.SceneId;
  /**
   * （v1.0.13）这个去处通往的幕（世界模型 ActExit.toAct；打算是它落地的那一幕）：幕末页一出现就能预取下一幕的场景包。老的服务端不给
   */
  toActId?: Data.ActId;
  tLabel: Data.TLabel;
}
/**
 * 幕末用文字说出自己的打算（3.11）
 */
export interface ActProposeMessage {
  type: "act_propose";
  clientMsgId: ClientMsgId;
  text: Text200;
}
/**
 * 进入下一幕：「その頃」（≤ 3 件）、新场景的快照和落地（3.11）
 */
export interface ActTransitionMessage {
  type: "act_transition";
  fromActId: Data.ActId;
  toActId: Data.ActId;
  /**
   * @maxItems 3
   */
  recap: RecapItem[];
  snapshot: Snapshot;
  /**
   * （v1.0.4）落地：第一行地の文 line 和先开口的人物 opener；去处（或成行的打算）没写 arrival 时省略。有 opener 时前端落地后发 act_landed
   */
  arrival?: Arrival;
}
/**
 * 「その頃」的一件（3.11）
 */
export interface RecapItem {
  eventId: Data.EventId;
  line: string;
  /**
   * 这件事是一个约定的兑现或违背时给
   */
  promise?: "kept" | "broken";
}
/**
 * 当前场景的世界投影（2.3），≤ 10 KB
 */
export interface Snapshot {
  playthroughId: Data.PlaythroughId;
  lastSeq: LastSeq;
  status: "active" | "ended" | "abandoned" | "deleted";
  actId: Data.ActId;
  sceneId: Data.SceneId;
  clock: SnapshotClock;
  deadline: Deadline;
  forecast: Forecast | null;
  player: PlayerPosition;
  places: PlaceAccess[];
  characters: CharacterPresence[];
  interactables: Interactable[];
  actions: SituationalAction[];
  pending: Pending;
  voice: Voice;
}
export interface SnapshotClock {
  t: Data.StoryTime;
  tLabel: Data.TLabel;
  deadlineT: Data.StoryTime;
}
/**
 * 期限（2.3）：玩家知道约定（契约 1.7 knows(player, fact.promise)）之前 shown = false、没有 line；之后一直 shown = true、带 line（S-077 ⑫，v1.0.3）
 */
export interface Deadline {
  shown: boolean;
  /**
   * 期限那一行，例「期限　三日目の日没／遅れれば、身代わりが死ぬ」
   */
  line?: string;
}
/**
 * 梅洛斯预计到达刑场的时刻（2.3）；玩家知道约定之前整个为 null（防剧透，条件和 Deadline.shown 一样）
 */
export interface Forecast {
  melosEtaT: Data.StoryTime;
  /**
   * false 时地图顶部写「このままでは、日没に間に合わない」
   */
  beforeDeadline: boolean;
}
export interface PlayerPosition {
  roleId: Data.RoleId;
  place: Data.PlaceId;
  spot: Spot;
}
export interface PlaceAccess {
  id: Data.PlaceId;
  /**
   * false 时前端提前把那条路挡住
   */
  enabled: boolean;
  /**
   * 进不去的理由，一句故事里的说明；只在 enabled = false 时给
   */
  reason?: string;
}
/**
 * 当前场景在场的人物（2.3）；还没有关系的人物两个 relation 字段都省略。group 的人物（群众、警吏）不占位置点，没有 spot（v1.0.4）
 */
export interface CharacterPresence {
  id: Data.CharacterId;
  place: Data.PlaceId;
  spot?: Spot;
  activity: Data.Activity;
  talkable: boolean;
  /**
   * （v1.0.4）一群人（契约 1.7 的 Character.group）：不占位置点，没有 spot，前端按地点成群地放（契约 3.1）
   */
  group?: true;
  /**
   * 由 trust 区间映射（第 4 节的表）
   */
  relationLabel?: string;
  /**
   * （1.5）同一区间的档位，接口里叫 relationLevel
   */
  relationLevel?: 1 | 2 | 3 | 4 | 5;
}
/**
 * 场景里可「調べる」的东西（2.3，estimatedMinutes 为 0）和场景出口（3.8）
 */
export interface Interactable {
  id: InteractableId;
  /**
   * examine = 調べる；go = 场景出口（3.8）
   */
  kind: "examine" | "go";
  spot: Spot;
  label: string;
  enabled: boolean;
  estimatedMinutes: Minutes;
}
/**
 * 此刻能做的情境动作（2.3、3.8）
 */
export interface SituationalAction {
  actionId: ActionId;
  kind: "examine" | "give" | "follow" | "block" | "help" | "wait" | "go" | "shortcut" | "run-together" | "hasten";
  /**
   * 对象人物；没有对象的动作（wait 这类，世界模型 Affordance.target 可选）省略，不给 null（C-1 评审定）
   */
  target?: Data.CharacterId;
  /**
   * 按钮上的动词短语（日语），不写耗时
   */
  label: string;
  estimatedMinutes: Minutes;
  /**
   * 第四幕对梅洛斯的影响（S-036、S-038）；没有为 null
   */
  melos: ("delay" | "hasten") | null;
  /**
   * 没有 melos 的动作为 null
   */
  melosMinutes: number | null;
  /**
   * 没有 melos 的动作为 null
   */
  melosInTime: boolean | null;
  enabled: boolean;
}
/**
 * 续玩时还没处理完的东西（第 4 节）
 */
export interface Pending {
  reveal: Reveal | null;
  confirm: PendingConfirm | null;
  actEnd: ActEnd | null;
  safetyPause: boolean;
  approach: PendingApproach | null;
  /**
   * （v1.0.4）幕切换以后还没落地：这一幕的 arrival 带 opener、服务端还没收到 act_landed 时给，和 act_transition.arrival 同形；没有时省略（3.11、第 4 节）
   */
  arrival?: Arrival;
}
/**
 * 关键时刻（3.4、3.4.1），直接带因果链
 */
export interface Reveal {
  revealId: RevealId;
  /**
   * 3.4.1 的四种
   */
  kind: "beat" | "eta" | "ending" | "favor";
  line: string;
  /**
   * @maxItems 12
   */
  chain: WhyStep[];
  /**
   * 链超过 12 步时中间折叠了几步，同 /why 的 collapsed（2.6）；没折叠时省略（C-1 评审加）
   */
  collapsed?: number;
}
export interface WhyEventStep {
  eventId: Data.EventId;
  seq: Seq;
  tLabel: Data.TLabel;
  summary: string;
  actor: Data.Actor;
  /**
   * 角色为玩家做的事；文档的例子只在 true 时给
   */
  forPlayer?: boolean;
}
export interface WhyBeatStep {
  beatId: Data.BeatId;
  tLabel: Data.TLabel;
  summary: string;
  change: BeatChange;
  /**
   * （v1.0.13）原作出处：世界模型 Beat.cite，只在这个节拍在时间线里会是 known 时带，原句带玩家此刻不知道的事实的剧透词的那条不出；没写出处或全过滤掉时省略（api-contract 2.5、2.6）
   *
   * @minItems 1
   */
  cite?: Data.Cite[];
}
/**
 * 续玩时还没回答的意图确认：confirm（3.9）的字段加剩余秒数 remainingSec（第 4 节「含剩余秒数」），timeoutSec 照样给（C-1 评审定）
 */
export interface PendingConfirm {
  draftId: DraftId;
  character: Data.CharacterId;
  prompt: string;
  /**
   * @minItems 2
   */
  options: ConfirmOption[];
  timeoutSec: number;
  remainingSec: number;
}
export interface ConfirmOption {
  /**
   * 例 yes、no
   */
  optionId: string;
  label: string;
}
/**
 * 续玩时正走过来的人物：和 approach（3.10）同形
 */
export interface PendingApproach {
  character: Data.CharacterId;
  kind: "request" | "news";
}
/**
 * （v1.0.4）幕切换的落地（3.11）：世界模型的 ActExit.arrival 或 Act.plan.arrival 原样下发
 */
export interface Arrival {
  /**
   * 落地后的第一行叙事（地の文，日语），跳转之后显示
   */
  line: string;
  /**
   * 落地后先开口的人物：服务端发起一轮，台词按人设生成，不是问句
   */
  opener?: Data.CharacterId;
}
/**
 * 语音状态（2.3、第 4 节 welcome）
 */
export interface Voice {
  enabled: boolean;
  degraded: boolean;
  minutesLeftToday: Minutes;
}
/**
 * 身体动作，先判后演（3.8）
 */
export interface ActionMessage {
  type: "action";
  clientMsgId: ClientMsgId;
  /**
   * 快照 actions 里的动作带它；move 和「調べる」不带
   */
  actionId?: ActionId;
  /**
   * 3.8 的清单：世界模型 Affordance.kind 加上 move
   */
  kind:
    "examine" | "give" | "follow" | "block" | "help" | "wait" | "go" | "shortcut" | "run-together" | "hasten" | "move";
  /**
   * 对象：人物 ID、地点 ID（move）或 interactable 的 ID。快照里这个动作有 target 就原样带；wait 这类没有对象的动作省略（服务端按 actionId 找回）。move、examine、go 必带（C-1 评审定）
   */
  target?: string;
  /**
   * give 时 params.item 是交出的物品
   */
  params?: {
    item?: Data.ItemId;
  };
}
/**
 * 动作的判定结果（3.8）
 */
export interface ActionResultMessage {
  type: "action_result";
  clientMsgId: ClientMsgId;
  status: "done" | "refused" | "partial";
  eventIds: Data.EventId[];
  /**
   * 一句故事里的说明；拒绝也在故事里说。这个动作挂着固定演出时没有（v1.0.4），和 setPiece 正好有一个
   */
  narration?: string;
  /**
   * （v1.0.4）这个动作挂着固定演出（契约 2.11 的 on.act）：它的 ID，紧接着推那条 set_piece（3.14），代替 narration
   */
  setPiece?: Data.SetPieceId;
  minutes: Minutes;
}
/**
 * commit.patch.actions（3.4）
 */
export interface ActionsPatch {
  add?: SituationalAction[];
  remove?: ActionId[];
}
/**
 * 进行中的局（1、2.2 的 409）
 */
export interface ActivePlaythrough {
  playthroughId: Data.PlaythroughId;
  roleId: Data.RoleId;
  roleName: string;
  actId: Data.ActId;
  tLabel: Data.TLabel;
  updatedAt: Data.RecordedAt;
}
/**
 * 松开
 */
export interface ActivityEndMessage {
  type: "activity_end";
  turnId: Data.TurnId;
  turnSeq: ClientTurnSeq;
}
/**
 * 按下说话；人物正在说话时也是打断
 */
export interface ActivityStartMessage {
  type: "activity_start";
  turnId: Data.TurnId;
  turnSeq: ClientTurnSeq;
  /**
   * 幕末说出打算（3.11）时给，其他情况省略
   */
  purpose?: "act_plan";
}
/**
 * 走过来的人物到了 2.5 m 内（3.10）
 */
export interface ApproachArrivedMessage {
  type: "approach_arrived";
  character: Data.CharacterId;
}
/**
 * 「いまは、いい」、走开，或等了 20 秒（3.10）
 */
export interface ApproachDismissMessage {
  type: "approach_dismiss";
  character: Data.CharacterId;
  reason: "dismissed" | "walked_away" | "timeout";
}
/**
 * 人物要走过来找你（3.10）
 */
export interface ApproachMessage {
  type: "approach";
  character: Data.CharacterId;
  kind: "request" | "news";
}
/**
 * commit.patch.characters[]（3.4）：按 id 合并，只给变了的字段。人物进场（之前不在当前场景）时带完整的 CharacterPresence 字段；离场就是 place 变成不在当前场景里的地点
 */
export interface CharacterPresencePatch {
  id: Data.CharacterId;
  place?: Data.PlaceId;
  spot?: Spot;
  activity?: Data.Activity;
  talkable?: boolean;
  /**
   * （v1.0.5）进场时和 CharacterPresence 一样带（一群人：不占位置点、没有 spot）
   */
  group?: true;
  /**
   * 由 trust 区间映射（第 4 节的表）
   */
  relationLabel?: string;
  /**
   * （1.5）同一区间的档位，接口里叫 relationLevel
   */
  relationLevel?: 1 | 2 | 3 | 4 | 5;
}
/**
 * 连接后第一条；服务端补发 lastSeq 之后的 commit
 */
export interface HelloMessage {
  type: "hello";
  lastSeq: LastSeq;
  clientVersion: string;
  /**
   * 非生产：打开 event_rejected 调试消息
   */
  debug?: boolean;
  /**
   * 非生产：服务端用录好的音频回答，不调用 Live（第 7 节）
   */
  fakeVoice?: boolean;
}
/**
 * 玩家进入某个可对话人物 8 m 内：服务端预热会话
 */
export interface NearMessage {
  type: "near";
  character: Data.CharacterId;
}
/**
 * 离开 12 m
 */
export interface FarMessage {
  type: "far";
  character: Data.CharacterId;
}
/**
 * 玩家点了这个人物
 */
export interface FocusMessage {
  type: "focus";
  character: Data.CharacterId;
}
/**
 * 离开对话
 */
export interface UnfocusMessage {
  type: "unfocus";
  reason: "walk_away" | "silence" | "menu" | "dismiss";
}
/**
 * 文字输入，代替一轮语音
 */
export interface TextMessage {
  type: "text";
  turnId: Data.TurnId;
  turnSeq: ClientTurnSeq;
  text: Text200;
  via: "typed" | "chip" | "correction";
  /**
   * 识别改正时被改正的那一轮（3.6）；只在 via = correction 时给
   */
  replaces?: Data.TurnId;
}
/**
 * 作废一轮（3.6）
 */
export interface TurnRetractMessage {
  type: "turn_retract";
  turnId: Data.TurnId;
}
/**
 * 回答意图确认（3.9）
 */
export interface ConfirmAnswerMessage {
  type: "confirm_answer";
  draftId: DraftId;
  optionId: string;
}
/**
 * 玩家在出戏卡上选了「物語に戻る」（3.12）
 */
export interface SafetyResumeMessage {
  type: "safety_resume";
}
/**
 * 每 20 秒一次
 */
export interface PingMessage {
  type: "ping";
}
/**
 * commit.patch.clock（3.4）：t、tLabel 必填，deadlineT 可选（C-1 评审定）
 */
export interface ClockPatch {
  t: Data.StoryTime;
  tLabel: Data.TLabel;
  deadlineT?: Data.StoryTime;
}
/**
 * 叙事者的一次提交，前端一次原子地应用（3.4）；覆盖 fromSeq〜seq（含两端）
 */
export interface CommitMessage {
  type: "commit";
  fromSeq: Seq;
  seq: Seq;
  /**
   * 没有 turnId 的 commit 来自到点的节拍、人物的打算、导演事件或幕切换
   */
  turnId?: Data.TurnId;
  events: VisibleEvent[];
  patch: SnapshotPatch;
  memories: MemoryChange[];
  promises: PromiseUpdate[];
  narration: string[];
  cue: Cue | null;
  reveal: Reveal | null;
}
/**
 * 推给前端的事件：数据契约 Event 的玩家可见投影（2.4）
 */
export interface VisibleEvent {
  eventId: Data.EventId;
  /**
   * 本局内严格递增，从 1 开始；重放按 seq
   */
  seq: number;
  /**
   * 来自哪一轮；到点的节拍、人物的打算这类事件没有，照数据契约 Event.turnId 可选（C-1 评审定）
   */
  turnId?: Data.TurnId;
  /**
   * 发生时的故事时间；按 seq 不递减
   */
  t: Data.StoryTime;
  /**
   * 这件事消耗的故事分钟；本事件之后时钟 = max(之前的时钟, t + dt)
   */
  dt: number;
  tLabel: Data.TLabel;
  type: "say" | "action" | "move" | "beat" | "learn" | "act-transition" | "correction" | "ending" | "forget";
  actor: Data.Actor;
  /**
   * 角色为玩家做的事（Event.beneficiary = player）
   */
  forPlayer: boolean;
  place: Data.PlaceId;
  /**
   * 叙事者写的中性日语摘要：只写故事里的行为，不含玩家原话，不含现实个人信息
   */
  summary: string;
  /**
   * 因为哪些事件（ev_…）或节拍（beat.…）
   */
  causes: (Data.EventId | Data.BeatId)[];
  visibleEffects: VisibleEffect[];
  promise: PromiseChange | null;
  /**
   * 提交时算出，（1.1）按 S-041 的四条
   */
  keyMoment: boolean;
  /**
   * 只有 type = correction 时有
   */
  supersedes: Data.EventId | null;
}
export interface VisibleBeatEffect {
  kind: "beat";
  beat: Data.BeatId;
  change: BeatChange;
  label: string;
}
/**
 * 变量这一种只给标签、不给原值（第 0 节）：kind、var、label（C-1 评审定）
 */
export interface VisibleVarEffect {
  kind: "var";
  var: Data.VarId;
  /**
   * StateVar.valueLabels 里这个取值的文字
   */
  label: string;
}
/**
 * 这个事件让一个约定成立、兑现、违背或作废（2.4）
 */
export interface PromiseChange {
  promiseId: Data.PromiseId;
  /**
   * 和数据契约 Effect（op = promise）的 change 同一组值
   */
  change: "made" | "kept" | "broken" | "voided";
}
/**
 * commit.patch（3.4）：快照字段的增量，按 id 合并。voice、status 不走 patch（C-1 评审定）
 */
export interface SnapshotPatch {
  clock?: ClockPatch;
  deadline?: Deadline;
  forecast?: Forecast | null;
  characters?: CharacterPresencePatch[];
  places?: PlaceAccess[];
  actions?: ActionsPatch;
  interactables?: InteractablesPatch;
  player?: PlayerPositionPatch;
}
/**
 * commit.patch.interactables：可调查物和场景出口（3.8）的增减，形状同 actions。add 里的 id 已经有了就整条替换（例：enabled 变了）（C-1 评审加）
 */
export interface InteractablesPatch {
  add?: Interactable[];
  remove?: InteractableId[];
}
/**
 * commit.patch.player（3.4）：只给变了的字段
 */
export interface PlayerPositionPatch {
  place?: Data.PlaceId;
  spot?: Spot;
}
/**
 * commit.memories[]（3.4）；前端据此让記憶帳的查询失效重拉。added、updated 必带 text 和 kind，deleted 不带（C-1 评审定）
 */
export interface MemoryChange {
  character: Data.CharacterId;
  change: "added" | "updated" | "deleted";
  memoryId: Data.MemoryId;
  /**
   * 角色视角的一句日语，給記憶帳显示；不含现实个人信息；删除后清空
   */
  text?: string;
  kind?: "promise" | "help" | "harm" | "shared-moment" | "claim" | "impression";
  /**
   * 由 trust 区间映射（第 4 节的表）
   */
  relationLabel: string;
  /**
   * （1.5）同一区间的档位，接口里叫 relationLevel
   */
  relationLevel: 1 | 2 | 3 | 4 | 5;
}
/**
 * commit.promises[]（3.4）
 */
export interface PromiseUpdate {
  promiseId: Data.PromiseId;
  character: Data.CharacterId;
  /**
   * 约定的内容（日语，中性，不是原话）
   */
  text: string;
  direction: PromiseDirection;
  /**
   * まだ / 果たされた / 破られた / 作废
   */
  status: "open" | "kept" | "broken" | "voided";
}
/**
 * 服务端在某个时刻触发的一句固定台词（3.4）
 */
export interface Cue {
  kind: CueKind;
  /**
   * 梅洛斯和玩家在同一个地点时是他；不在时为 null，text 按 narration 显示
   */
  speaker: Data.CharacterId | null;
  text: string;
}
/**
 * 确认结束
 */
export interface ConfirmClosedMessage {
  type: "confirm_closed";
  draftId: DraftId;
  /**
   * null = 当作「不是」
   */
  optionId: string | null;
  by: "button" | "voice" | "timeout";
}
/**
 * 意图确认（3.9）
 */
export interface ConfirmMessage {
  type: "confirm";
  draftId: DraftId;
  character: Data.CharacterId;
  prompt: string;
  /**
   * @minItems 2
   */
  options: ConfirmOption[];
  timeoutSec: number;
}
export interface CreatePlaythroughRequest {
  bookId: BookId;
  roleId: Data.RoleId;
}
export interface CreatePlaythroughResponse {
  playthroughId: Data.PlaythroughId;
  snapshot: Snapshot;
}
/**
 * 降级为文字回答
 */
export interface DegradedMessage {
  type: "degraded";
  voice: false;
  reason: "budget" | "service" | "daily";
}
/**
 * 结局卡（2.8）：Ending.card 加 fallbackImageUrl
 */
export interface EndingCardView {
  /**
   * 称号 ≤ 14 字
   */
  title: string;
  /**
   * 世界的去向 ≤ 26 字
   */
  subtitle: string;
  /**
   * （1.6 起 1〜3 人）影响最深的 1〜3 人，一个也没排上名时是梅洛斯一句（卡片按最多 3 行排）
   *
   * @minItems 1
   * @maxItems 3
   */
  characterLines: {
    character: Data.CharacterId;
    /**
     * ≤ 40 字
     */
    line: string;
  }[];
  /**
   * 「原作との違い」≤ 48 字
   */
  contrast: string;
  /**
   * 截帧失败时用的预画插画（每类底线结局一张）
   */
  fallbackImageUrl: AssetPath;
}
/**
 * 还没生成（202）
 */
export interface EndingPending {
  status: "pending";
  etaSeconds: number;
}
/**
 * 结局已生成，用 2.8 取
 */
export interface EndingReadyMessage {
  type: "ending_ready";
  endingId: Data.EndingId;
}
/**
 * 进入结局演出（3.13）
 */
export interface EndingStartedMessage {
  type: "ending_started";
  trigger: "deadline" | "story-closed";
  staging: Staging;
}
/**
 * 结局演出里谁在哪、什么状态（3.13）
 */
export interface Staging {
  place: Data.PlaceId;
  /**
   * @minItems 1
   */
  characters: StagingCharacter[];
}
export interface StagingCharacter {
  /**
   * 人物 ID，或 player（玩家也在里面）
   */
  id: "player" | Data.CharacterId;
  state: StagingState;
}
/**
 * 结局（2.8）：world → you → characters 三层
 */
export interface EndingView {
  endingId: Data.EndingId;
  world: EndingWorldView;
  you: EndingYouView;
  /**
   * （1.1，D-015、S-032）7 个可对话人物都在
   */
  characters: Data.CharacterEnding[];
  /**
   * 每一局都有（S-076，数据契约 1.6 第 5 节）：生成的结局取 rank 最前的 1〜3 人，一个也没排上名时放梅洛斯一句；模板尾声的局用 ux-design 11.4 那一组预写的句子
   */
  card: EndingCardView;
}
/**
 * 结局的世界层（2.8）。contrast 和数据契约一样可选
 */
export interface EndingWorldView {
  /**
   * variant?.id ?? outcome
   */
  outcomeId: string;
  /**
   * true = 5 类底线结局之一（没有 variant）
   */
  baseline: boolean;
  /**
   * variant?.title ?? title
   */
  title: string;
  /**
   * 每句至少引用一个事件
   */
  epilogue: {
    sentence: string;
    /**
     * 至少引用一个本局事件
     *
     * @minItems 1
     */
    cites: Data.EventId[];
  }[];
  /**
   * （1.1，S-026）「原作では…／あなたの世界では…」
   */
  contrast?: {
    original: string;
    yours: string;
    beat?: Data.BeatId;
  };
}
/**
 * 结局的「你」层（2.8）
 */
export interface EndingYouView {
  title: string;
  fate: string;
  /**
   * （1.1，D-012）人物为你做的事
   */
  didForYou: {
    sentence: string;
    /**
     * 至少引用一个本局事件
     *
     * @minItems 1
     */
    cites: Data.EventId[];
  }[];
  /**
   * （1.1）你为人物做的事
   */
  youDid: {
    sentence: string;
    /**
     * 至少引用一个本局事件
     *
     * @minItems 1
     */
    cites: Data.EventId[];
  }[];
}
export interface ErrorBody {
  code: ErrorCode;
  /**
   * 可以直接给玩家看的日语短句
   */
  message: string;
  retryable: boolean;
  /**
   * rate_limited、daily_limit 时给
   */
  retryAfterSeconds: number | null;
}
/**
 * 不致命的错误（第 5 节的形状）；致命错误后服务端关闭连接
 */
export interface ErrorMessage {
  type: "error";
  error: ErrorBody;
}
/**
 * REST 的错误响应（第 5 节）
 */
export interface ErrorResponse {
  error: ErrorBody;
  /**
   * 只在 active_playthrough_exists（409）时给，同 /v1/me，放在 error 外面（C-1 评审定）
   */
  activePlaythrough?: ActivePlaythrough;
}
/**
 * 非生产（hello.debug = true）：候选事件被否决
 */
export interface EventRejectedMessage {
  type: "event_rejected";
  turnId: Data.TurnId;
  /**
   * 被否决的候选事件，就是写进事件流的那条 rejected 事件：完整的 Event，check.status = rejected、effects 为空、dt = 0（数据契约第 3 节）。导演事件不过 3.2 节的规矩时直接丢掉，不发 event_rejected（C-1 评审定）
   */
  candidate: Data.Event;
  failedRules: (
    "R1-anchor" | "R2-precondition" | "R3-time" | "R4-knowledge" | "R5-persona" | "R6-safety" | "R7-capability"
  )[];
  reason: string;
}
export interface EventsQuery {
  afterSeq: LastSeq;
  limit?: number;
}
export interface EventsResponse {
  /**
   * @maxItems 50
   */
  events: VisibleEvent[];
  lastSeq: LastSeq;
}
/**
 * 服务端要关闭连接，前端按第 4 节重连
 */
export interface GoawayMessage {
  type: "goaway";
  reason: "deploy" | "maintenance";
  reconnectAfterMs: number;
}
/**
 * 服务端确认打断：人物还在说时被新的一轮打断。被打断的轮没有 turn_complete，照常交给叙事者（v1.0.3）
 */
export interface InterruptedMessage {
  type: "interrupted";
  turnId: Data.TurnId;
}
/**
 * 断线前的最后一轮（第 4 节）
 */
export interface LastTurn {
  turnId: Data.TurnId;
  /**
   * 和谁说的；幕末用声音说打算的一轮（activity_start purpose = act_plan）没有人物，为 null（C-1 评审定）
   */
  character: Data.CharacterId | null;
  /**
   * settled / pending（叙事者还在判）/ lost（断线时人物还没说完：不判、没有 turn_settled，v1.0.3）
   */
  status: "settled" | "pending" | "lost";
  /**
   * 原话已清空的轮次为 null
   */
  playerText: string | null;
  /**
   * 原话已清空、或人物的文字没收到时为 null
   */
  characterText: string | null;
}
/**
 * 今天的语音时间剩 5 分钟时推一次
 */
export interface LimitsMessage {
  type: "limits";
  voiceMinutesLeft: Minutes;
}
export interface LoginRequest {
  /**
   * 邀请码，不限格式（≤ 64 字），前端只去掉前后空格（C-1 评审定）
   */
  inviteCode: string;
}
export interface ManifestParams {
  bookId: BookId;
}
/**
 * 不变的内容（2.1），构建时由世界模型和资源清单生成
 */
export interface ManifestResponse {
  manifestVersion: string;
  book: {
    id: BookId;
    title: string;
    author: string;
  };
  /**
   * @minItems 1
   */
  roles: {
    roleId: Data.RoleId;
    name: string;
    summary: string;
    startSceneId: Data.SceneId;
    startActId: Data.ActId;
  }[];
  /**
   * @minItems 1
   */
  scenes: {
    sceneId: Data.SceneId;
    /**
     * @minItems 1
     */
    places: Data.PlaceId[];
    assetUrl: AssetPath;
    assetVersion: string;
  }[];
  /**
   * （v1.0.13）世界模型的全部地点和名字（Place.name），地图节点详情、幕末副题以外要显示地名的地方用。sceneId：地点所在的场景；没有场景、或场景不在 scenes 里（没有场景包）的地点为 null
   *
   * @minItems 1
   */
  places: {
    placeId: Data.PlaceId;
    name: string;
    sceneId: Data.SceneId | null;
  }[];
  characters: {
    id: Data.CharacterId;
    name: string;
    reading: string;
    talkable: boolean;
    /**
     * 声音定了以后才有（Q-004）；不能对话的人物没有
     */
    prerecorded?: Prerecorded;
  }[];
  acts: {
    actId: Data.ActId;
    title: string;
    /**
     * @minItems 1
     */
    sceneIds: Data.SceneId[];
  }[];
  clock: {
    deadlineT: Data.StoryTime;
    sunsetMinuteOfDay: number;
    /**
     * @minItems 1
     */
    days: string[];
  };
  ruby: {
    word: string;
    reading: string;
  }[];
  /**
   * （v1.0.4）固定演出里人物的预录句（2.1、3.14）。键「{固定演出 ID}/{序号}」，序号 = 这一句在那条固定演出 lines 里的位置（从 1 起，地の文也算）。构建时用这个人物的声音生成，不能对话的人物（警吏）也有；声音还没生成的句子没有键。没有固定演出时省略
   */
  setPieceVoices?: {
    [k: string]: VoiceClip | undefined;
  };
}
/**
 * ux-design 16.2 的 6 句加固定台词（2.1）
 */
export interface Prerecorded {
  /**
   * 相槌 3 句
   *
   * @minItems 3
   * @maxItems 3
   */
  aizuchi: VoiceClip[];
  /**
   * 听不清 2 句
   *
   * @minItems 2
   * @maxItems 2
   */
  unheard: VoiceClip[];
  wait: VoiceClip;
  /**
   * 服务端在某个时刻触发的固定台词，键是 commit.cue.kind；没有就是空对象
   */
  cues: {
    arrival_capped?: VoiceClip;
  };
}
/**
 * 一句预录台词（2.1）
 */
export interface VoiceClip {
  url: AssetPath;
  /**
   * 剧本原文，字幕用它（source = script）
   */
  text: string;
  /**
   * 实际音频长度
   */
  durationMs: number;
}
export interface MeResponse {
  user: {
    /**
     * 邀请码账号的匿名 ID（S-020），不是邮箱、不是姓名
     */
    userRef: string;
  };
  limits: {
    runsToday: number;
    runsPerDay: number;
    voiceMinutesLeft: Minutes;
  };
  /**
   * 没有进行中的局时为 null
   */
  activePlaythrough: ActivePlaythrough | null;
}
export interface MemoriesResponse {
  characters: MemoryBookCharacter[];
}
export interface MemoryBookCharacter {
  character: Data.CharacterId;
  /**
   * 由 trust 区间映射（第 4 节的表）
   */
  relationLabel: string;
  /**
   * （1.5）同一区间的档位，接口里叫 relationLevel
   */
  relationLevel: 1 | 2 | 3 | 4 | 5;
  promises: PromiseView[];
  didForYou: {
    eventId: Data.EventId;
    text: string;
  }[];
  youDid: {
    eventId: Data.EventId;
    text: string;
  }[];
  memories: MemoryView[];
}
/**
 * 記憶帳里的一条约定（2.7）。voided 照给，前端不显示
 */
export interface PromiseView {
  promiseId: Data.PromiseId;
  /**
   * 约定的内容（日语，中性，不是原话）
   */
  text: string;
  direction: PromiseDirection;
  /**
   * まだ / 果たされた / 破られた / 作废
   */
  status: "open" | "kept" | "broken" | "voided";
  /**
   * 约定成立的事件（Promise.madeBy）
   */
  eventId: Data.EventId;
}
/**
 * 記憶帳里的一条记忆（2.7）
 */
export interface MemoryView {
  memoryId: Data.MemoryId;
  kind: "promise" | "help" | "harm" | "shared-moment" | "claim" | "impression";
  /**
   * 角色视角的一句日语，給記憶帳显示；不含现实个人信息；删除后清空
   */
  text: string;
  t: Data.StoryTime;
  tLabel: Data.TLabel;
  /**
   * （1.1）見た / 聞いた / 噂で
   */
  via: "witnessed" | "told" | "rumor";
  promiseId: Data.PromiseId | null;
}
export interface MemoryDeleteResponse {
  memoryId: Data.MemoryId;
  deleted: true;
  character: Data.CharacterId;
  /**
   * 由 trust 区间映射（第 4 节的表）
   */
  relationLabel: string;
  /**
   * （1.5）同一区间的档位，接口里叫 relationLevel
   */
  relationLevel: 1 | 2 | 3 | 4 | 5;
  /**
   * 作废了约定时给它的 ID
   */
  promiseVoided: Data.PromiseId | null;
  sessionRebuilt: boolean;
}
export interface MemoryImpactResponse {
  /**
   * 没有就是 null
   */
  keeps: string | null;
  /**
   * true = 删除后这条记忆所属的约定变成 voided
   */
  voidsPromise: boolean;
}
export interface MemoryPathParams {
  id: Data.PlaythroughId;
  memoryId: Data.MemoryId;
}
/**
 * 不随事件的叙事一行（灰色地の文）
 */
export interface NarrationMessage {
  type: "narration";
  line: string;
  /**
   * 服务端内部的来源标记（例：节拍 ID、离题提示的规则名），只给日志和评测对照；前端不用、不显示（C-1 评审定）
   */
  ref?: string;
}
export interface PlaythroughPathParams {
  id: Data.PlaythroughId;
}
export interface PongMessage {
  type: "pong";
}
/**
 * 不暂停的小提示（S-069），一局最多一次
 */
export interface SafetyHintMessage {
  type: "safety_hint";
}
/**
 * 出戏卡（3.12）
 */
export interface SafetyPauseMessage {
  type: "safety_pause";
}
/**
 * 回到故事
 */
export interface SafetyResumedMessage {
  type: "safety_resumed";
}
/**
 * 回应 hello（第 4 节）
 */
export interface WelcomeMessage {
  type: "welcome";
  lastSeq: LastSeq;
  voice: Voice;
  /**
   * 这一局还没有对话时为 null
   */
  lastTurn: LastTurn | null;
  pending: Pending;
}
/**
 * 需要等待演出（人物转身、吸气）
 */
export interface SessionPreparingMessage {
  type: "session_preparing";
  character: Data.CharacterId;
  reason: "switch" | "rebuild" | "reconnect";
  etaMs: number;
}
/**
 * 这个人物可以说话了
 */
export interface SessionReadyMessage {
  type: "session_ready";
  character: Data.CharacterId;
  voiceAvailable: boolean;
}
/**
 * 服务端发起的一轮：人物先开口（3.9、3.10、3.11 的落地）
 */
export interface TurnStartedMessage {
  type: "turn_started";
  turnId: Data.TurnId;
  turnSeq: ServerTurnSeq;
  speaker: Data.CharacterId;
  /**
   * arrival（v1.0.4）= 幕切换落地后 opener 先开口（3.11）。approach、arrival 的一轮服务端把 speaker 当作已经 focus 的人物，前端不用另发 focus
   */
  reason: "approach" | "leaving" | "confirm" | "arrival";
}
/**
 * 字幕。人物每一轮恰好一条 final = true，没回答的轮、出戏卡停下的轮、一个字没说就被打断的轮除外；定稿可能晚于 turn_complete
 */
export interface TranscriptMessage {
  type: "transcript";
  turnId: Data.TurnId;
  speaker: Speaker;
  /**
   * 只有补转写也失败的人物定稿为 null
   */
  text: string | null;
  final: boolean;
  /**
   * 只在人物的 final = true 上给（S-071）
   */
  source?: "live" | "script" | "fallback";
}
/**
 * 人物这一轮说完；被打断的轮没有这条（v1.0.3）
 */
export interface TurnCompleteMessage {
  type: "turn_complete";
  turnId: Data.TurnId;
  /**
   * false = 人物这一轮没有出声，前端立即进入 no-response
   */
  audio: boolean;
  metrics: {
    /**
     * audio = false 时没有第一个音频分片，给 null（C-1 评审定）
     */
    serverReleaseToFirstAudioMs: number | null;
  };
}
/**
 * 候选话语 2〜3 个（3.5）；新的一条替换旧的
 */
export interface SuggestionsMessage {
  type: "suggestions";
  turnId?: Data.TurnId;
  character: Data.CharacterId;
  /**
   * @minItems 2
   * @maxItems 3
   */
  items: {
    text: string;
    kind: "ask" | "act" | "accept" | "decline";
  }[];
}
/**
 * 每一轮判完都推（3.4）；之后这一轮不能再作废
 */
export interface TurnSettledMessage {
  type: "turn_settled";
  turnId: Data.TurnId;
  outcome: "committed" | "no_change" | "rejected" | "retracted" | "no_response" | "paused";
  eventIds: Data.EventId[];
  minutes: Minutes;
}
/**
 * （v1.0.4）固定演出（3.14，契约 2.11）：写好的地の文和人物的预录句，按顺序演。不是事件，不占 seq，断线时没收到的不补发
 */
export interface SetPieceMessage {
  type: "set_piece";
  pieceId: Data.SetPieceId;
  /**
   * 人物的句子播 manifest 的 setPieceVoices["<pieceId>/<序号>"]（序号 = 在 lines 里的位置，从 1 起，地の文也算）
   *
   * @minItems 1
   */
  lines: SetPieceLine[];
}
/**
 * 「取り消す」「言い直す」的结果（3.6）
 */
export interface TurnRetractResultMessage {
  type: "turn_retract_result";
  turnId: Data.TurnId;
  status: "retracted" | "too_late";
}
export interface TelemetryActPlanResult {
  name: "act_plan_result";
  /**
   * 没有局时省略
   */
  playthroughId?: Data.PlaythroughId;
  /**
   * 真实时间：设备的钟，ISO 8601 UTC，以 Z 结尾（data-design 9.3）
   */
  clientTs: Data.RecordedAt;
  /**
   * 故事时间，有的话
   */
  t?: Data.StoryTime;
  props: {
    actId: Data.ActId;
    accepted: boolean;
    try: number;
    inputMode: InputMode;
  };
}
export interface TelemetryAppOpen {
  name: "app_open";
  /**
   * 没有局时省略
   */
  playthroughId?: Data.PlaythroughId;
  /**
   * 真实时间：设备的钟，ISO 8601 UTC，以 Z 结尾（data-design 9.3）
   */
  clientTs: Data.RecordedAt;
  /**
   * 故事时间，有的话
   */
  t?: Data.StoryTime;
  props: {
    entry: "direct" | "line" | "other";
    inAppBrowser: boolean;
  };
}
export interface TelemetryAppResumed {
  name: "app_resumed";
  /**
   * 没有局时省略
   */
  playthroughId?: Data.PlaythroughId;
  /**
   * 真实时间：设备的钟，ISO 8601 UTC，以 Z 结尾（data-design 9.3）
   */
  clientTs: Data.RecordedAt;
  /**
   * 故事时间，有的话
   */
  t?: Data.StoryTime;
  props: {
    awayMs: number;
    discarded: boolean;
    resumeMs: number;
    contextLost: boolean;
  };
}
export interface TelemetryApproachEnded {
  name: "approach_ended";
  /**
   * 没有局时省略
   */
  playthroughId?: Data.PlaythroughId;
  /**
   * 真实时间：设备的钟，ISO 8601 UTC，以 Z 结尾（data-design 9.3）
   */
  clientTs: Data.RecordedAt;
  /**
   * 故事时间，有的话
   */
  t?: Data.StoryTime;
  props: {
    character: Data.CharacterId;
    result: "talked" | "dismissed" | "walked_away";
  };
}
export interface TelemetryApproachShown {
  name: "approach_shown";
  /**
   * 没有局时省略
   */
  playthroughId?: Data.PlaythroughId;
  /**
   * 真实时间：设备的钟，ISO 8601 UTC，以 Z 结尾（data-design 9.3）
   */
  clientTs: Data.RecordedAt;
  /**
   * 故事时间，有的话
   */
  t?: Data.StoryTime;
  props: {
    character: Data.CharacterId;
  };
}
/**
 * POST /v1/telemetry 的请求体：一批 ≤ 50 条。不含音频、原话、记忆文本
 */
export interface TelemetryBatch {
  common: TelemetryCommon;
  /**
   * @minItems 1
   * @maxItems 50
   */
  events: TelemetryEvent[];
}
/**
 * 公共属性（data-design 9.3），只有粗粒度的设备信息；每批带一次，服务端入库时抄到这一批的每条（C-1 评审定）
 */
export interface TelemetryCommon {
  /**
   * 屏幕尺寸类：逻辑像素加 DPR，如 ios-390x844@3
   */
  deviceClass: string;
  os: string;
  /**
   * 含 App 内浏览器名
   */
  browser: string;
  appVersion: string;
}
export interface TelemetryMicPermission {
  name: "mic_permission";
  /**
   * 没有局时省略
   */
  playthroughId?: Data.PlaythroughId;
  /**
   * 真实时间：设备的钟，ISO 8601 UTC，以 Z 结尾（data-design 9.3）
   */
  clientTs: Data.RecordedAt;
  /**
   * 故事时间，有的话
   */
  t?: Data.StoryTime;
  props: {
    result: "granted" | "denied" | "unavailable";
    reason?: string;
    afterPrimer: boolean;
  };
}
export interface TelemetryRoleSelected {
  name: "role_selected";
  /**
   * 没有局时省略
   */
  playthroughId?: Data.PlaythroughId;
  /**
   * 真实时间：设备的钟，ISO 8601 UTC，以 Z 结尾（data-design 9.3）
   */
  clientTs: Data.RecordedAt;
  /**
   * 故事时间，有的话
   */
  t?: Data.StoryTime;
  props: {
    roleId: Data.RoleId;
  };
}
export interface TelemetrySceneReady {
  name: "scene_ready";
  /**
   * 没有局时省略
   */
  playthroughId?: Data.PlaythroughId;
  /**
   * 真实时间：设备的钟，ISO 8601 UTC，以 Z 结尾（data-design 9.3）
   */
  clientTs: Data.RecordedAt;
  /**
   * 故事时间，有的话
   */
  t?: Data.StoryTime;
  props: {
    sceneId: Data.SceneId;
    loadMs: number;
    /**
     * 点「はじめる」到能走（毫秒）
     */
    fromTap?: number;
  };
}
export interface TelemetryWebVitals {
  name: "web_vitals";
  /**
   * 没有局时省略
   */
  playthroughId?: Data.PlaythroughId;
  /**
   * 真实时间：设备的钟，ISO 8601 UTC，以 Z 结尾（data-design 9.3）
   */
  clientTs: Data.RecordedAt;
  /**
   * 故事时间，有的话
   */
  t?: Data.StoryTime;
  props: {
    lcp?: number;
    inp?: number;
    cls?: number;
    inpTarget?: string;
    loafScript?: string;
  };
}
export interface TelemetryPerfSample {
  name: "perf_sample";
  /**
   * 没有局时省略
   */
  playthroughId?: Data.PlaythroughId;
  /**
   * 真实时间：设备的钟，ISO 8601 UTC，以 Z 结尾（data-design 9.3）
   */
  clientTs: Data.RecordedAt;
  /**
   * 故事时间，有的话
   */
  t?: Data.StoryTime;
  props: {
    /**
     * 10 秒的帧时间直方图，固定 9 格，每格是帧数（data-design 9.3）。第 i 格数「上一格上界 < 帧时间 ≤ 这一格上界」的帧，上界依次是 8.5、12、17、20、26、34、51、101 ms，最后一格是 > 101 ms。边界都放在刷新间隔整数倍稍上，同一种掉帧不会拆到两格。格子固定，不同版本前端发来的直方图才能相加；要换边界就另起一个字段
     *
     * @minItems 9
     * @maxItems 9
     */
    frameTimeHistogram: number[];
    longTasks: number;
    jsHeapMb?: number;
    renderer: "webgl" | "webgpu";
    qualityLevel: QualityLevel;
    assetTier: "standard" | "high";
    dpr: number;
    drawCalls: number;
    lowPower: boolean;
  };
}
export interface TelemetryQualityChanged {
  name: "quality_changed";
  /**
   * 没有局时省略
   */
  playthroughId?: Data.PlaythroughId;
  /**
   * 真实时间：设备的钟，ISO 8601 UTC，以 Z 结尾（data-design 9.3）
   */
  clientTs: Data.RecordedAt;
  /**
   * 故事时间，有的话
   */
  t?: Data.StoryTime;
  props: {
    from?: QualityLevel;
    to: QualityLevel;
    reason: "start" | "down" | "up" | "lowPower" | "locked";
    /**
     * 起始档自测的一帧 GPU 耗时（ms），reason = start 时带；取到 0.1 ms（防设备指纹，data-design 9.3）
     */
    probeGpuMs?: number;
    assetMbps?: number;
  };
}
export interface TelemetryGlContextLost {
  name: "gl_context_lost";
  /**
   * 没有局时省略
   */
  playthroughId?: Data.PlaythroughId;
  /**
   * 真实时间：设备的钟，ISO 8601 UTC，以 Z 结尾（data-design 9.3）
   */
  clientTs: Data.RecordedAt;
  /**
   * 故事时间，有的话
   */
  t?: Data.StoryTime;
  props: {
    restored: boolean;
  };
}
export interface TelemetryTalkTurn {
  name: "talk_turn";
  /**
   * 没有局时省略
   */
  playthroughId?: Data.PlaythroughId;
  /**
   * 真实时间：设备的钟，ISO 8601 UTC，以 Z 结尾（data-design 9.3）
   */
  clientTs: Data.RecordedAt;
  /**
   * 故事时间，有的话
   */
  t?: Data.StoryTime;
  props: {
    turnId: Data.TurnId;
    character: Data.CharacterId;
    inputMode: InputMode;
    /**
     * 松手到听到声音（毫秒），和 turn_complete.metrics 按 turnId 对齐
     */
    clientReleaseToAudibleMs?: number;
    interrupted: boolean;
    noResponse: boolean;
  };
}
export interface TelemetryTurnRetracted {
  name: "turn_retracted";
  /**
   * 没有局时省略
   */
  playthroughId?: Data.PlaythroughId;
  /**
   * 真实时间：设备的钟，ISO 8601 UTC，以 Z 结尾（data-design 9.3）
   */
  clientTs: Data.RecordedAt;
  /**
   * 故事时间，有的话
   */
  t?: Data.StoryTime;
  props: {
    turnId: Data.TurnId;
    kind: "cancel" | "redo" | "timeout" | "correction";
    result: "retracted" | "too_late";
  };
}
export interface TelemetryTranscriptCorrected {
  name: "transcript_corrected";
  /**
   * 没有局时省略
   */
  playthroughId?: Data.PlaythroughId;
  /**
   * 真实时间：设备的钟，ISO 8601 UTC，以 Z 结尾（data-design 9.3）
   */
  clientTs: Data.RecordedAt;
  /**
   * 故事时间，有的话
   */
  t?: Data.StoryTime;
  props: {
    turnId: Data.TurnId;
  };
}
export interface TelemetryConfirmAnswered {
  name: "confirm_answered";
  /**
   * 没有局时省略
   */
  playthroughId?: Data.PlaythroughId;
  /**
   * 真实时间：设备的钟，ISO 8601 UTC，以 Z 结尾（data-design 9.3）
   */
  clientTs: Data.RecordedAt;
  /**
   * 故事时间，有的话
   */
  t?: Data.StoryTime;
  props: {
    answer: "yes" | "no" | "timeout";
  };
}
export interface TelemetrySonokoroViewed {
  name: "sonokoro_viewed";
  /**
   * 没有局时省略
   */
  playthroughId?: Data.PlaythroughId;
  /**
   * 真实时间：设备的钟，ISO 8601 UTC，以 Z 结尾（data-design 9.3）
   */
  clientTs: Data.RecordedAt;
  /**
   * 故事时间，有的话
   */
  t?: Data.StoryTime;
  props: {
    count: number;
    tappedMap: boolean;
  };
}
export interface TelemetryMapOpened {
  name: "map_opened";
  /**
   * 没有局时省略
   */
  playthroughId?: Data.PlaythroughId;
  /**
   * 真实时间：设备的钟，ISO 8601 UTC，以 Z 结尾（data-design 9.3）
   */
  clientTs: Data.RecordedAt;
  /**
   * 故事时间，有的话
   */
  t?: Data.StoryTime;
  props: {
    from: "hud" | "sonokoro" | "ending";
  };
}
export interface TelemetryWhyOpened {
  name: "why_opened";
  /**
   * 没有局时省略
   */
  playthroughId?: Data.PlaythroughId;
  /**
   * 真实时间：设备的钟，ISO 8601 UTC，以 Z 结尾（data-design 9.3）
   */
  clientTs: Data.RecordedAt;
  /**
   * 故事时间，有的话
   */
  t?: Data.StoryTime;
  props: {
    /**
     * 和 api-contract 2.6 /why 的 target 一一对应（data-design 9.3）：reveal = 关键时刻卡上的「なぜ」，forecast = 地图顶部「間に合わない」那一行的「なぜ」
     */
    target: "event" | "beat" | "reveal" | "forecast";
    fromKeyMoment: boolean;
  };
}
export interface TelemetryMemoryBookOpened {
  name: "memory_book_opened";
  /**
   * 没有局时省略
   */
  playthroughId?: Data.PlaythroughId;
  /**
   * 真实时间：设备的钟，ISO 8601 UTC，以 Z 结尾（data-design 9.3）
   */
  clientTs: Data.RecordedAt;
  /**
   * 故事时间，有的话
   */
  t?: Data.StoryTime;
  props: {};
}
export interface TelemetryMemorySectionViewed {
  name: "memory_section_viewed";
  /**
   * 没有局时省略
   */
  playthroughId?: Data.PlaythroughId;
  /**
   * 真实时间：设备的钟，ISO 8601 UTC，以 Z 结尾（data-design 9.3）
   */
  clientTs: Data.RecordedAt;
  /**
   * 故事时间，有的话
   */
  t?: Data.StoryTime;
  props: {
    section: "promises" | "didForYou" | "youDid" | "memories";
  };
}
export interface TelemetryMemoryDeleted {
  name: "memory_deleted";
  /**
   * 没有局时省略
   */
  playthroughId?: Data.PlaythroughId;
  /**
   * 真实时间：设备的钟，ISO 8601 UTC，以 Z 结尾（data-design 9.3）
   */
  clientTs: Data.RecordedAt;
  /**
   * 故事时间，有的话
   */
  t?: Data.StoryTime;
  props: {
    character: Data.CharacterId;
  };
}
export interface TelemetryContinueStarted {
  name: "continue_started";
  /**
   * 没有局时省略
   */
  playthroughId?: Data.PlaythroughId;
  /**
   * 真实时间：设备的钟，ISO 8601 UTC，以 Z 结尾（data-design 9.3）
   */
  clientTs: Data.RecordedAt;
  /**
   * 故事时间，有的话
   */
  t?: Data.StoryTime;
  props: {
    awayMs: number;
  };
}
export interface TelemetryConnectionLost {
  name: "connection_lost";
  /**
   * 没有局时省略
   */
  playthroughId?: Data.PlaythroughId;
  /**
   * 真实时间：设备的钟，ISO 8601 UTC，以 Z 结尾（data-design 9.3）
   */
  clientTs: Data.RecordedAt;
  /**
   * 故事时间，有的话
   */
  t?: Data.StoryTime;
  props: {
    reason: string;
  };
}
export interface TelemetryConnectionRestored {
  name: "connection_restored";
  /**
   * 没有局时省略
   */
  playthroughId?: Data.PlaythroughId;
  /**
   * 真实时间：设备的钟，ISO 8601 UTC，以 Z 结尾（data-design 9.3）
   */
  clientTs: Data.RecordedAt;
  /**
   * 故事时间，有的话
   */
  t?: Data.StoryTime;
  props: {
    downMs: number;
  };
}
export interface TelemetryEndingViewed {
  name: "ending_viewed";
  /**
   * 没有局时省略
   */
  playthroughId?: Data.PlaythroughId;
  /**
   * 真实时间：设备的钟，ISO 8601 UTC，以 Z 结尾（data-design 9.3）
   */
  clientTs: Data.RecordedAt;
  /**
   * 故事时间，有的话
   */
  t?: Data.StoryTime;
  props: {
    endingId: Data.EndingId;
    outcome: string;
  };
}
export interface TelemetryEndingClosed {
  name: "ending_closed";
  /**
   * 没有局时省略
   */
  playthroughId?: Data.PlaythroughId;
  /**
   * 真实时间：设备的钟，ISO 8601 UTC，以 Z 结尾（data-design 9.3）
   */
  clientTs: Data.RecordedAt;
  /**
   * 故事时间，有的话
   */
  t?: Data.StoryTime;
  props: {
    endingId: Data.EndingId;
    dwellMs: number;
  };
}
export interface TelemetryEndingCardSaved {
  name: "ending_card_saved";
  /**
   * 没有局时省略
   */
  playthroughId?: Data.PlaythroughId;
  /**
   * 真实时间：设备的钟，ISO 8601 UTC，以 Z 结尾（data-design 9.3）
   */
  clientTs: Data.RecordedAt;
  /**
   * 故事时间，有的话
   */
  t?: Data.StoryTime;
  props: {
    endingId: Data.EndingId;
  };
}
export interface TelemetryEndingShared {
  name: "ending_shared";
  /**
   * 没有局时省略
   */
  playthroughId?: Data.PlaythroughId;
  /**
   * 真实时间：设备的钟，ISO 8601 UTC，以 Z 结尾（data-design 9.3）
   */
  clientTs: Data.RecordedAt;
  /**
   * 故事时间，有的话
   */
  t?: Data.StoryTime;
  props: {
    endingId: Data.EndingId;
    completed?: boolean;
  };
}
export interface TelemetryReplayStarted {
  name: "replay_started";
  /**
   * 没有局时省略
   */
  playthroughId?: Data.PlaythroughId;
  /**
   * 真实时间：设备的钟，ISO 8601 UTC，以 Z 结尾（data-design 9.3）
   */
  clientTs: Data.RecordedAt;
  /**
   * 故事时间，有的话
   */
  t?: Data.StoryTime;
  props: {
    fromEndingId: Data.EndingId;
    roleId: Data.RoleId;
  };
}
export interface TelemetryDegradedShown {
  name: "degraded_shown";
  /**
   * 没有局时省略
   */
  playthroughId?: Data.PlaythroughId;
  /**
   * 真实时间：设备的钟，ISO 8601 UTC，以 Z 结尾（data-design 9.3）
   */
  clientTs: Data.RecordedAt;
  /**
   * 故事时间，有的话
   */
  t?: Data.StoryTime;
  props: {
    reason: "budget" | "service" | "daily";
  };
}
export interface TestAdvanceRequest {
  minutes: number;
}
export interface TimelineBeatItem {
  kind: "beat";
  beatId: Data.BeatId;
  t: Data.StoryTime;
  tLabel: Data.TLabel;
  title?: string;
  /**
   * canon = 数据契约 WorldState.beats 的 happened
   */
  status?: "canon" | "hastened" | "delayed" | "prevented" | "altered" | "pending";
  /**
   * 还没到、或玩家还不知道的节拍为 false，只给时刻
   */
  known: boolean;
  /**
   * （v1.0.13）原作出处：世界模型 Beat.cite（数据契约第 0 节的 Cite），地图节点详情列「原作」用。只在 known 时给；原句带玩家此刻不知道的事实的剧透词（spoilers()）的那条不出，世界模型里没写出处或全过滤掉时省略（api-contract 2.5）
   *
   * @minItems 1
   */
  cite?: Data.Cite[];
}
export interface TimelineEventItem {
  kind: "event";
  eventId: Data.EventId;
  t: Data.StoryTime;
  tLabel: Data.TLabel;
  summary: string;
  place: Data.PlaceId;
  style: "player" | "caused" | "character" | "system";
  causedByPlayer: boolean;
  forPlayer: boolean;
  /**
   * 只列玩家见过的人物
   */
  knownBy: Data.CharacterId[];
}
export interface TimelineResponse {
  days: {
    day: number;
    label: string;
    items: TimelineItem[];
  }[];
  lastSeq: LastSeq;
}
export interface WhyQuery {
  /**
   * 事件、节拍、关键时刻的 ID，或 forecast
   */
  target: Data.EventId | Data.BeatId | RevealId | "forecast";
}
export interface WhyResponse {
  /**
   * 同 query 的 target
   */
  target: Data.EventId | Data.BeatId | RevealId | "forecast";
  /**
   * 按时间正序，最长 12 步
   *
   * @maxItems 12
   */
  chain: WhyStep[];
  /**
   * 中间折叠了几步
   */
  collapsed: number;
}
