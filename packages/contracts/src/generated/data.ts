// 生成的文件，不要手改：改 packages/contracts/schemas/ 后跑 `uv run contracts-gen`。
/**
 * 幕：`act.` 加小写 slug（可以有 `.` 和 `-`）
 */
export type ActId = string;
/**
 * 故事时间 t：从 Day 0（约束之日）00:00 起算的故事分钟数（第 0 节）
 */
export type StoryTime = number;
/**
 * 节拍：`beat.` 加小写 slug（可以有 `.` 和 `-`）；节拍的变体也用这个前缀（`beat.25.v-no-doubt`）
 */
export type BeatId = string;
/**
 * 3D 场景：`scene.` 加小写 slug（可以有 `.` 和 `-`）
 */
export type SceneId = string;
/**
 * 幕末去处：`exit.` 加小写 slug（可以有 `.` 和 `-`）
 */
export type ExitId = string;
/**
 * 地点：`place.` 加小写 slug（可以有 `.` 和 `-`）
 */
export type PlaceId = string;
/**
 * 玩家身份：`role.` 加小写 slug（可以有 `.` 和 `-`）
 */
export type RoleId = string;
/**
 * 状态变量：`var.` 加 slug（可以有 `.` 和 `-`），段里可以用驼峰（`var.player.companionOf`、`var.player.knowsShortcut`、`var.melos.knowsTyranny`），第 0 节（1.6 写清）
 */
export type VarId = string;
/**
 * 效果：按 op 区分的 8 种（第 3 节）。事件、节拍结果、去处、情境动作、互助、期限规则共用
 */
export type Effect =
  | {
      op: "set";
      var: VarId;
      value: unknown;
      from?: unknown;
    }
  | {
      op: "inc";
      var: VarId;
      by: number;
    }
  | {
      op: "beat";
      beat: BeatId;
      to: "happened" | "prevented" | "delayed" | "hastened" | "altered";
      minutes?: number;
      /**
       * altered 时 = 改变后的结果（代替世界模型里的 outcomes）
       */
      outcomes?: Effect[];
      note?: string;
    }
  | {
      op: "learn";
      character: "player" | CharacterId;
      fact: FactId | RunFactId;
    }
  | {
      op: "relocate";
      character: CharacterId;
      place: PlaceId;
      /**
       * （1.7）站在这个地点的哪个位置点；省略 = 由后端按布局的站位规则排（第 3.1 节 WorldState.spots）
       */
      spot?: SpotId;
    }
  | {
      op: "promise";
      /**
       * 可选（1.6 契约第 3 节写清）：世界模型的效果模板（2.10）和候选事件（evals/s2/README.md）不写，提交时由叙事者分配 prm_…。提交的事件另外要求必带（Event.effects）
       */
      promiseId?: PromiseId;
      change: "made" | "kept" | "broken" | "voided";
      /**
       * change = made 时必填
       */
      from?: "player" | CharacterId;
      /**
       * change = made 时必填
       */
      to?: "player" | CharacterId;
      /**
       * change = made 时必填
       */
      text?: string;
      /**
       * 期限（时刻或节拍）
       */
      due?: {
        t?: StoryTime;
        beat?: BeatId;
      };
      /**
       * 模板 ID（可选）
       */
      template?: PromiseTemplateId;
    }
  | {
      op: "improv";
      factId: RunFactId;
      character: CharacterId;
      statement: string;
    }
  | {
      op: "hold";
      item: ItemId;
      /**
       * 新的持有者；null = 被拿走、用掉
       */
      to: "player" | CharacterId | null;
      from?: "player" | CharacterId | null;
    };
/**
 * 人物：`char.` 加小写 slug（可以有 `.` 和 `-`）
 */
export type CharacterId = string;
/**
 * 事实：`fact.` 加小写 slug（可以有 `.` 和 `-`）
 */
export type FactId = string;
/**
 * 本局即兴设定（1.1）：`rf_` 加 ULID（26 位 Crockford base32，大写）
 */
export type RunFactId = string;
/**
 * （1.7）场景布局里的位置点（api-contract 第 0 节 spot，assets/scenes/<场景>/layout.json 的 spots），小写 slug，例 stake-front、way.castle。不带类型前缀：名字由前端在布局里定
 */
export type SpotId = string;
/**
 * 约定（1.1）：`prm_` 加 ULID（26 位 Crockford base32，大写）
 */
export type PromiseId = string;
/**
 * 约定模板（1.1）：`promise.` 加小写 slug（可以有 `.` 和 `-`）
 */
export type PromiseTemplateId = string;
/**
 * 物品（1.1）：`item.` 加小写 slug（可以有 `.` 和 `-`）
 */
export type ItemId = string;
/**
 * （1.1）人物此刻在做什么，同 api-contract 2.3；前端不认识的按 idle（2.4）
 */
export type Activity = "idle" | "walk" | "run" | "talk" | "work" | "sleep" | "absent";
/**
 * 事件是谁做的（不是谁写的，写入方永远是叙事者）：player 玩家，system 按时间表自然发生，narrator 只用于 correction，或人物 ID（第 0 节）
 */
export type Actor = ("player" | "system" | "narrator") | CharacterId;
/**
 * 情境动作（1.1）：`aff.` 加小写 slug（可以有 `.` 和 `-`）
 */
export type AffordanceId = string;
/**
 * 互助（1.1）：`aid.` 加小写 slug（可以有 `.` 和 `-`）
 */
export type AidId = string;
/**
 * 因果边：`edge.` 加小写 slug（可以有 `.` 和 `-`）
 */
export type EdgeId = string;
/**
 * 事件：`ev_` 加 ULID（26 位 Crockford base32，大写）
 */
export type EventId = string;
/**
 * 写入时的契约版本（第 0 节「版本」）。1.5 冻结，以后只做加法，每个新版本往这里加一个值。1.6：StateVar.valueRequires（C-16）、结局卡 1〜3 人。1.7：位置点（relocate 和 ActExit 的 spot、WorldState.spots）、Character.group、ActExit.arrival / sub、Affordance.playerSpot（C-18）、Act.plan（C-19）、WorldModel.setPieces（S-080 ④）、WorldModel.objects。1.8：Affordance.pastLabel，事件 summary 里玩家一律写身份名
 */
export type SchemaVersion = "1.0" | "1.1" | "1.2" | "1.3" | "1.4" | "1.5" | "1.6" | "1.7" | "1.8";
/**
 * 结局：`end_` 加 ULID（26 位 Crockford base32，大写）
 */
export type EndingId = string;
/**
 * 一局：`pt_` 加 ULID（26 位 Crockford base32，大写）
 */
export type PlaythroughId = string;
/**
 * 真实时间，ISO 8601 UTC，以 Z 结尾（第 0 节）。只用于审计和分析，不参与故事逻辑。用 pattern 校验，不靠 format
 */
export type RecordedAt = string;
/**
 * 世界结局的底线类 ID，不带前缀的小写短横线 slug，如 `canon-reunion`
 */
export type WorldEndingId = string;
/**
 * 记忆：`mem_` 加 ULID（26 位 Crockford base32，大写）
 */
export type MemoryId = string;
/**
 * 一轮：`turn_` 加 ULID（26 位 Crockford base32，大写）
 */
export type TurnId = string;
/**
 * 一句话：`utt_` 加 ULID（26 位 Crockford base32，大写）
 */
export type UtteranceId = string;
/**
 * （1.7）可调查物：`obj.` 加小写 slug（可以有 `.` 和 `-`）
 */
export type ObjectId = string;
/**
 * 全局规则（globalRules）：`rule.` 加小写 slug（可以有 `.` 和 `-`）
 */
export type RuleId = string;
/**
 * （1.7）固定演出：`piece.` 加小写 slug（可以有 `.` 和 `-`）
 */
export type SetPieceId = string;
/**
 * 时间的说法，按世界模型的 clock.labels 生成，如「約束の日・夜」（第 0 节）
 */
export type TLabel = string;

/**
 * 幕（2.8，S-004）
 */
export interface Act {
  id: ActId;
  order: number;
  title: string;
  /**
   * 本幕最早从什么时候开始
   */
  start: {
    t: StoryTime;
  };
  end: {
    /**
     * 这些节拍任一有了结果就收幕
     */
    onBeats: BeatId[];
    /**
     * 最迟在这个时间收幕
     */
    atLatest: StoryTime;
  };
  /**
   * 本幕可能用到的场景（前端据此预加载）
   */
  scenes: SceneId[];
  /**
   * 幕末去处；最后一幕为空，收幕即进入结局
   */
  exits: ActExit[];
  /**
   * （1.7，C-19）玩家在幕末说出的打算成行时落在哪里（2.8.1 第 2 步）：成行的事件按这里写下一幕、地点、时间、落点和落地。省略 = 叙事者按世界模型判（M3 定）
   */
  plan?: {
    toAct: ActId;
    /**
     * 下一幕的起点
     */
    place: PlaceId;
    /**
     * 下一幕从几点开始
     */
    t: StoryTime;
    /**
     * 玩家落在 place 的哪个位置点；省略 = 这个地点的起点（startSpots）
     */
    spot?: SpotId;
    /**
     * 成行本身固定的效果（例：人物的 relocate）；打算自己的效果由叙事者从玩家的话里提取，照常检查后加在同一条事件上
     */
    effects: Effect[];
    /**
     * 落地，同 ActExit.arrival
     */
    arrival?: {
      /**
       * 落地后的第一行叙事（地の文，日语），跳转之后显示
       */
      line: string;
      /**
       * 落地后先开口的人物：服务端发起一轮，台词按人设生成，不是问句
       */
      opener?: CharacterId;
    };
  };
  inferred: true;
  note?: string;
}
/**
 * 幕末推荐去处（2.8）
 */
export interface ActExit {
  id: ExitId;
  /**
   * 玩家看到的选项（日语）
   */
  label: string;
  toAct: ActId;
  /**
   * 下一幕的起点
   */
  place: PlaceId;
  /**
   * 下一幕从几点开始
   */
  t: StoryTime;
  /**
   * 跟着某个节拍走：该节拍本局被推迟/提前多少，t 就平移多少
   */
  alignTo?: BeatId;
  /**
   * 只对这些身份开放；省略 = 全部
   */
  roles?: RoleId[];
  /**
   * 收幕时的状态要满足
   */
  requires?: Condition[];
  /**
   * 选择本身的效果
   */
  effects: Effect[];
  /**
   * （1.4）跳过的这段路上有一个能改的节拍时，过场页给一个二选一
   */
  enRoute?: EnRoute;
  /**
   * （1.7）幕末页上这个去处副题的后半（日语，叙事口吻，不写分钟数）；前半「{地点}・{日子}の{时段}」由服务端按 place 的 Place.name 和 t 算好（日子、时段照 clock.labels，不套它的 format），和后半一起下发（ux-design 4.4）。省略 = 只有前半
   */
  sub?: string;
  /**
   * （1.7）玩家落在 place 的哪个位置点；省略 = 前端按这个地点的起点（layout.json 的 startSpots）
   */
  spot?: SpotId;
  /**
   * （1.7）落地：第一行叙事和先开口的人物（ux/slice/jump-transition.md「落地」）
   */
  arrival?: {
    /**
     * 落地后的第一行叙事（地の文，日语），跳转之后显示
     */
    line: string;
    /**
     * 落地后先开口的人物：服务端发起一轮，台词按人设生成，不是问句
     */
    opener?: CharacterId;
  };
}
/**
 * 条件：引用 stateVars（2.4）。节拍前提、变体、去处、情境动作、世界结局共用
 */
export interface Condition {
  var: VarId;
  op: "==" | "!=" | ">=" | "<=" | "in";
  value: unknown;
  inferred?: true;
  /**
   * 原文没写、为游戏设计的前提的说明
   */
  note?: string;
}
/**
 * （1.4）过场里的二选一（2.8）
 */
export interface EnRoute {
  /**
   * 跳过的这段里能改的节拍
   */
  beat: BeatId;
  /**
   * 过场页上叙事的一句（日语）
   */
  line: string;
  /**
   * 正好两个；最后一个是「照原作」，effects 为空
   *
   * @minItems 2
   * @maxItems 2
   */
  choices: EnRouteChoice[];
  inferred: true;
  note?: string;
  cite?: Cite[];
}
/**
 * （1.5）过场二选一的一个选项（2.8）
 */
export interface EnRouteChoice {
  /**
   * 按钮上的动词（日语），不写分钟数
   */
  label: string;
  effects: Effect[];
  /**
   * （1.5）effects 里有改节拍的一条时必填：梅洛斯到刑场早（−）晚（+）几分钟
   */
  melosMinutes?: number;
  /**
   * （1.5）选了这一项，进下一幕之前过场页再多一句（日语）
   */
  after?: string;
}
/**
 * 原文出处，可以被机器校验（第 0 节）
 */
export interface Cite {
  /**
   * 原文版本 ID，如 "aozora:1567_ruby_4948@sha256:2a437c047d7f"（对规范化全文求哈希）
   */
  source: string;
  /**
   * 规范化文本里的段落号，从 1 开始
   */
  para: number;
  /**
   * 原文片段，≤ 80 字。必须是该段的精确子串（跨字段的规矩，由 build_world 校验，不在 Schema 里）
   */
  quote: string;
}
/**
 * （1.1）情境动作（2.10）
 */
export interface Affordance {
  id: AffordanceId;
  kind: "examine" | "give" | "follow" | "block" | "help" | "wait" | "go" | "shortcut" | "run-together" | "hasten";
  /**
   * 按钮上的动词短语（日语），不写耗时
   */
  label: string;
  /**
   * （1.8）做完以后的事件句（日语，过去式，带对象，不带主语和「。」），例「老爺を家まで送った」。叙事者写成 summary「{Role.name}は、{pastLabel}」，下发给玩家时服务端换成「あなた」
   */
  pastLabel: string;
  /**
   * 在哪个地点出现
   */
  place: PlaceId;
  /**
   * 只在这一幕
   */
  act?: ActId;
  /**
   * 只对这些身份；省略 = 全部
   */
  roles?: RoleId[];
  /**
   * 对象人物
   */
  target?: CharacterId;
  /**
   * kind = give 时必填：交出的物品
   */
  item?: ItemId;
  /**
   * 玩家花的故事时间（= 事件的 dt）
   */
  minutes: number;
  /**
   * 第四幕对梅洛斯的影响
   */
  melos?: "delay" | "hasten";
  /**
   * （1.4）有 melos 时必填：梅洛斯到刑场会晚（+）或早（−）几分钟
   */
  melosMinutes?: number;
  /**
   * 出现条件
   */
  when?: Condition[];
  /**
   * 做成了就兑现这条互助（fromYou 的 MutualAid.id）
   */
  aid?: AidId;
  /**
   * （1.7）做完以后玩家站在 place 的哪个位置点（布局的 spots）；省略 = 不挪。只管玩家，人物用 relocate 的 spot
   */
  playerSpot?: SpotId;
  /**
   * 效果模板：判定通过时提交的效果；空 = 只影响关系
   */
  effects: Effect[];
  inferred: true;
  note?: string;
  cite?: Cite[];
}
/**
 * 情节节拍（2.4）
 */
export interface Beat {
  id: BeatId;
  /**
   * 原著顺序（可以有小数，插在两个节拍之间）
   */
  order: number;
  title: string;
  summary: string;
  /**
   * 故事分钟；原著发生在 canonical；最晚 latest 之后就不可能再发生
   */
  window: {
    earliest: StoryTime;
    latest: StoryTime;
    canonical: StoryTime;
  };
  place: PlaceId;
  participants: CharacterId[];
  /**
   * anchor：不能被阻止或改写；mutable：可被提前、推迟、阻止或改变结果
   */
  kind: "anchor" | "mutable";
  /**
   * 发生前提，引用 stateVars
   */
  preconditions: Condition[];
  /**
   * 原著里发生后对状态的影响
   */
  outcomes: Effect[];
  /**
   * （1.1）节拍发生后这个人物在做什么
   */
  activities?: {
    character: CharacterId;
    activity: Activity;
  }[];
  /**
   * （1.4）到点发生时，按这一局的状态换成另一种演法
   */
  variants?: BeatVariant[];
  cite: Cite[];
}
/**
 * （1.4，S-064）节拍到点发生时按这一局的状态换的另一种演法（2.4）
 */
export interface BeatVariant {
  /**
   * 如 "beat.25.v-no-doubt"
   */
  id: BeatId;
  /**
   * 节拍到点、前提成立时，按顺序取第一个 when 全满足的变体
   */
  when: Condition[];
  /**
   * 这一局的演法（日语）
   */
  summary: string;
  /**
   * 代替节拍的 outcomes
   */
  outcomes: Effect[];
  inferred: true;
  note?: string;
  cite?: Cite[];
}
/**
 * 因果边（2.5）
 */
export interface CausalEdge {
  id: EdgeId;
  /**
   * beat 或 stateVar
   */
  from: BeatId | VarId;
  /**
   * beat 或 stateVar
   */
  to: BeatId | VarId;
  type: "enables" | "requires" | "prevents" | "delays" | "hastens";
  /**
   * （1.1）只用于 enables / requires；默认 shift
   */
  timeLink?: "shift" | "order";
  /**
   * delays / hastens 必填：from 发生会让 to 推迟（提前）几分钟
   */
  minutes?: number;
  /**
   * 为什么有这条边（日语）
   */
  note: string;
  /**
   * 原文能直接支持时给出处
   */
  cite?: Cite[];
  /**
   * 原文没明说、由人推断的为 true
   */
  inferred: boolean;
}
/**
 * 人物（2.1）
 */
export interface Character {
  id: CharacterId;
  name: string;
  reading?: string;
  /**
   * 一两句，中性描述
   */
  summary: string;
  /**
   * 性格，每条有出处
   */
  traits: {
    text: string;
    cite: Cite[];
    /**
     * 从该节拍发生起才用（1.1）
     */
    since?: BeatId;
    /**
     * 该节拍发生后不再用（1.1）
     */
    until?: BeatId;
    /**
     * 此刻的 WorldState 满足这些条件才用（1.4）；since / until / when 同时写时三者都要满足
     */
    when?: Condition[];
  }[];
  /**
   * 动机（= S-030 的「当下目标」）
   */
  goals: {
    text: string;
    cite: Cite[];
    /**
     * 从该节拍发生起才用（1.1）
     */
    since?: BeatId;
    /**
     * 该节拍发生后不再用（1.1）
     */
    until?: BeatId;
    /**
     * 此刻的 WorldState 满足这些条件才用（1.4）；since / until / when 同时写时三者都要满足
     */
    when?: Condition[];
  }[];
  /**
   * 说话方式，给角色 Agent 和评测用
   */
  speech: {
    /**
     * 「私」「わし」…
     */
    firstPerson?: string;
    register: string;
    /**
     * 原文台词，直接引用
     *
     * Items: 原文台词，直接引用。契约写作 Cite & { since?, until?, when? }：这里写成关死的普通对象，source / para / quote 用 JSON 指针引 Cite 的字段（约束只有一份），不用 allOf，生成的类型也是关死的
     */
    sampleLines: {
      /**
       * 原文版本 ID，如 "aozora:1567_ruby_4948@sha256:2a437c047d7f"（对规范化全文求哈希）
       */
      source: string;
      /**
       * 规范化文本里的段落号，从 1 开始
       */
      para: number;
      /**
       * 原文片段，≤ 80 字。必须是该段的精确子串（跨字段的规矩，由 build_world 校验，不在 Schema 里）
       */
      quote: string;
      /**
       * 从该节拍发生起才用（1.1）
       */
      since?: BeatId;
      /**
       * 该节拍发生后不再用（1.1）
       */
      until?: BeatId;
      /**
       * 此刻的 WorldState 满足这些条件才用（1.4）；since / until / when 同时写时三者都要满足
       */
      when?: Condition[];
    }[];
    /**
     * （1.4）原文没有、为游戏写的示例台词
     */
    designLines?: DesignLine[];
  };
  /**
   * 知道哪个 fact，从哪个 beat 起
   */
  knows: {
    fact: FactId;
    /**
     * "pre" = 故事开始前就知道
     */
    since: BeatId | "pre";
  }[];
  initialPlace: PlaceId;
  /**
   * 第一版能不能自由对话（S-003）
   */
  talkable: boolean;
  /**
   * （1.7）一群人（群众、警吏、山贼、一团旅人）：不占布局的位置点，前端按地点成群地放（站位规则见第 3.1 节 WorldState.spots）
   */
  group?: true;
  /**
   * 声音配置的引用，具体值由后端/UX 管
   */
  voiceRef?: string;
  /**
   * （1.1）开局在做什么（默认 idle）
   */
  initialActivity?: Activity;
  /**
   * （1.3）开局带在身上的物品（portable 的 Item ID）
   */
  items?: ItemId[];
  cite: Cite[];
  /**
   * （1.1）互助：他能为你做的、你能为他做的
   */
  mutualAid?: MutualAid[];
  /**
   * （1.1）这个人物常见的约定
   */
  promiseTemplates?: PromiseTemplate[];
  /**
   * （1.1）每一幕「没人管时的打算」
   */
  plans?: {
    act: ActId;
    text: string;
    inferred?: true;
    cite?: Cite[];
  }[];
}
/**
 * （1.4）原文没有、为游戏写的示例台词（2.1）
 */
export interface DesignLine {
  /**
   * 日语一句。角色提示里和 sampleLines 一样当示例用，不逐字照念
   */
  text: string;
  /**
   * 从该节拍发生起才用（1.1）
   */
  since?: BeatId;
  /**
   * 该节拍发生后不再用（1.1）
   */
  until?: BeatId;
  /**
   * 此刻的 WorldState 满足这些条件才用（1.4）；since / until / when 同时写时三者都要满足
   */
  when?: Condition[];
  inferred: true;
  /**
   * 什么场合说
   */
  note?: string;
  /**
   * 依据的原文
   */
  cite?: Cite[];
}
/**
 * （1.1）互助：他能为你做的、你能为他做的（2.1）
 */
export interface MutualAid {
  id: AidId;
  /**
   * forYou = 他能为你做的；fromYou = 你能为他做的
   */
  direction: "forYou" | "fromYou";
  /**
   * 日语一句，给叙事者和角色提示用，不直接显示给玩家
   */
  text: string;
  /**
   * 只在这些条件下才可能
   */
  when?: Condition[];
  /**
   * 这一条是该身份第一幕的「开局互助」（S-048）
   */
  opening?: RoleId;
  /**
   * 只用于 forYou：兑现时算关键时刻（S-041）
   */
  major?: true;
  /**
   * （1.3）只用于 forYou：兑现时人物交给你的物品
   */
  gives?: ItemId;
  /**
   * （1.4）兑现时提交的效果模板（同 Affordance.effects）
   */
  effects?: Effect[];
  inferred: true;
  /**
   * 有原文依据时给出处
   */
  cite?: Cite[];
}
/**
 * （1.1）这个人物常见的约定；叙事者写 promise 效果时引用（2.1）
 */
export interface PromiseTemplate {
  id: PromiseTemplateId;
  /**
   * 谁许下的；另一方是模板所属的人物（by 是人物自己时，另一方是玩家）
   */
  by: "player" | CharacterId;
  /**
   * 约定的内容（日语），如「必ず戻る」
   */
  text: string;
  inferred?: true;
  cite?: Cite[];
  /**
   * （1.4）语气、什么场合
   */
  note?: string;
}
/**
 * （1.1）每个可对话人物的结局（第 5 节）
 */
export interface CharacterEnding {
  character: CharacterId;
  /**
   * 受影响深浅，从 1 起；unchanged 时 null
   */
  rank: number | null;
  /**
   * 玩家没碰过、世界变化也没波及到：只显示「原作どおり」，不生成句子
   */
  unchanged: boolean;
  /**
   * 原作里他的结局，一句（日语）
   */
  original?: string;
  /**
   * 1〜3 句，「あなたの世界では」；unchanged 时省略
   *
   * @minItems 1
   * @maxItems 3
   */
  yours?: {
    sentence: string;
    /**
     * 至少引用一个本局事件
     *
     * @minItems 1
     */
    cites: EventId[];
  }[];
}
/**
 * 自检结果（第 3 节）
 */
export interface CheckResult {
  status: "passed" | "rewritten" | "downgraded" | "rejected";
  /**
   * 共尝试几次（改写上限 2 次，即最多 3）
   */
  attempts: number;
  failedRules: (
    "R1-anchor" | "R2-precondition" | "R3-time" | "R4-knowledge" | "R5-persona" | "R6-safety" | "R7-capability"
  )[];
  /**
   * 给「なぜこうなった？」和评审看的一句日语
   */
  reason?: string;
  /**
   * 自检用的模型/规则版本
   */
  checker: string;
}
/**
 * 时钟：开局时间、期限、时段叫法（2.6）
 */
export interface Clock {
  /**
   * 默认开局时间（各身份见 Role.startT）
   */
  startT: StoryTime;
  deadline: {
    t: StoryTime;
    /**
     * 如「三日目の日没」
     */
    label: string;
    cite: Cite[];
    /**
     * （1.1）决定赶不赶得上的节拍
     */
    watchBeat?: BeatId;
    /**
     * （1.4，S-066）watchBeat 最早的时刻
     */
    earliestArrival?: StoryTime;
    /**
     * （1.5，S-066 ①）本局第一次到下限时说一次的话
     */
    earliestArrivalCue?: {
      speaker: CharacterId;
      line: string;
      narration: string;
      inferred: true;
      note?: string;
    };
  };
  /**
   * 日没是几点；默认 1140（19:00）
   */
  sunsetMinuteOfDay: number;
  /**
   * 到期限时自动执行（actor: "system"）；所有 if 都按期限那一刻的状态判断
   */
  onDeadline: {
    if: Condition[];
    then: Effect[];
    note: string;
    cite: Cite[];
  }[];
  /**
   * tLabel 的生成规则
   */
  labels: {
    /**
     * 下标 = Day（S-037）
     */
    days: string[];
    /**
     * 一天内的时段起点（分钟）和叫法，如 [1140,"日没"]；从 0 开始严格递增
     */
    bands: [number, string][];
    /**
     * （1.1）模板，含 {day} 和 {band}
     */
    format: string;
    inferred: true;
    note?: string;
    /**
     * （1.1）时段叫法的原文依据
     */
    cite?: Cite[];
  };
}
/**
 * 结局（第 5 节）。1.6 起写入的结局，world.title、player.didForYou / youDid（可以是空数组）、characters、card 必写
 */
export interface Ending {
  schemaVersion: SchemaVersion;
  endingId: EndingId;
  playthroughId: PlaythroughId;
  worldModelVersion: string;
  /**
   * story-closed = 最后一幕的收幕节拍有了结果
   */
  trigger: "deadline" | "story-closed" | "abandoned";
  t: StoryTime;
  decidedAt: RecordedAt;
  world: {
    /**
     * WorldModel.endings.world[].id（底线类）
     */
    outcome: WorldEndingId;
    /**
     * 日语
     */
    summary: string;
    /**
     * 和原著不同的节拍，各自指回事件
     */
    changedBeats: {
      beat: BeatId;
      to: string;
      causedBy: EventId[];
    }[];
    finalVars: {
      [k: string]: unknown | undefined;
    };
    /**
     * （1.1）世界结局的一句标题。1.6 起必写：模板尾声的局写世界模型 endings.world 里这一类的 label（api-contract 2.8 的 world.title）
     */
    title?: string;
    /**
     * （1.1，S-031 ①）这一局生成的世界结局；没有 = 就是底线类本身
     */
    variant?: {
      /**
       * 本局内唯一，如 "gen.king-abdicates"（API 的 outcomeId）
       */
      id: string;
      title: string;
      summary: string;
      /**
       * 它主张的最终状态，必须和 finalVars 一致
       */
      claims: {
        var: VarId;
        value: unknown;
      }[];
      /**
       * 至少 2 个本局事件（「讲得通」）
       *
       * @minItems 2
       */
      causedBy: EventId[];
    };
    /**
     * （1.1）按 endings.signature 算出的署名（2.9.1）：变量 → 最终值，节拍 → 是否照原著发生
     */
    signature?: {
      [k: string]: unknown | undefined;
    };
    /**
     * （1.1，S-026）「原作では…／あなたの世界では…」
     */
    contrast?: {
      original: string;
      yours: string;
      beat?: BeatId;
    };
  };
  player: {
    /**
     * 顾问、人质、同行者、目击者、被处刑…
     */
    fate: {
      id: string;
      label: string;
      /**
       * @minItems 1
       */
      causedBy: EventId[];
    };
    relationships: {
      character: CharacterId;
      /**
       * 初值 + 未删除记忆的 trustDelta 之和，截断到 -100..100
       */
      trust: number;
      label: string;
      line?: string;
      memoryIds: MemoryId[];
    }[];
    /**
     * 如「王に信を説いた旅人」
     */
    title: {
      text: string;
      /**
       * @minItems 1
       */
      causedBy: EventId[];
    };
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
      cites: EventId[];
    }[];
    lastScene: {
      place: PlaceId;
      description: string;
      /**
       * （1.1）结局演出里在场的人物（S-053）
       */
      present?: CharacterId[];
    };
    /**
     * （1.1，D-012）人物为你做的事
     */
    didForYou?: {
      sentence: string;
      /**
       * 至少引用一个本局事件
       *
       * @minItems 1
       */
      cites: EventId[];
    }[];
    /**
     * （1.1）你为人物做的事
     */
    youDid?: {
      sentence: string;
      /**
       * 至少引用一个本局事件
       *
       * @minItems 1
       */
      cites: EventId[];
    }[];
  };
  /**
   * （1.1，D-015、S-032）7 个可对话人物都在
   */
  characters?: CharacterEnding[];
  /**
   * （1.1，S-049、S-051）结局卡，字数由这里保证。1.6 起每一局都生成：生成的结局取 rank 最前的 1〜3 人，一个也没排上名时放梅洛斯一句（按他的 original）；校验两次不过、改用模板尾声的局，字段取 ux-design 11.4 对应那一组的预写句子
   */
  card?: {
    /**
     * 称号 ≤ 14 字
     */
    title: string;
    /**
     * 世界的去向 ≤ 26 字
     */
    subtitle: string;
    /**
     * 「原作との違い」≤ 48 字
     */
    contrast: string;
    /**
     * （1.6 起 1〜3 人）影响最深的 1〜3 人，一个也没排上名时是梅洛斯一句（卡片按最多 3 行排）
     *
     * @minItems 1
     * @maxItems 3
     */
    characterLines: {
      character: CharacterId;
      /**
       * ≤ 40 字
       */
      line: string;
    }[];
  };
  /**
   * 生成产物的存储引用
   */
  share?: {
    cardImageRef?: string;
    videoRef?: string;
    branchTreeRef?: string;
  };
}
/**
 * （1.1）结局署名：什么叫「世界结局实质不同」（2.9.1）
 */
export interface EndingSignature {
  /**
   * 这些变量的最终值
   */
  vars: VarId[];
  /**
   * 这些节拍是否照原著发生
   */
  beats: BeatId[];
  inferred: true;
  note?: string;
}
/**
 * 运行时事件，只追加（第 3 节）。叙事者是唯一写入方
 */
export interface Event {
  schemaVersion: SchemaVersion;
  eventId: EventId;
  playthroughId: PlaythroughId;
  /**
   * 本局内严格递增，从 1 开始；重放按 seq
   */
  seq: number;
  /**
   * 来自哪一轮；system 事件没有
   */
  turnId?: TurnId;
  /**
   * 同一轮提交重试时不重复写（后端生成，靠它去重，不能是空串）
   */
  idempotencyKey: string;
  worldModelVersion: string;
  /**
   * 发生时的故事时间；按 seq 不递减
   */
  t: StoryTime;
  /**
   * 这件事消耗的故事分钟；本事件之后时钟 = max(之前的时钟, t + dt)
   */
  dt: number;
  recordedAt: RecordedAt;
  actor: Actor;
  type: "say" | "action" | "move" | "beat" | "learn" | "act-transition" | "correction" | "ending" | "forget";
  /**
   * （1.1）事件从哪来；只给评测、Trace 和「その頃」排序，不推前端
   */
  origin?: "turn" | "action" | "schedule" | "plan" | "director" | "act" | "memory";
  /**
   * （1.1）这件事是为谁做的
   */
  beneficiary?: "player" | CharacterId;
  /**
   * （1.1）提交前经过故事里的意图确认（S-040）
   */
  confirmed?: true;
  place: PlaceId;
  /**
   * 叙事者写的中性日语摘要：只写故事里的行为，不含玩家原话，不含现实个人信息
   */
  summary: string;
  /**
   * 相关原话（可删除；删除后这里保留 ID 但内容取不到）
   */
  utteranceRefs?: UtteranceId[];
  /**
   * 因为哪些事件（ev_…）或节拍（beat.…）
   */
  causes: (EventId | BeatId)[];
  /**
   * 提交的事件里 promise 效果必须带 promiseId（见 Effect 的 promise 分支）
   */
  effects: Effect[];
  /**
   * 提交时算出，（1.1）按 S-041 的四条
   */
  keyMoment: boolean;
  check: CheckResult;
  /**
   * 只用于 type=correction：修正哪一条事件
   */
  supersedes?: EventId;
  /**
   * 只用于 type=act-transition（actor=player）和过场二选一的 action 事件
   */
  exitId?: ExitId;
  /**
   * （1.2，S-031 ③）只用于 type=act-transition（actor=player）且玩家说出了自己的打算
   */
  plan?: {
    /**
     * 叙事者的日语转述；不逐字引用玩家原话
     */
    label: string;
    toAct: ActId;
    place: PlaceId;
    /**
     * 不早于 Act.start.t
     */
    t: StoryTime;
    /**
     * 同行的人物
     */
    with?: CharacterId[];
  };
}
/**
 * 事实（2.3）
 */
export interface Fact {
  id: FactId;
  /**
   * 中性陈述（日语）
   */
  statement: string;
  /**
   * 从哪个 beat 起成立；"pre" = 开场前已成立
   */
  trueFrom: BeatId | "pre";
  /**
   * public：在场的人都会知道；private：只有 knows 里的人知道
   */
  visibility: "public" | "private";
  /**
   * 说出这个事实时常用的词和别名（日语）
   */
  spoilerTerms?: string[];
  cite: Cite[];
}
/**
 * （1.1）故事里的物品（2.10）
 */
export interface Item {
  id: ItemId;
  /**
   * 日语
   */
  name: string;
  /**
   * 在这些地点随手可得；能带在身上的物品写 []
   */
  at: PlaceId[];
  /**
   * （1.3）一件实物：同一时刻只在一个人手里
   */
  portable?: true;
  inferred: true;
  note?: string;
  cite?: Cite[];
}
/**
 * 角色对玩家的记忆，可删除（第 4 节）。只由已提交的事件生成
 */
export interface MemoryItem {
  schemaVersion: SchemaVersion;
  memoryId: MemoryId;
  playthroughId: PlaythroughId;
  /**
   * 谁记得
   */
  character: CharacterId;
  kind: "promise" | "help" | "harm" | "shared-moment" | "claim" | "impression";
  /**
   * 角色视角的一句日语，給記憶帳显示；不含现实个人信息；删除后清空
   */
  text: string;
  /**
   * 来自哪些事件；记忆只由已提交的事件生成（第 4 节），所以至少一个
   *
   * @minItems 1
   */
  fromEvents: EventId[];
  t: StoryTime;
  /**
   * 这条记忆对信任的影响，-20..+20
   */
  trustDelta: number;
  /**
   * 0..1，检索排序用
   */
  salience: number;
  /**
   * （1.1）見た / 聞いた / 噂で
   */
  via?: "witnessed" | "told" | "rumor";
  /**
   * （1.1）这条记忆属于哪个约定
   */
  promiseId?: PromiseId;
  createdAt: RecordedAt;
  /**
   * 删除后：text 清空，只留 ID 和删除时间（审计用）
   */
  deletedAt?: RecordedAt;
}
/**
 * 地点（2.2）
 */
export interface Place {
  id: PlaceId;
  name: string;
  description: string;
  /**
   * 步行分钟；跑步等节奏由叙事者按系数换算
   */
  adjacent: {
    place: PlaceId;
    travelMinutes: number;
    inferred?: boolean;
  }[];
  /**
   * 有河的地点
   */
  crossing?: {
    bridgeMinutes: number;
    swimMinutes: number;
    boatMinutes: number;
    inferred: true;
  };
  /**
   * 对应的 3D 场景；null = 第一版没有场景
   */
  sceneRef: SceneId | null;
  /**
   * 原文没有这个场景、为游戏设计的地点
   */
  inferred?: boolean;
  note?: string;
  cite: Cite[];
}
/**
 * 一局游戏（第 1 节）
 */
export interface Playthrough {
  schemaVersion: SchemaVersion;
  playthroughId: PlaythroughId;
  /**
   * 邀请码账号的匿名 ID（S-020），不是邮箱、不是姓名
   */
  userRef: string;
  /**
   * 开局时锁定，整局不变
   */
  worldModelVersion: string;
  /**
   * 玩家选的身份
   */
  roleId: RoleId;
  /**
   * S-010：默认不填，第一版没有任何界面入口
   */
  playerAlias?: string;
  /**
   * S-010：默认不收集
   */
  ageBand?: "under13" | "13to17" | "18plus" | "unknown";
  status: "active" | "ended" | "abandoned" | "deleted";
  startedAt: RecordedAt;
  endedAt?: RecordedAt;
  /**
   * 最后一次有玩家操作的真实时间；默认保留期按它算
   */
  lastActiveAt: RecordedAt;
  /**
   * 最后一个事件的序号
   */
  lastSeq: number;
}
/**
 * 关系，不单独存，按记忆推出（第 4 节）
 */
export interface Relationship {
  character: CharacterId;
  /**
   * 初值 + 未删除记忆的 trustDelta 之和，截断到 -100..100
   */
  trust: number;
  /**
   * 由 trust 区间映射（第 4 节的表）
   */
  label: string;
  /**
   * （1.5）同一区间的档位，接口里叫 relationLevel
   */
  level: 1 | 2 | 3 | 4 | 5;
}
/**
 * 玩家身份（2.7）
 */
export interface Role {
  id: RoleId;
  name: string;
  /**
   * 第几版开放
   */
  release: number;
  startAct: ActId;
  startPlace: PlaceId;
  startT: StoryTime;
  /**
   * 一开始认识谁（这些角色开局信任 +10）
   */
  knownCharacters: CharacterId[];
  /**
   * 能自由进出的地点
   */
  access: PlaceId[];
  /**
   * （1.1）条件满足时也能进
   */
  conditionalAccess?: {
    place: PlaceId;
    when: Condition[];
    note?: string;
  }[];
  /**
   * 身份自带知道的 fact
   */
  initialKnowledge: FactId[];
  /**
   * （1.3）开局带在身上的物品
   */
  items?: ItemId[];
  inferred: true;
  note?: string;
}
/**
 * （1.1）本局即兴设定（3.1）
 */
export interface RunFact {
  factId: RunFactId;
  /**
   * 谁说的（归属于谁）
   */
  character: CharacterId;
  /**
   * 一句中性日语
   */
  statement: string;
  /**
   * 记下它的事件
   */
  madeBy: EventId;
}
/**
 * 3D 场景（2.2）
 */
export interface Scene {
  /**
   * ID 由前端提出（frontend-design 8.1）
   */
  id: SceneId;
  name: string;
  /**
   * 第几版做
   */
  release: number;
  inferred: true;
  note?: string;
}
/**
 * （1.7）固定演出（2.11，S-080 ④）：每局一样、写好的地の文和人物的预录句，挂在节拍或玩家的动作上，由服务端在对的时机下发。只是演出：不是事件，不改世界状态；例外是 learns（演出里说出的事，听的人就知道了）
 */
export interface SetPiece {
  id: SetPieceId;
  /**
   * 什么时候演：这个节拍发生时玩家在场，或玩家的这种动作判定之后
   */
  on:
    | {
        beat: BeatId;
      }
    | {
        /**
         * api-contract 3.8 的 kind
         */
        act:
          | "examine"
          | "give"
          | "follow"
          | "block"
          | "help"
          | "wait"
          | "go"
          | "shortcut"
          | "run-together"
          | "hasten"
          | "move";
        /**
         * 对人物的动作写人物 ID，move 写地点 ID，go 写出口通往的地点（布局 exits[].place），examine 写 interactable 的 ID（obj.*）；省略 = 不看对象
         */
        target?: string;
        /**
         * 只在被拒时演；省略 = 只在做成时（done / partial）
         */
        refused?: true;
      };
  /**
   * 这些节拍已经发生（happened / altered）
   */
  after?: BeatId[];
  /**
   * 这些节拍还没发生
   */
  before?: BeatId[];
  /**
   * 这些人物知道这件事：Character.knows 里到这个时刻已经成立的（since），或这一局已提交的 learn
   */
  knows?: {
    character: CharacterId;
    fact: FactId;
  }[];
  /**
   * 这些固定演出里至少有一个这一局已经演过
   */
  played?: SetPieceId[];
  /**
   * 这些固定演出这一局都还没演过
   */
  notPlayed?: SetPieceId[];
  /**
   * 别的状态条件（同节拍前提）
   */
  when?: Condition[];
  /**
   * 一局只演一次
   */
  once?: true;
  /**
   * 按顺序演，整条放在一条 set_piece 消息里下发（api-contract 3.14）：narration = 地の文；speaker + line = 这个人物的一句预录（构建时生成，ux-design 16.2），录音是 manifest 的 setPieceVoices["{id}/{序号}"]，序号从 1 起、地の文也算
   *
   * @minItems 1
   */
  lines: (
    | {
        /**
         * 一行地の文（日语）
         */
        narration: string;
      }
    | {
        speaker: CharacterId;
        /**
         * 预录句，也是字幕（日语）
         */
        line: string;
      }
  )[];
  /**
   * 演这一条时谁知道了哪件事（S-077 ⑪）：服务端在这一条演出的同一次提交里紧跟着另写一条 type learn 的事件（actor = 第一个说话的人物，只有地の文时 system；checker set-piece；动作时机 origin action，节拍时机不写 origin）。只给 learn，不给任意 effects：固定演出不过叙事者的 R1〜R7
   *
   * @minItems 1
   */
  learns?: {
    character: "player" | CharacterId;
    fact: FactId;
  }[];
  inferred: true;
  note?: string;
}
/**
 * 状态变量（2.6）
 */
export interface StateVar {
  id: VarId;
  type: "enum" | "int" | "bool" | "place" | "minutes";
  values?: string[];
  min?: number;
  max?: number;
  /**
   * var.player.location、var.act.current 的初值由身份决定
   */
  default: unknown;
  /**
   * 决定结局的变量
   */
  keyMoment?: boolean;
  /**
   * 变化能不能显示给玩家；默认 false
   */
  visibleToPlayer?: boolean;
  /**
   * 取值 → 一句可直接显示的日语
   */
  valueLabels?: {
    [k: string]: string | undefined;
  };
  /**
   * （1.6，C-16）把变量改成某个值时要满足的条件（2.6）。① 只管叙事者提交的事件，到点的节拍和期限（origin = schedule）不判，节拍的结果由节拍前提管；② 值真的变了才判，设成现在的值不判；③ 按这个 effect 之前的状态判，同一事件里前面的 effect 已生效；④ when 不成立报 R2；⑤ 设好以后条件不再成立不自动改回、不算违规
   */
  valueRequires?: {
    /**
     * 这个变量的一个取值（enum 在 values 里，其余合类型）
     */
    value: unknown;
    /**
     * 全部成立才能改成 value；和节拍前提同一个 Condition 和求值函数
     *
     * @minItems 1
     */
    when: Condition[];
    /**
     * 为什么有这个条件（日语）；不成立时叙事者的 reason 带上变量、value 和它
     */
    note: string;
    inferred: true;
    cite?: Cite[];
  }[];
  description: string;
}
/**
 * （1.1）约定，由 promise 效果推出，不单独写（3.1）。生成的代码里叫 StoryPromise，避开 JS 的 Promise
 */
export interface StoryPromise {
  promiseId: PromiseId;
  /**
   * 许下的一方
   */
  from: "player" | CharacterId;
  /**
   * 对方
   */
  to: "player" | CharacterId;
  /**
   * 约定的内容（日语，中性，不是原话）
   */
  text: string;
  due?: {
    t?: StoryTime;
    beat?: BeatId;
  };
  template?: PromiseTemplateId;
  /**
   * まだ / 果たされた / 破られた / 作废
   */
  status: "open" | "kept" | "broken" | "voided";
  /**
   * 成立的事件
   */
  madeBy: EventId;
  /**
   * 兑现、违背或作废的事件
   */
  resolvedBy?: EventId;
}
/**
 * 玩家和角色的原话，单独存放，可删除（第 3 节）
 */
export interface Utterance {
  utteranceId: UtteranceId;
  playthroughId: PlaythroughId;
  /**
   * 記憶帳删除时按轮清空（第 4 节）
   */
  turnId: TurnId;
  speaker: "player" | CharacterId;
  /**
   * 识别后的文字（不存音频）；删除后清空
   */
  text: string;
  t: StoryTime;
  recordedAt: RecordedAt;
  /**
   * 删除后 text 清空
   */
  deletedAt?: RecordedAt;
}
/**
 * 世界结局的底线分类（2.9，S-007）
 */
export interface WorldEnding {
  /**
   * 写进 Ending.world.outcome
   */
  id: WorldEndingId;
  /**
   * 判定顺序：从 1 开始，第一个条件全满足的就是本局的世界结局
   */
  order: number;
  /**
   * 日语，结局卡上显示
   */
  label: string;
  /**
   * 按结局时的 WorldState 判断
   */
  when: Condition[];
  inferred: true;
  note?: string;
}
/**
 * 世界模型（第 2 节）：静态、按书版本化；由原文抽取流水线生成，人工校对后发布，运行时只读
 */
export interface WorldModel {
  schemaVersion: SchemaVersion;
  /**
   * 内容版本，如 "hashire-merosu@1.0.0"
   */
  worldModelVersion: string;
  book: {
    /**
     * 如 "hashire-merosu"
     */
    id: string;
    title: string;
    author: string;
    year: number;
    source: {
      provider: "aozora";
      cardId: string;
      fileId: string;
      url: string;
      textSha256: string;
      /**
       * 取得原文的日期
       */
      retrievedAt: string;
      license: "public-domain";
    };
  };
  characters: Character[];
  places: Place[];
  facts: Fact[];
  beats: Beat[];
  causal: CausalEdge[];
  /**
   * 不能被推翻的 fact / beat ID（锚点）
   */
  anchors: (FactId | BeatId)[];
  /**
   * 死者不复活、没有奇迹、时间不倒流、没有现代物品、人物自己做决定
   */
  globalRules: {
    id: RuleId;
    text: string;
    inferred: true;
    /**
     * 有原文依据时（1.4）
     */
    cite?: Cite[];
  }[];
  clock: Clock;
  stateVars: StateVar[];
  /**
   * 玩家可选身份
   */
  roles: Role[];
  /**
   * 3D 场景（S-001）
   */
  scenes: Scene[];
  /**
   * 幕（S-004）
   */
  acts: Act[];
  endings: {
    /**
     * 世界结局的底线分类（S-007、S-034）
     */
    world: WorldEnding[];
    /**
     * （1.1）什么叫「结局实质不同」，见 2.9.1
     */
    signature?: EndingSignature;
  };
  /**
   * 时间消耗参数（S-005、S-038），键见 2.6.1；值是故事分钟
   */
  pacing?: {
    [k: string]: number | undefined;
  };
  /**
   * （1.1）pacing 的说明（日语）
   */
  pacingNote?: string;
  /**
   * （1.1）情境动作，见 2.10
   */
  affordances?: Affordance[];
  /**
   * （1.1）故事里的物品，见 2.10
   */
  items?: Item[];
  /**
   * （1.7，S-080 ④）固定演出：挂在节拍或玩家的动作上的地の文和预录句，见 2.11
   */
  setPieces?: SetPiece[];
  /**
   * （1.7）场景里可「調べる」的东西，见 2.12
   */
  objects?: WorldObject[];
}
/**
 * （1.7）可调查物（2.12）：场景里可「調べる」的东西。服务端按它出快照的 interactables（kind examine，0 分），不写死；场景出口照布局的 exits
 */
export interface WorldObject {
  id: ObjectId;
  /**
   * 在哪个地点（要有场景）
   */
  place: PlaceId;
  /**
   * 按钮上的字（日语，UX 出）
   */
  label: string;
  /**
   * 布局里的位置点（前端加）；服务端出快照时要有
   */
  spot?: SpotId;
  inferred: true;
  note?: string;
}
/**
 * 由事件推出的当前状态，不是第二份事实（3.1）：世界模型初值 + 按 seq 依次应用全部事件的 effects
 */
export interface WorldState {
  playthroughId: PlaythroughId;
  /**
   * 推导到第几个事件
   */
  asOfSeq: number;
  /**
   * 时钟 = 所有事件 max(t + dt)
   */
  t: StoryTime;
  /**
   * 所有 stateVar 的当前值
   */
  vars: {
    [k: string]: unknown | undefined;
  };
  beats: {
    [k: string]: "pending" | "happened" | "prevented" | "delayed" | "hastened" | "altered" | undefined;
  };
  /**
   * 还没结果的节拍的本局排定时间（2.5.1）
   */
  schedule: {
    [k: string]: StoryTime | undefined;
  };
  /**
   * 角色 → 运行时新学到的 fact
   */
  knowledge: {
    [k: string]: (FactId | RunFactId)[] | undefined;
  };
  /**
   * 角色 → 地点
   */
  locations: {
    [k: string]: PlaceId | undefined;
  };
  /**
   * （1.7）角色 → 指定的位置点：relocate 写了 spot 才有；换到别的地点时去掉。没有的由后端按布局的站位规则排（第 3.1 节）
   */
  spots?: {
    [k: string]: SpotId | undefined;
  };
  /**
   * （1.1）promiseId → 约定
   */
  promises?: {
    [k: string]: StoryPromise | undefined;
  };
  /**
   * （1.1）factId → 即兴设定
   */
  runFacts?: {
    [k: string]: RunFact | undefined;
  };
  /**
   * （1.3）portable 物品 → 现在谁拿着
   */
  holdings?: {
    [k: string]: "player" | CharacterId | null | undefined;
  };
}
