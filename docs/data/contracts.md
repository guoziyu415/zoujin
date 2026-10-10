# 数据契约（contracts.md）v1.7

负责人：数据工程 · 状态：**v1.7**（1.5 在 M2-0 冻结（C-2），以后只做加法；1.6 是冻结后第一个加法版本）。v1.0 是基线（S-033），v1.1 是 PM 接受的新基线（S-061〜S-063），已按后端评审（`backend/reviews/data-v0.1.md`）和 PM 评审（`pm/reviews/data-v0.1.md`）修改。1.1 只做加法：加进 D-012〜D-015 的落地（S-029〜S-032：互助、约定、打算、即兴设定、导演事件、生成的结局、角色结局）、S-034〜S-053 里和数据有关的决定、后端设计 v1.0 第 12 节的 13 条提案和 UX 设计 v1.0 第 18.3 节的要求。1.2 也只做加法：幕末说出的打算（S-031 ③）、作废和出戏的一轮怎么落数据（S-054、S-057）。1.3 加随身的东西（UX 5.1，C-14）。1.4 按 UX 对世界模型的校对和 S-064 加：有条件的台词和设计台词、互助的效果、节拍的变体、过场里的二选一、第四幕按钮上「对梅洛斯的影响」。1.5 给过场的选项也加上「对梅洛斯的影响」和选后的一句（UX 校对 7.3、ux-design 4.5）。1.6 把两条只写在说明文字里的取值条件写成数据（`StateVar.valueRequires`，C-16），结局卡改成 1〜3 人、每一局都出（C-17）。1.7 加位置点（谁站在布局的哪个点）、成群的人物和幕末去处的落地（M2 切片，C-18），以及打算成行时的落点（C-19）、固定演出（S-080 ④）、可调查物和玩家知道什么。跨角色决定见 `pm/decisions.md`。还在等别人定的事列在第 7 节。
UX、前端请看第 2.8 节（幕）、第 4 节（记忆）、第 5 节（结局）。1.1 新增或写清的地方都标了「（1.1）」，文末变更记录有汇总。
最近更新：2026-10-10（1.7：relocate 和 `ActExit` 的 `spot`、`WorldState.spots`、`Character.group`、`ActExit.arrival`、`ActExit.sub`、`Affordance.playerSpot`（C-18）、`Act.plan`（C-19）、`setPieces`（S-080 ④）、`objects`、玩家学到的事实（`learn` 写 `player`）；1.6：`StateVar.valueRequires`（C-16）、结局卡 1〜3 人（C-17））

四个契约：**WorldModel**（世界模型，静态、按书版本化）、**Event**（运行时事件，只追加）、**Memory**（角色对玩家的记忆，可删除）、**Ending**（结局）。另有两个支撑结构：**Playthrough**（一局游戏）和 **WorldState**（由事件推出的当前状态）。

改字段先找数据工程。v1.0 起契约只做加法：新增可选字段走小版本（1.1、1.2…）；改语义或删字段要升大版本，并由 PM 记进 `pm/decisions.md`。

---

## 0. 通用约定

| 约定 | 内容 |
|---|---|
| 格式 | JSON；每个契约有 JSON Schema（放在 `packages/contracts/schemas/data/*.schema.json`，CI 校验）。本文用 TypeScript 风格写，便于阅读 |
| 版本 | 每个文档带 `schemaVersion`（写入时的契约版本，现在是 `"1.6"`；1.1 起新增的字段都是可选的，旧版本写的文档按新版本读仍然合法）；世界模型另带 `worldModelVersion`（内容版本，如 `"hashire-merosu@1.0.0"`） |
| 静态 ID | 世界模型里的 ID 用小写短横线 slug，带类型前缀：`char.king`、`place.syracuse-square`、`scene.village`、`act.2`、`beat.03`、`fact.promise`、`var.hostage.fate`、`role.traveler`、`edge.10-11`、`exit.1.road` 幕末去处、`rule.no-resurrection` 全局规则；（1.1）`aid.melos.shortcut` 互助、`promise.melos.return` 约定模板、`aff.river-hold` 情境动作、`item.water` 物品；（1.7）`piece.gate-taken` 固定演出、`obj.workshop-door` 可调查物。世界结局的 ID 不带前缀（`canon-reunion`）。（1.6 写清）状态变量 ID 的段里可以用驼峰：`var.player.companionOf`、`var.player.knowsShortcut`、`var.melos.knowsTyranny`（`world.json` 已在用） |
| 运行时 ID | 前缀 + ULID（按时间可排序）：`pt_…` 一局、`turn_…` 一轮、`ev_…` 事件、`mem_…` 记忆、`utt_…` 一句话、`end_…` 结局；（1.1）`prm_…` 约定、`rf_…` 本局即兴设定 |
| 故事时间 | `t` = 从 Day 0（约束之日）00:00 起算的故事分钟数。期限是 Day 3 日没 = `5460`（2.6 节）。时间只由事件推进，不随真实时间流动（S-021） |
| 时间的说法 | `tLabel` 按世界模型的 `clock.labels` 生成，如 `t=1380` →「約束の日・夜」，`t=5460` →「三日目・日没」（1.1：格式和时段按 UX 的表，S-037，见 2.6）。前端、記憶帳、结局都用同一个规则 |
| 真实时间 | `recordedAt`，ISO 8601 UTC，只用于审计和分析，不参与故事逻辑 |
| 语言 | 玩家看得到的文字（`summary`、记忆 `text`、结局文字、`tLabel`、関係 `label`）一律日语（S-008） |
| 出处 | 见下面的 `Cite`。世界模型里来自原文的每条内容至少一个 `Cite`（A-003） |
| 不可信文本 | 玩家原话只存在 `Utterance` 里（可删除）。其他契约只引用 `utt_` ID，或存叙事者写的中性日语摘要。任何契约字段都不能被当作指令拼进 Agent 的系统提示（A-004） |
| 个人信息 | `Event.summary`、`MemoryItem.text`、`Ending` 的全部文字字段**不得包含现实中的个人信息**（真名、住址、电话、学校、账号等）。事件只追加、删不掉，所以必须在写入前就干净；违反即自检 R6 失败，评测 E8 覆盖 |

```ts
// 原文出处：可以被机器校验
type Cite = {
  source: string;   // 原文版本 ID，如 "aozora:1567_ruby_4948@sha256:2a437c047d7f"（对规范化全文求哈希）
  para: number;     // 规范化文本里的段落号，从 1 开始
  quote: string;    // 原文片段，必须是该段的**精确子串**，≤ 80 字
};
// 校验规则：quote 必须能在 source 的第 para 段里逐字找到，否则世界模型发布失败。
// 推断出来、原文没写的内容用 inferred: true 标出，并在 note 里写推断依据。
```

**`actor` 的含义（事件是谁做的，不是谁写的；写入方永远是叙事者）：**

| actor | 含义 | 例 |
|---|---|---|
| `"player"` | 玩家的话或动作 | 替梅洛斯担保、选择幕末去处 |
| 角色 ID | 角色自己的行为（从对话里提取）；（1.1）也包括没人管时按打算做的事（S-030 ①）、兑现答应你的事（S-029 ②） | `char.melos` 答应在河边等 |
| `"system"` | 按时间表自然发生的事：到点的节拍、期限规则、幕的开始；环境的变化（钟声、天色） | Day 0 深夜塞利农提乌斯被召进城 |
| `"narrator"` | 只用于 `correction`：叙事者撤回或修正自己已提交的事件 | — |

（1.1）叙事者以「导演」身份制造的变化（S-031 ②）**不另设 actor**：`actor` 照上表写故事里是谁做的（报信的人物、环境变化写 `system`），另用 `Event.origin = "director"` 标出来源（3 节）。这样 `actor` 的含义和 1.0 一样，「なぜこうなった？」按故事里的行为者显示（api-contract 2.6）。

---

## 1. Playthrough（一局）

```ts
type Playthrough = {
  schemaVersion: "1.0" | "1.1" | "1.2" | "1.3" | "1.4" | "1.5" | "1.6";
  playthroughId: string;          // pt_…
  userRef: string;                // 邀请码账号的匿名 ID（S-020），不是邮箱、不是姓名；L3「删除我的全部数据」按它删
  worldModelVersion: string;      // 开局时锁定，整局不变
  roleId: string;                 // 玩家选的身份，如 "role.traveler"
  playerAlias?: string;           // S-010：默认不填，第一版没有任何界面入口；角色用身份称呼玩家（「旅の方」）
  ageBand?: "under13" | "13to17" | "18plus" | "unknown"; // S-010：默认不收集。第一版只对 18 岁以上（S-022）；用 Gemini 时不能面向 18 岁以下（S-060）
  status: "active" | "ended" | "abandoned" | "deleted";
  startedAt: string; endedAt?: string;
  lastActiveAt: string;           // 最后一次有玩家操作的真实时间；默认保留期按它算：30 天没操作自动删（S-035，data-design 5.5）
  lastSeq: number;                // 最后一个事件的序号
};
```

同一局可以中途退出、改天继续，角色记得你；不同局之间不记得（S-012）。

---

## 2. WorldModel（世界模型，静态）

由「原文抽取流水线」生成，人工校对后按版本发布，运行时只读。内容分两层：**原文层**（人物、地点、事实、节拍、因果，每条带 `Cite`）和**设计层**（场景、幕、身份、状态变量、结局分类、时间说法；1.1 加人物的互助、约定模板、打算，情境动作、物品、结局署名；全部 `inferred: true`，由 PM/UX 和数据一起定，有原文依据时也附 `cite`）。

```ts
type WorldModel = {
  schemaVersion: "1.0" | "1.1" | "1.2" | "1.3" | "1.4" | "1.5" | "1.6";
  worldModelVersion: string;      // "hashire-merosu@1.0.0"
  book: {
    id: string;                   // "hashire-merosu"
    title: string; author: string; year: number;
    source: { provider: "aozora"; cardId: string; fileId: string; url: string; textSha256: string; retrievedAt: string; license: "public-domain" };
  };
  // —— 原文层 ——
  characters: Character[];
  places: Place[];
  facts: Fact[];
  beats: Beat[];
  causal: CausalEdge[];
  anchors: string[];              // 不能被推翻的 fact / beat ID（锚点）
  globalRules: { id: string; text: string; inferred: true; cite?: Cite[] }[];  // （1.4）cite：有原文依据时（例：妹は十六歳）  // 死者不复活、没有奇迹、时间不倒流、没有现代物品、人物自己做决定
  // —— 设计层 ——
  clock: Clock;
  stateVars: StateVar[];
  roles: Role[];                  // 玩家可选身份
  scenes: Scene[];                // 3D 场景（S-001）
  acts: Act[];                    // 幕（S-004）
  endings: {
    world: WorldEnding[];             // 世界结局的底线分类（S-007、S-034）；1.1 起是「保证能到达的底线」，结局可以按这一局生成（S-031 ①）
    signature?: EndingSignature;      // （1.1）什么叫「结局实质不同」（S-031 ⑤、S-041），见 2.9.1
  };
  pacing?: Record<string, number>;    // 时间消耗参数（S-005、S-038），键见 2.6.1
  pacingNote?: string;                // （1.1）pacing 的说明（日语）
  affordances?: Affordance[];         // （1.1）情境动作（S-036 ②、S-038、UX 5.1），见 2.10
  items?: Item[];                     // （1.1）故事里的物品（R7：给东西要拿得到），见 2.10
  setPieces?: SetPiece[];               // （1.7，S-080 ④）固定演出：挂在节拍或玩家的动作上的地の文和预录句，见 2.11
  objects?: WorldObject[];              // （1.7）场景里可「調べる」的东西，见 2.12
};
```

### 2.1 Character

```ts
type Character = {
  id: string;                     // "char.melos"
  name: string; reading?: string; // 「メロス」「王ディオニス」
  summary: string;                // 一两句，中性描述
  traits: { text: string; cite: Cite[]; since?: string; until?: string; when?: Condition[] }[];  // 性格，每条有出处
  goals: { text: string; cite: Cite[]; since?: string; until?: string; when?: Condition[] }[];   // 动机（= S-030 的「当下目标」）
  speech: {                        // 说话方式，给角色 Agent 和评测用
    firstPerson?: string;          // 「私」「わし」…
    register: string;              // 「率直、激しい、古風な言い回し」
    sampleLines: (Cite & { since?: string; until?: string; when?: Condition[] })[];  // 原文台词，直接引用
    designLines?: DesignLine[];    // （1.4）原文没有、为游戏写的示例台词（UX 校对 2.1、2.8）
  };
  // （1.1）since / until = 节拍 ID：从该节拍发生起才用 / 该节拍发生后不再用（后端评审提案第 5 条）。
  // 角色提示只放此刻有效的条目，例：王的「どうか、わしをも仲間に入れてくれまいか」since beat.26，改心前不进提示。
  // 节拍本局没发生，since 的条目就一直不用，until 的条目就一直有效。
  // （1.4）when = 此刻的 WorldState 满足这些条件才用（S-064：セリヌンティウスが本局で友を疑ったかどうかで、
  // 「生れて、はじめて君を疑った」を言うか言わないかが変わる）。since / until / when 同时写时三者都要满足。
  knows: { fact: string; since: string }[];  // 知道哪个 fact，从哪个 beat 起（"pre" = 故事开始前就知道）
  initialPlace: string;
  talkable: boolean;               // 第一版能不能自由对话。S-003：メロス、王、セリヌンティウス、妹、花婿、フィロストラトス、市の老爺
  group?: true;                    // （1.7）一群人（群众、警吏、山贼、一团旅人）：不占布局的位置点，前端按地点成群地放（3.1 的站位规则）
  voiceRef?: string;               // 声音配置的引用，具体值由后端/UX 管
  initialActivity?: Activity;      // （1.1）开局在做什么（默认 idle），见 2.4 的 Activity
  items?: string[];                // （1.3）开局带在身上的物品（portable 的 Item ID），如梅洛斯的短剑
  cite: Cite[];
  // —— （1.1）设计层：S-029、S-030、S-048 ——
  mutualAid?: MutualAid[];         // 互助：他能为你做的、你能为他做的。能对话的人物两种至少各一条
  promiseTemplates?: PromiseTemplate[];  // 这个人物常见的约定；叙事者写 promise 效果时引用。玩家临时提出的约定不需要模板
  plans?: { act: string; text: string; inferred?: true; cite?: Cite[] }[];  // 每一幕「没人管时的打算」；能对话的人物必填
};

type DesignLine = {                // （1.4）
  text: string;                    // 日语一句。角色提示里和 sampleLines 一样当示例用，不逐字照念
  since?: string; until?: string; when?: Condition[];   // 和 sampleLines 同样的生效规则
  inferred: true;
  note?: string;                   // 什么场合说（例：「人質の夜」「S-044 ② の開口例」）
  cite?: Cite[];                   // 依据的原文（例：「メロスは来ます、とだけ答え」→「……メロスは来る。それだけだ。」）
};

type MutualAid = {                 // （1.1）
  id: string;                      // "aid.melos.shortcut"
  direction: "forYou" | "fromYou"; // forYou = 他能为你做的；fromYou = 你能为他做的
  text: string;                    // 日语一句，给叙事者和角色提示用，不直接显示给玩家
  when?: Condition[];              // 只在这些条件下才可能（例：梅洛斯被捕时才能在王前提起你）
  opening?: string;                // 身份 ID：这一条是该身份第一幕的「开局互助」（S-048），玩家正常说话就能完成
  major?: true;                    // 只用于 forYou：兑现时算关键时刻（S-041「为你做的一件大事」）
  gives?: string;                  // （1.3）只用于 forYou：兑现时人物交给你的物品（portable 的 Item ID）；叙事者提交 hold 效果
  effects?: Effect[];              // （1.4）兑现时提交的效果模板（同 Affordance.effects），例：一緒に信じ続ける → selinuntius.faith +1。
                                   // 经由情境动作兑现时只提交动作的 effects，不重复提交这里的
  inferred: true;
  cite?: Cite[];                   // 有原文依据时给出处
};

type PromiseTemplate = {           // （1.1）
  id: string;                      // "promise.melos.return"
  by: "player" | string;           // 谁许下的；另一方是模板所属的人物（by 是人物自己时，另一方是玩家）
  text: string;                    // 约定的内容（日语），如「必ず戻る」
  inferred?: true; cite?: Cite[];
  note?: string;                   // （1.4）语气、什么场合（例：王的赌约是冷笑着说的，不是软化，UX 校对 2.4）
};
```

**防剧透规则（叙事者、局势说明和评测共用）：** 在故事时间 `t`，角色 C 能提起的事实 = `C.knows` 里 `since` 已发生的那些 + 运行时通过事件 `learn` 学到的那些（1.1：包括别人的即兴设定）+ C 自己的即兴设定（3 节 `improv`）。别的一律当「不知道」。

**（1.7）玩家知道什么（R4 的行为者是玩家时）：** 玩家能提起的事实 = 身份的 `initialKnowledge` + 这一局学到的（`learn` 的 `character` 写 `"player"`）。学到有两条路：① 人物告诉玩家：叙事者从这一轮提取 `learn`，R4 查说的人知不知道；② 亲眼看到：节拍发生（`happened` / `altered`）时玩家在节拍的地点（`var.player.location` = `Beat.place`，按这个事件之前的状态），共享规则库在这个节拍的系统事件里追加 `learn`，事实 = `trueFrom` 是这个节拍、`visibility: "public"`、玩家还不知道的那些（2.3：public 在场的人都会知道）。`trueFrom` 这一局没发生的事实，玩家也不算知道（2.3）。人物不按在场自动学：`Character.knows` 已按原作的在场写好，原作以外的在场靠 `learn`（例：群众要玩家传话才知道约定，S-077）。人物和玩家都由共享规则库的 `zoujin_worldsim.knows(world, state, who, fact)` 判。

**互助、约定、打算怎么用（1.1，S-029、S-030、S-048）：**

- `mutualAid` 是设计好的保底，不是上限：玩家临时提出的别的请求，叙事者按人物的目标、性格、知情范围判断。能不能成看关系（第 4 节的 trust）和当时情势（`when`）。
- 人物答应的事写成 `actor` = 人物 ID 的事件，过 R1〜R7；可以在玩家不在场时兑现，在幕切换时结算。为玩家做的事带 `beneficiary: "player"`，`causes` 要能追到玩家的一个举动。兑现 `major` 的那一条算关键时刻（3 节）。
- 约定有状态（进行中 / 守约 / 失约 / 作废），用 3 节的 `promise` 效果记录；失约也是有后果的事件。
- 不在玩家面前的人物，叙事者在幕切换和关键时刻按 `plans` 批量推进（不每轮跑），写成 `actor` = 人物 ID、`origin: "plan"` 的事件。
- 每个第一版身份有一对 `opening` 互助（一条 forYou、一条 fromYou），开局 5 分钟内一定能完成（S-048）。
- 校验工具检查：能对话的人物两种方向都有、有 `plans`；第一版身份都有一对开局互助；`major` 只用于 forYou。

### 2.2 Place 与 Scene

```ts
type Place = {
  id: string;                      // "place.syracuse-square"
  name: string; description: string;
  adjacent: { place: string; travelMinutes: number; inferred?: boolean }[]; // 步行分钟；跑步等节奏由叙事者按系数换算
  crossing?: { bridgeMinutes: number; swimMinutes: number; boatMinutes: number; inferred: true }; // 有河的地点
  sceneRef: string | null;         // 对应的 3D 场景；null = 第一版没有场景（见下）
  inferred?: boolean;              // 原文没有这个场景、为游戏设计的地点
  note?: string;
  cite: Cite[];
};

type Scene = {
  id: string;                      // "scene.syracuse-square"（ID 由前端提出，frontend-design 8.1）
  name: string;
  release: number;                 // 第几版做
  inferred: true;
  note?: string;                   // 如「三日目の日没は同じ場面を刑場に転換」
};
```

**`sceneRef` 为空的地点**（第一版只有 `place.neighbor-village`）：玩家不能在那里停留。经过它的移动、在那里发生的节拍，由叙事者在移动或幕切换时用一两句日语旁白交代（字幕 + 旁白音），事件照常写入日志，「なぜこうなった？」照常能追到。

### 2.3 Fact

```ts
type Fact = {
  id: string;                      // "fact.promise"
  statement: string;               // 中性陈述（日语）
  trueFrom: string;                // 从哪个 beat 起成立；"pre" = 开场前已成立
  visibility: "public" | "private"; // public：在场的人都会知道；private：只有 knows 里的人知道
  spoilerTerms?: string[];         // 说出这个事实时常用的词和别名（日语）。后端输出侧剧透检测、评测 E2 的确定性检查用；流水线生成、人工校对
  cite: Cite[];
};
```

（1.4 写清）`trueFrom` 的节拍这一局没有发生（被阻止或来不及），这条事实这一局就不成立，谁的 `knows` 都不算知道。例：弟子撑住了セリヌンティウスの心，`beat.s2` 没发生 → `fact.selinuntius-doubted-once` 不成立，刑场上梅洛斯也不会「知道」他疑过（S-064）。`altered` 的节拍算发生了。

### 2.4 Beat（情节节拍）

```ts
type Beat = {
  id: string;                      // "beat.03"
  order: number;                   // 原著顺序
  title: string; summary: string;
  window: { earliest: number; latest: number; canonical: number }; // 故事分钟；原著发生在 canonical；最晚 latest 之后就不可能再发生
  place: string;
  participants: string[];          // 角色 ID
  kind: "anchor" | "mutable";      // anchor：不能被阻止或改写；mutable：可被提前、推迟、阻止或改变结果
  preconditions: Condition[];      // 发生前提，引用 stateVars
  outcomes: Effect[];              // 原著里发生后对状态的影响（同 Event.effects 的写法）
  activities?: { character: string; activity: Activity }[];  // （1.1）节拍发生后这个人物在做什么，到他下一个带 activity 的节拍或移动为止
  variants?: BeatVariant[];        // （1.4）到点发生时，按这一局的状态换成另一种演法（2.4.1 第 2 步）
  cite: Cite[];
};

type BeatVariant = {               // （1.4，S-064）
  id: string;                      // "beat.25.v-no-doubt"
  when: Condition[];               // 节拍到点、前提成立时，按顺序取第一个 when 全满足的变体
  summary: string;                 // 这一局的演法（日语），叙事者据此演出；也是「その頃」和结局卡「原作との違い」的素材
  outcomes: Effect[];              // 代替节拍的 outcomes
  inferred: true; note?: string; cite?: Cite[];
};

type Activity = "idle" | "walk" | "run" | "talk" | "work" | "sleep" | "absent";  // （1.1）同 api-contract 2.3；前端不认识的按 idle

type Condition = {
  var: string; op: "==" | "!=" | ">=" | "<=" | "in"; value: unknown;
  inferred?: true; note?: string;  // 原文没写、为游戏设计的前提（例：王的信任降到 0 就不会改心）
};
```

#### 2.4.1 节拍是世界的默认时间表（回答 PM 评审第 1 条、后端评审第 7 条）

不管玩家在不在场，规则只有一条：

1. 每个节拍有一个「本局排定时间」`schedule[beat]`，初值是 `window.canonical`，按 2.5.1 的规则随推迟、提前而移动。
2. 叙事者每次提交让时钟前进后，按排定时间顺序检查所有还没结果的节拍：排定时间已到、前提成立 → 提交 `type: "beat"` 事件（`actor: "system"`，effect `{op:"beat", to:"happened"}` 加该节拍的 `outcomes`）。
   （1.4）节拍有 `variants` 时，先按顺序找第一个 `when` 全满足的变体：找到 → effect 写 `{op:"beat", to:"altered", outcomes: 变体的 outcomes, note: 变体的 id}`，`summary` 用变体的 `summary`；找不到 → 照上面写 `happened`。例：本局セリヌンティウスが一度も疑わなかった（`var.selinuntius.doubted == false`）→ `beat.25` 按变体演：メロスだけが打ち明けて殴られる。
3. 排定时间已到但前提不成立 → 不发生，下次时钟前进时再查；超过 `window.latest` 仍不成立 → 提交 `to: "prevented"`（`actor: "system"`，`check.reason` 写原因，例：「花婿が同意しなかったため婚礼は挙げられなかった」）。
   **（1.1 写清）** 例外：有 `delays` / `hastens` 出边的节拍（它发不发生决定后面的时间），排定时间已到而前提不成立时**当场**提交 `to: "prevented"`，不等到 `latest`，它的分钟立刻按 2.5.1 退还给下游。否则下游节拍会在它被判定之前就按原时间发生，2.5.1 说的「from 被阻止时 to 反过来提前」永远用不上。例：牧童带他走山口的脇道（`aff.pass-detour`），他不用格斗、体力有余，过了山口不会倒下（`beat.20` 的前提「体力 ≤ 20」不成立）→ `beat.20` 当场记 prevented → 泉（`beat.21`）提前 60 分钟（`edge.20-21-delay`）。参考实现见 `data/spikes/pipeline/worldsim.py` 的 `Sim.run`。
4. 玩家在场时，叙事者把这个节拍当作关键时刻演出；不在场时只写日志，UX 可以在幕切换时用「その頃」回顾（第 2.8 节）。
5. 玩家想改变一个节拍，只能在它发生之前通过自己的行动（事件）改变前提、推迟、提前或阻止它；锚点节拍不能被改变（R1）。

所以「玩家在村子时，城里的塞利农提乌斯被押上刑场」就是到点自动发生；幕切换时一次跳过很多小时，就按排定时间顺序一次结算完（2.8.1）。

### 2.5 CausalEdge（因果边）

```ts
type CausalEdge = {
  id: string;
  from: string; to: string;        // beat 或 stateVar
  type: "enables" | "requires" | "prevents" | "delays" | "hastens";
  timeLink?: "shift" | "order";    // （1.1）只用于 enables / requires。shift（默认，同 1.0）：from 推迟或提前多少，to 跟着平移；
                                   // order：只要求 to 不早于 from，不传递偏移（例：洪水和渡河，见 2.5.1）
  minutes?: number;                // delays / hastens 必填：from 发生会让 to 推迟（提前）几分钟
  note: string;                    // 为什么有这条边（日语）
  cite?: Cite[];                   // 原文能直接支持时给出处
  inferred: boolean;               // 原文没明说、由人推断的为 true
};
```

| type | 含义 |
|---|---|
| `enables` | from 让 to 成为可能，to 通常紧跟 from（同一条时间线：from 推迟，to 跟着推迟） |
| `requires` | to 必须先有 from；from 没发生，to 就不能发生（（1.4 写清）`altered` 也算发生了，只是结果不同） |
| `prevents` | from 发生后 to 不再可能 |
| `delays` / `hastens` | from 发生会让 to 推迟 / 提前 `minutes` 分钟；所以 from 被阻止时，to 反过来提前 / 推迟同样分钟 |

#### 2.5.1 时间传播规则（叙事者 R3 检查、评测 E5、校验工具共用一套）

- 节拍 X 被推迟 m 分钟 → `shift[X] += m`；被提前 → `shift[X] -= m`。
- 节拍 Y 的偏移 = Y 自己的推迟/提前 + 所有 `enables` / `requires` 父节拍偏移中的**最大值**（等最慢的那个），再加上 `delays` / `hastens` 边被阻止时的反向分钟。
- `schedule[Y] = max(window.earliest, canonical + shift[Y])`；超过 `window.latest` → Y 来不及（`prevented`，原因「時間切れ」），沿 `enables` / `requires` 往下的节拍同样来不及。
- **（1.1）`timeLink: "order"` 的边**不参加上面的「最大值」，只加一条下限：`schedule[Y] ≥ schedule[from]`。用在「from 只是早就该发生的前提、不是同一条时间线」的地方。例：洪水冲走桥（`beat.17`，早上 6 点，锚点）是渡河（`beat.18`，正午）的前提；如果按「等最慢的那个」，洪水的偏移永远是 0，玩家在第三幕帮梅洛斯省下的时间就永远传不到第四幕。`edge.17-18` 标成 order 以后，第三幕天亮前叫醒梅洛斯（`aff.wake-melos`，出发早 60 分钟，1.4 起代替原来的「帮花婿备婚礼」）能让梅洛斯日没前 60 分钟赶到（情景 `sc.wake-early`）。默认值 `shift` 和 1.0 的规则完全一样，没标的边行为不变。
- 例：原著的梅洛斯在日没那一刻（5460）冲进刑场，**余量是零**（S-036 保持）。玩家在河边拖住他 20 分钟就来不及。如果前面在过场里催他别闲逛（`edge.16-18-delay`，40 分钟；1.4 起是 `exit.3.road` 的 `enRoute`，体力照样消耗），18:20 就到，这时在河边拖 20 分钟也赶得上（情景 `sc.delay-offset`，18:40）。牧童（或听花婿说过路的人）带他走山口的脇道，他体力留着，过了山口不会倒下（2.4.1 第 3 条的例外，`edge.20-21-delay` 省 60 分钟），18:00 到（`sc.detour`）。帮他争取时间和拖住他一样容易（S-036 ②）：在河边拖 30 分钟、之后在泉边递水，18:30 到（`sc.hold-then-help`）；只拖不帮就来不及（`sc.hold-no-help`）。
- **（1.4，S-066；1.5 改为逐步算）到达下限 `clock.deadline.earliestArrival`：** 梅洛斯到 watchBeat 的时刻每一步都不早于下限。把本局对节拍的改动按节拍顺序（= 玩家做的先后）一个个加上去，每加一个看 watchBeat 的偏移变了多少（`delta`），累计 `a = max(下限 − canonical, a + delta)`，watchBeat 的偏移就是最后的 `a`。所以：已经到了下限，再帮他快是 0（作废，不攒着）；拖慢照算全额（S-066 ②）；拖慢之后离开了下限，再帮他快又有用，最多回到下限（ux-design 4.3）。例：「帮他快」全部做，不设下限 16:10 到，封顶在 17:30（`sc.all-help`）；第三幕帮快已到下限，第四幕在河边拖 30 分钟，18:00 到（`sc.all-help-then-hold`）；之后在泉边递水，回到 17:30、不会更早（`sc.capped-hold-then-water`）。参考实现 `Sim.schedule()`。1.4 的写法（帮快总量先封顶、再加拖延）会让拖慢之后的帮快也变成 0，和 S-066 ①「按钮写实际还能早多少」不一致，1.5 改掉；按 1.4 写法算出的情景结果只有 `sc.all-help-then-hold` 受影响，已改成上面的定义。
- 校验工具的情景模拟（`worlds/…/scenarios.json`）和评测 E5 都按这条规则算，参考实现是 `packages/worldsim/reference/worldsim.py`（W-1 移植成包 `packages/worldsim`）：条件求值 `holds`、效果应用 `apply`、排程 `schedule`、结局分类 `classify`（后端评审提案第 13 条：共享规则库可以直接从这里移植，评测用同一批用例对照）。

### 2.6 Clock 与 StateVar

```ts
type Clock = {
  startT: number;                  // 默认开局时间（各身份见 Role.startT）
  deadline: { t: number; label: string; cite: Cite[]; watchBeat?: string; earliestArrival?: number;
              earliestArrivalCue?: { speaker: string; line: string; narration: string; inferred: true; note?: string } };
                                   // label 如「三日目の日没」；（1.1）watchBeat = 决定赶不赶得上的节拍（beat.24）：
                                   // 太阳带上的「预计到达」和关键时刻的 eta 都看它的排定时间
                                   // （1.4，S-066）earliestArrival = watchBeat 最早的时刻（『走れメロス』5370 = 三日目 17:30，日没前 90 分）。
                                   // 帮他快超过它的部分作废、不留着抵后面的拖延；拖延照算全额（2.5.1）
                                   // （1.5，S-066 ①）earliestArrivalCue = 本局第一次到下限时说一次的话：提交后 watchBeat 的排定时刻
                                   // 第一次等于 earliestArrival，speaker 和玩家在同一地点 → 他说 line（「……これなら、間に合う。」），
                                   // 不在 → 叙事说 narration（「この足なら、陽の沈む前に着く。」）。之后离开又回到下限不再说（ux-design 4.3）
  sunsetMinuteOfDay: number;       // 日没是几点；游戏节奏参数，默认 1140（19:00）
  onDeadline: { if: Condition[]; then: Effect[]; note: string; cite: Cite[] }[];  // 到期限时自动执行（actor: "system"）；所有 if 都按期限那一刻的状态判断
  labels: {                        // tLabel 的生成规则（inferred）
    days: string[];                // ["約束の日","一日目","二日目","三日目"]，下标 = Day（S-037）
    bands: [number, string][];     // 一天内的时段起点（分钟）和叫法，如 [1140,"日没"]；从 0 开始严格递增
    format: string;                // （1.1）模板，含 {day} 和 {band}；『走れメロス』是 "{day}・{band}"（S-037、ux-design 4.2）
    inferred: true; note?: string;
    cite?: Cite[];                 // （1.1）时段叫法的原文依据（深夜、薄明、午前、真昼、日没）
  };
};

type StateVar = {
  id: string;                      // "var.hostage.fate"
  type: "enum" | "int" | "bool" | "place" | "minutes";
  values?: string[]; min?: number; max?: number;
  default: unknown;                // var.player.location、var.act.current 的初值由身份决定（Role.startPlace / startAct）
  keyMoment?: boolean;             // 决定结局的变量；（1.1）应当和 endings.signature.vars 一致，关键时刻按 3 节 S-041 的四条判
  visibleToPlayer?: boolean;       // 变化能不能显示给玩家（api-contract 的 visibleEffects）；默认 false。体力、信任这类数值不显示
  valueLabels?: Record<string, string>;  // 取值 → 一句可直接显示的日语，如 { "destroyed": "橋が流された" }
  valueRequires?: { value: unknown; when: Condition[]; note: string; inferred: true; cite?: Cite[] }[];
                                   // （1.6，C-16）把变量改成 value 时 when 要全部成立，见下面「取值条件」；note 是日语，叙事者的 reason 用它
  description: string;
};
```

**取值条件 `valueRequires`（1.6，C-16）：** 有的取值不是随时能设的，条件以前只写在说明文字里，叙事者第 3 步判不了。现在写成数据，叙事者、参考实现（`packages/worldsim/reference/worldsim.py` 的 `value_requires()`）和评测都只读它，不写死阈值。

1. 只管叙事者提交的事件。到点的节拍和期限（`actor: "system"`、`origin: "schedule"`）不判，节拍的结果由节拍前提管（例：刑场的 `beat.26` 让王改心）。导演事件的 `actor` 也是 `system`，但 `origin` 是 `director`，照样判：按 `origin` 区分，不按 `actor`。
2. 只在值真的变化时判；设成和现在一样的值不判。
3. 按这个 effect 之前的状态判，同一事件里前面的 effect 已经生效：先升信任再设 `wavering` 能过，反过来不过。
4. `when` 用和节拍前提同一个 `Condition` 类型和求值函数。不成立报 R2，`reason` 带变量、`value` 和这一条的 `note`。
5. 设好以后条件不再成立（信任又掉到 40 以下）不自动改回，也不算违规；改不改回是剧情的事。

世界模型自检（`build_world`）另查：`value` 在这个变量的取值里；`when` 引用的变量存在、取值合法；`note` 不空；情景（`scenarios.json`）里的事件也守这些条件；节拍以外的效果模板（互助、幕末去处、情境动作等）把变量设成受限的值时给警告。

『走れメロス』有三条：`var.king.disposition` 设 `wavering` 要 `var.king.trust` ≥ 40，设 `reformed` 要 ≥ 70（刑场的改心是到点的 `beat.26`，不判）；`var.river.crossing` 设 `bridge` 要 `var.bridge` = `intact`。

**玩家看得到哪些变化：** （1.4 写清，S-067）`valueLabels` 里没写的取值，当场不显示、不进状态栏、也不进「その頃」，只在结局里交代（例：`player.custody` / `hostage.fate` 的 `executed`，结局里间接说，不写「処刑」「死」）。一个事件的 effect 只有同时满足两条才进 `visibleEffects`：① 改的是 `visibleToPlayer` 的变量（文字取 `valueLabels`），或者是节拍走向的改变（文字 =「{beat.title}」+ 改变的说法）；② 玩家当时在这个事件的地点，或者事件就是玩家做的。其他变化不实时显示，留到幕切换时的「その頃」回顾（2.8.1），以免把玩家不可能知道的事提前说出来。

『走れメロス』的时段（ux-design 4.2）：深夜 0:00、薄明 4:00、朝 5:30、午前 9:00、真昼 11:30、午後 13:00、夕方 16:00、日没前 18:00、日没 19:00、夜 19:30。例：`t=1050` →「約束の日・夕方」，`t=1440` →「一日目・深夜」。

**三日之期的数法（已对照原文核对，S-011）：** Day 0 进城、约定、深夜塞利农提乌斯被召进城、梅洛斯当夜出发；Day 1 上午到村（「翌る日の午前」），睡到夜里，夜里去说服花婿、争到天亮；Day 2 正午婚礼（「結婚式は、真昼に行われた」），夜里睡在羊舍；Day 3 薄明出发（「眼が覚めたのは翌る日の薄明の頃である」），日没那一刻冲进刑场。所以「三日目」= Day 3。

#### 2.6.1 时间消耗 `pacing`（1.1，S-038〔待验证〕，R1 试玩后调）

| 键 | 『走れメロス』 | 含义 |
|---|---|---|
| `talkTurnMinutes` | 10 | 第一〜三幕和人物一来一回，有没有事件都算 |
| `talkTurnMinutesAct4` | 15 | 第四幕一来一回 |
| `failedTurnMinutes` | 0 | 作废、没听清、没回应的一轮 |
| `sceneWalkMinutes` | 0 | 场景内走动 |
| `examineMinutes` | 0 | 「調べる」 |
| `situationalMinMinutes` / `situationalMaxMinutes` | 15 / 120 | 情境动作的耗时范围；每个动作的耗时写在 `Affordance.minutes`，按钮上先写出来 |

第四幕和梅洛斯**边跑边说**只花玩家的时间，不改他的排定时间；只有让他**停下**的动作（2.10 里 `melos: "delay"` 的情境动作）才把时间加到他身上（S-038 补充）。只推进时钟、没有效果的事件（闲聊的一轮）照常写入，对玩家不可见（3 节）。

### 2.7 Role（玩家身份）

```ts
type Role = {
  id: string;                      // "role.traveler"
  name: string;
  release: number;                 // 第几版开放。S-002：第一版 = 旅人、石屋の弟子（UX 5.1 改名）、村の牧童；王城の侍女、警吏 = 2
  startAct: string;                // 从哪一幕开始，如牧童从 "act.3"
  startPlace: string; startT: number;
  knownCharacters: string[];       // 一开始认识谁（这些角色开局信任 +10）
  access: string[];                // 能自由进出的地点；其他地点要靠事件（被带进去、被召见）
  conditionalAccess?: { place: string; when: Condition[]; note?: string }[];
                                   // （1.1）条件满足时也能进（UX 5.1：旅人被押入王城时、跟着塞利农提乌斯时）
  initialKnowledge: string[];      // 身份自带知道的 fact
  items?: string[];                // （1.3）开局带在身上的物品（UX 5.1「随身的东西」），portable 的 Item ID
  inferred: true;                  // 身份是原著里没有的人，所有字段都是设计出来的
  note?: string;
};
```

R7 判「能不能进」：`access` ∪ 此刻条件成立的 `conditionalAccess` ∪ 事件给的许可（被带进去、被召见）。

### 2.8 Act（幕，S-004）

一局分四幕。每一幕里自由走动和说话；幕结束时玩家从「去处」里选一个（跟谁、去哪），故事时间跳到下一幕。（1.2，S-031 ③）`exits` 是**推荐去处**：玩家也可以说出自己的打算，叙事者判定能否成行（2.8.1 第 2 步）。

```ts
type Act = {
  id: string;                      // "act.1"
  order: number;                   // 1, 2, 3, 4
  title: string;                   // 「約束の日」
  start: { t: number };            // 本幕最早从什么时候开始（各去处的 t 不早于它）
  end: {
    onBeats: string[];             // 这些节拍任一有了结果（发生、被阻止或来不及）就收幕
    atLatest: number;              // 最迟在这个时间收幕
  };
  scenes: string[];                // 本幕可能用到的场景（前端据此预加载）
  exits: ActExit[];                // 幕末去处；最后一幕为空，收幕即进入结局
  plan?: {                         // （1.7，C-19）玩家在幕末说出的打算成行时落在哪里（2.8.1 第 2 步）；省略 = 叙事者按世界模型判（M3 定）
    toAct: string; place: string; t: number;   // 同 ActExit 的同名字段
    spot?: string;                 // 玩家落在 place 的哪个位置点；省略 = 这个地点的起点（startSpots）
    effects: Effect[];             // 成行本身固定的效果（例：人物的 relocate）；打算自己的效果由叙事者从玩家的话里提取，照常检查后加在同一条事件上
    arrival?: { line: string; opener?: string };  // 落地，同 ActExit.arrival
  };
  inferred: true;
  note?: string;
};

type ActExit = {
  id: string;                      // "exit.1.road"
  label: string;                   // 玩家看到的选项（日语），如「メロスと夜の道を行く」
  toAct: string;
  place: string;                   // 下一幕的起点
  t: number;                       // 下一幕从几点开始
  alignTo?: string;                // 跟着某个节拍走：该节拍本局被推迟/提前多少，t 就平移多少（例：跟梅洛斯走时对齐他的到达）
  roles?: string[];                // 只对这些身份开放；省略 = 全部
  requires?: Condition[];          // 收幕时的状态要满足
  effects: Effect[];               // 选择本身的效果，如 set var.player.companionOf = "char.melos"
  enRoute?: EnRoute;               // （1.4，UX 校对 3.2）跳过的这段路上有一个能改的节拍时，过场页给一个二选一
  sub?: string;                    // （1.7，UX）幕末页上这个去处副题的后半（日语，≤ 16 字，叙事口吻，不写分钟数），如「老爺があなたを覚えている」；
                                   // 前半「{地点}・{日子}の{时段}」前端按 place 和 t 生成。省略 = 只有前半
  spot?: string;                   // （1.7）玩家落在 place 的哪个位置点（布局 layout.json 的 spots）；省略 = 这个地点的起点（startSpots）
  arrival?: { line: string; opener?: string };  // （1.7）落地：line = 跳转之后的第一行叙事（地の文，日语）；
                                   // opener = 落地后先开口的人物（服务端发起一轮，台词按人设生成，不是问句）。ux/slice/jump-transition.md「落地」
};

type EnRoute = {                   // （1.4）
  beat: string;                    // 跳过的这段里能改的节拍（例：beat.16 隣村でのんびり歩く）
  line: string;                    // 过场页上叙事的一句（日语）：「隣村で、メロスは歩をゆるめた。」
  choices: EnRouteChoice[];        // 正好两个；最后一个是「照原作」，effects 为空。玩家不选 = 最后一个
  inferred: true; note?: string; cite?: Cite[];
};

type EnRouteChoice = {
  label: string;                   // 按钮上的动词（日语），不写分钟数：「急かす」
  effects: Effect[];
  melosMinutes?: number;           // （1.5）effects 里有改节拍的一条时必填：梅洛斯到刑场早（−）晚（+）几分钟，原著路径上的估计值，
                                   // 校验工具用共享规则核对（同 Affordance.melosMinutes，2.10）。按钮写本局实际值：「急かす（40分早まる）」
  after?: string;                  // （1.5）选了这一项，进下一幕之前过场页再多一句（日语）：「メロスは足を速めた。河原には、思ったより早く着いた。」
};
```

#### 2.8.1 幕切换的事件顺序

1. 收幕条件满足 → 后端推送「幕终わり」和当前可选的去处（按 `roles`、`requires` 过滤）。
2. 玩家选择 → 事件 `type: "act-transition"`，`actor: "player"`，`exitId` = 去处 ID，`t` = 当前时间，`dt = 0`，`effects` = 该去处的 `effects`。
   （1.2，S-031 ③）玩家说出自己的打算（api-contract 3.11 `act_propose`）：叙事者按 R2、R3、R7 判定能否成行（时间、地点、权限、同行的人在不在）。**成行** → 同样写这一条事件，但不写 `exitId`，改写 `plan`（叙事者的日语转述，不逐字引用玩家原话；下一幕起点、时间、同行的人），`effects` 由叙事者写、照常自检，第 4 步的目标时间用 `plan.t`。（1.7，C-19）这一幕有 `Act.plan` 时，`plan.toAct`、`plan.place`、`plan.t` 照它写，`effects` = `Act.plan.effects` 加上叙事者从打算里提取的效果，落点和落地照 `Act.plan.spot`、`Act.plan.arrival`。**不成行** → 不写事件，后端回替代去处（替代去处被选中时按成行处理）。同一次幕末最多试 2 次。
   （1.4）选的去处有 `enRoute`，而且它的节拍还没有结果、本局排定时间落在现在和目标时间之间 → 过场页先给这个二选一。玩家选了 → 事件 `type: "action"`，`actor: "player"`，`origin: "act"`，`exitId` = 去处 ID，`t` = 当前时间，`dt = 0`，`effects` = 选项的 `effects`，照常自检。玩家选最后一个（照原作）或不选 → 不写事件。每次过场最多一个二选一。（1.5）按钮上的分钟数是按本局此刻算的实际值（同 2.10 的按钮；api-contract 3.11 `act_ended.options[].enRoute.choices[].melosMinutes`，最后一项为 null）；选了带 `after` 的一项（接口里叫 `afterLine`），过场页先显示这一句再进下一幕。回传是 `act_choose` 的 `enRouteChoice`（序号），评测入口是 eval_api 的 `choose`。第 4 步的目标时间在这之后算（例：催梅洛斯别闲逛 → `beat.16` prevented → 他早 40 分钟到河边 → 跟着他走的去处 `alignTo: beat.18` 也早 40 分钟）。
3. 叙事者按 2.4.1 结算从现在到目标时间之间所有到点的节拍（`actor: "system"`，各自带自己的 `t`）。
4. 事件 `type: "act-transition"`，`actor: "system"`，`t` = 目标时间（`exit.t` 加上 `alignTo` 的偏移，或（1.2）`plan.t`；都不早于当前时间），`effects` = `set var.act.current`、`set var.player.location`。（1.7）去处有 `spot` 时玩家落在那个位置点（api-contract `snapshot.player.spot`）；有 `arrival` 时，落地后先显示 `arrival.line`，`arrival.opener` 先开口。
5. UX 用第 3 步的事件做「その頃」回顾（「あなたのいない間に」）。（1.1，ux-design 4.5 放宽）只列玩家在下一幕开始时能知道的事，最多 3 件，按顺序取：和玩家有关的约定的兑现或违背 → `keyMoment` 事件 → 玩家见过的人物自己做的事（`origin: "plan"`）。导演事件也在这里交代（S-045 ③）。

『走れメロス』的四幕（幕名和时间按 S-037；时间、去处都已用校验工具核对过）：

| 幕 | 时间 | 场景 | 幕末去处 |
|---|---|---|---|
| act.1 約束の日 | Day 0 17:30（夕方，玩家先于梅洛斯在广场）→ 梅洛斯出发（23:45） | 广场、王座之间 | 跟梅洛斯走夜路（→ 泉，Day 1 02:45）/ 留在城里陪塞利农提乌斯 / 留在市里 |
| act.2 その夜 | Day 1 00:00 → 梅洛斯到村（Day 1 10:00） | 归途（夜，桥还在）、广场、王座之间 | 跟梅洛斯到村子 / 在市里等 |
| act.3 村の二日 | Day 1 09:00 → 梅洛斯冒雨出发（Day 3 04:30） | 村子、广场、王座之间 | 跟梅洛斯冲进雨里（→ 河边，Day 3 11:20）/ 在市里等日没 |
| act.4 三日目 | Day 3 04:30 → 结局 | 归途、广场（日没时变刑场） | —（进入结局） |

### 2.9 WorldEnding（世界结局分类，S-007）

```ts
type WorldEnding = {
  id: string;                      // 写进 Ending.world.outcome
  order: number;                   // 判定顺序：从 1 开始，第一个条件全满足的就是本局的世界结局
  label: string;                   // 日语，结局卡上显示
  when: Condition[];               // 按结局时的 WorldState 判断
  inferred: true;
  note?: string;
};
```

（1.1）S-031 ① 以后，这些分类是**保证一定能到达的底线**，不是结局的全部：叙事者可以按这一局实际发生的事生成新的世界结局（`Ending.world.variant`，第 5 节），但 `Ending.world.outcome` 仍然是按下表判出的底线类，所以 1.0 的校验规则不变。

『走れメロス』的五类（S-034 加了第 4 类；校验工具用 22 个改道情景验证过都能走到，见 `worlds/hashire-merosu/1.0.0-draft/report.md`）：

| order | id | label | 条件 | 例 |
|---|---|---|---|---|
| 1 | `player-substituted` | あなたが身代わりになった | `var.hostage.who == "player"` | 你代替塞利农提乌斯做了人质 |
| 2 | `canon-reunion` | 原作どおりの大団円 | 梅洛斯回来了，且王改心 | 原著 |
| 3 | `in-time-king-unchanged` | 間に合ったが、王は変わらなかった | 梅洛斯回来了，王没改心 | 约定时你嘲弄王，王的信任降到 0 |
| 4 | `king-changed-first` | 王が先に変わった | 王已改心，梅洛斯没回来 | 第二天你先打开了王的心，梅洛斯却迟到了。处刑不执行；人质怎么被放、迟到意味着什么，按这一局生成（S-034） |
| 5 | `too-late` | 間に合わなかった | `var.hostage.fate == "executed"` | 你在河边拖住梅洛斯 |

#### 2.9.1 结局署名（1.1，S-031 ⑤、S-041）

```ts
type EndingSignature = {
  vars: string[];                  // 这些变量的最终值
  beats: string[];                 // 这些节拍是否照原著发生（happened 与否）
  inferred: true; note?: string;
};
```

两局的「世界结局实质不同」= 署名不同：`vars` 的最终值和 `beats` 是否发生，组成的元组不一样。底线类相同、署名不同也算不同的结局。用在两处：结局多样性的统计（S-031 ⑤，data-design 第 9 节）；关键时刻的第三条「预测的世界结局发生实质变化」（S-041，3 节）。『走れメロス』的署名：`vars` = 人质是谁、人质的下场、王的心、梅洛斯的去向、玩家的去向、婚礼；`beats` = 捕缚、召见人质、婚礼、山贼、倒下、（1.4，S-064）セリヌンティウスがちらと疑う、赶到刑场、王改心、緋のマント（beat.04、06、11、19、20、s2、24、26、27）。原著加 22 个改道情景，有 10 种不同的署名。

### 2.10 Affordance 和 Item（1.1，情境动作和物品）

快照里的 `actions`（api-contract 2.3）从这里来（后端评审提案第 7 条）。动作的种类按 UX 的清单（ux-design 18.2、api-contract 3.8）。

```ts
type Affordance = {
  id: string;                      // "aff.river-hold"
  kind: "examine" | "give" | "follow" | "block" | "help" | "wait" | "go" | "shortcut" | "run-together" | "hasten";
  label: string;                   // 按钮上的动词短语（日语），**不写耗时**，前端用 minutes 拼成「引き止める（30分ほど）」（半角数字，ux-design 4.3）
  place: string;                   // 在哪个地点出现
  act?: string;                    // 只在这一幕
  roles?: string[];                // 只对这些身份；省略 = 全部
  target?: string;                 // 对象人物
  item?: string;                   // kind = give 时必填：交出的物品
  minutes: number;                 // 玩家花的故事时间（= 事件的 dt），情境动作在 pacing 的 15〜120 之间
  melos?: "delay" | "hasten";      // 第四幕对梅洛斯的影响（S-036 ②、S-038），前端标出
  melosMinutes?: number;           // （1.4，UX 4.3）有 melos 时必填：梅洛斯到刑场（clock.deadline.watchBeat）会晚（+）或早（−）几分钟，
                                   // 按原著路径估算（校验工具用共享规则核对）。第四幕的按钮写对梅洛斯的影响，不写玩家花的 minutes：
                                   // 「引き止める（30分遅れる）」「浅瀬を探す（10分早まる）」；快照里给的是本局实际值（S-066，见下）
  when?: Condition[];              // 出现条件：快照只给此刻成立的
  aid?: string;                    // 做成了就兑现这条互助（fromYou 的 MutualAid.id）
  playerSpot?: string;             // （1.7）做完以后玩家站在 place 的哪个位置点（布局的 spots，同 ActExit.spot）；省略 = 不挪。
                                   // 只管玩家，人物用 relocate 的 spot。例：「家まで送る」做完站在老爺家门口的旁边
  effects: Effect[];               // 效果模板：判定通过时提交的效果；空 = 只影响关系（生成记忆），不改世界状态
  inferred: true; note?: string; cite?: Cite[];
};

type Item = {
  id: string;                      // "item.water"
  name: string;                    // 日语
  at: string[];                    // 在这些地点随手可得（如有水的地方）；能带在身上的物品写 []
  portable?: true;                 // （1.3）一件实物：同一时刻只在一个人手里（WorldState.holdings），换手靠 hold 效果
  inferred: true; note?: string; cite?: Cite[];    // 设计层；原文里有的物品（短剑）也附出处
};
```

- **R7 和物品：** `give` 要求玩家此刻拿得到这个物品：人在它的 `at` 的地点，或者（1.3）`WorldState.holdings` 里它在玩家手上。不在 `items` 里的东西（现代物品）、不在玩家手上的东西（被没收的短剑）一律 R7 否决（评测 E4-005、E4-010）。
- **随身的东西（1.3，UX 5.1）：** 起点是 `Role.items`（玩家）和 `Character.items`（人物）；之后只靠 `hold` 效果换手：玩家交出（`give` 的效果模板里写 `hold`）、人物兑现互助时交给你（`MutualAid.gives`）、节拍的结果（如捕缚时短剑被没收，`to: null`）。同一件物品开局最多在一个人物手里；不做背包界面，物品只出现在「渡す」这类动作上。
- **S-036 ② 的检查：** 第四幕每个有 `melos: "delay"` 动作的地点，也要有至少一个 `melos: "hasten"` 的动作，耗时同样写在按钮上。`delay` 的动作效果里要有让梅洛斯的节拍 `delayed` 的一条；`hasten` 的要有 `hastened` 或 `prevented`（阻止一个拖慢他的节拍）。
- 动作的实际结果仍由叙事者判定（先判后演，api-contract 3.8）；效果模板是「照常成立时」的效果，情势不同时叙事者可以改写，仍过自检。
- 效果模板里的 `promise` 只写 `change: "made"` 和 `from` / `to` / `text` / `template`，不写 `promiseId`（提交时由叙事者分配 `prm_…`）。
- **（1.4）按钮上的分钟数：** 第四幕带 `melos` 的动作，按钮写对梅洛斯的影响（带正负号）；第一〜三幕照旧写玩家花的 `minutes`。世界模型里的 `melosMinutes` 是原著路径上的估计值（校验和校对用）。**快照里给按钮的是按本局当前排程算的实际值**（S-066 ①）：共享规则 `worldsim.py` 的 `arrival_delta(本局情景, 动作的 effects, 当前时刻)` 返回 `{minutes, inTime}`。已经到了到达下限时，「帮他快」的实际值是 0，按钮不能写「早まる」；由人物或叙事说一次 `clock.deadline.earliestArrivalCue`（1.5，2.6）。`inTime: false` = 做了就来不及。（1.5 写清）这个实际值放在快照的 `actions[].melosMinutes`（api-contract 2.3，v0.3.4），过场选项的放在 `act_ended.options[].enRoute`（api-contract 3.11）。分钟数 = 做和不做各排一次程、看 watchBeat 的差，两次都用去掉 `window.latest` 的排程（拖到来不及也有数）；赶不赶得上看真实排程。在原著路径上它等于世界模型里的 `melosMinutes`。实际值是 0 时按钮写「（変わらない）」（ux-design 4.3）。
- 『走れメロス』现在有 19 个：第四幕 12 个（河边、泉边各一慢一快；山口一慢三快：人人可用的「先に登って様子を見る」（10 分），和绕开山口的脇道（牧童，或听花婿说过路的人，1.5 按 UX 校对 7.4）；进城的路一慢三快：近道（牧童，或听人说过的人）、先跑去报信），身份独有的 4 个（旅人「メロスの身元を保証する」、石屋の弟子「工房を預かる」「親方のそばにいる」、牧童「水を一杯差し出す」），第三幕 3 个（帮妹妹、帮花婿备婚礼，天亮前叫醒梅洛斯）。物品见世界模型的 `items`（1.3：开局带的、互助得到的、原作里的短剑）。


### 2.11 SetPiece（1.7，固定演出，S-080 ④）

有些地の文和人物的话是写好的、每局都一样（切片：城门的警吏、工房关着的门、群众让路）。它们写在世界模型里，由服务端在对的时机下发，前端不按 ID 写死，也不判断条件。它们只是演出：不是事件，不改世界状态，叙事者不改写。唯一的例外是 `learns`：演出里说出了一件事，听的人就知道了（S-077 ⑪：城门的警吏顺口说出约定）。

```ts
type SetPiece = {
  id: string;                      // "piece.gate-taken"
  on: { beat: string } | { act: string; target?: string; refused?: true };
                                   // beat：这个节拍发生（happened / altered）时玩家在节拍的地点（在场，2.4.1 第 4 条）；
                                   // act：玩家的这种动作（api-contract 3.8 的 kind）判定之后。target：对人物的动作写人物 ID，move 写地点 ID，
                                   // go 写出口通往的地点（布局 exits[].place），examine 写可调查物的 ID（obj.*，2.12）；省略 = 不看对象。
                                   // refused = 只在被拒时，省略 = 只在做成时（done / partial）
  after?: string[];                // 这些节拍已经发生（happened / altered）
  before?: string[];               // 这些节拍还没发生
  knows?: { character: string; fact: string }[];  // 这些人物知道这件事：Character.knows 里到这个时刻已经成立的（since），或这一局已提交的 learn
  played?: string[];               // 这些固定演出里至少有一个这一局已经演过
  notPlayed?: string[];            // 这些固定演出这一局都还没演过
  when?: Condition[];              // 别的状态条件（同节拍前提）
  once?: true;                     // 一局只演一次
  lines: ({ narration: string } | { speaker: string; line: string })[];
                                   // 按顺序演：narration = 一行地の文（服务端推 narration { line, ref }，ref = 这条的 id）；
                                   // speaker + line = 这个人物的一句预录（构建时生成，ux-design 16.2，声音按 UX 的文案表），字幕就是 line。
                                   // 预录句怎么下发（manifest 的 cues 那样，或别的）由后端定（B-3）
  learns?: { character: string; fact: string }[];
                                   // 演这一条时谁知道了哪件事（character 可以是 "player"，2.1）。服务端把这些 learn 和这一条的演出同一次提交
                                   // 写进事件（写在动作的事件里还是另写一条，B-3 定）。只给 learn、不给任意 effects：固定演出不过叙事者的
                                   // R1〜R7，能改的状态越少越好；它的 R4 由校验工具静态查（见下）
  inferred: true; note?: string;
};
```

- 同一个时机（同一个节拍，或同一种动作和对象、同样的 `refused`）有几条时，按列表顺序取第一条条件全满足、而且（`once` 的）这一局还没演过的，只演这一条。都不满足就不演，照常由叙事者说。
- `on.act` 的那一条在这个动作的 `action_result` 之后演，代替叙事者对这个动作的叙事（不再另说一遍）；`on.beat` 的演在节拍的那次提交之后。玩家不在场的节拍不演。
- 选哪一条和条件怎么算只有一份：共享规则库 `zoujin_worldsim.pick_set_piece(world, state, hook, played)`（`played` 是这一局演过的固定演出 ID，由服务端记）。`knows` 用同一个库的 `knows(world, state, character, fact)`。
- 校验工具查：ID 唯一；引用的节拍、人物、事实、地点存在；`target` 按动作是存在的人物或地点，`examine` 的是 `objects` 里的可调查物；`played`、`notPlayed` 引用别的固定演出；`learns` 的事实在演的时候一定成立、说的人一定知道（事实的 `trueFrom` 和说话人物 `knows` 的 `since` 都是 `pre` 或写在 `after` 里；只有地の文时只查前一半）；同一个时机上，排在一条没有任何条件的条目后面的永远轮不到，算错。`act` 是不是 api-contract 3.8 的动作、`lines` 的形状由 Schema 查。

### 2.12 WorldObject（1.7，可调查物）

场景里可以「調べる」的东西（例：工房关着的屋门）。服务端按它出快照的 `interactables`（`kind: "examine"`，0 分，api-contract 2.3），不写死；玩家调查时有挂在上面的固定演出（2.11）就演，没有就由叙事者说一行。场景出口不在这里，照布局的 `exits`。

```ts
type WorldObject = {
  id: string;                      // "obj.workshop-door"
  place: string;                   // 在哪个地点（要有场景）
  label: string;                   // 按钮上的字（日语，UX 出），例「戸を叩く」
  spot?: string;                   // 布局里的位置点（前端加）；服务端出快照时要有
  inferred: true; note?: string;
};
```

- 校验工具查：ID 唯一、以 `obj.` 开头；地点存在、有场景；`spot` 在这个地点所在场景的布局里、属于这个地点（同 3.1）；`label` 不为空。

---

## 3. Event（运行时事件，只追加）

叙事者是**唯一写入方**（A-001）。角色的台词不是事件；叙事者从一轮对话和动作里提取候选事件，自检通过后才写入（A-002）。

```ts
type Event = {
  schemaVersion: "1.0" | "1.1" | "1.2" | "1.3" | "1.4" | "1.5" | "1.6";
  eventId: string;                 // ev_…
  playthroughId: string;
  seq: number;                     // 本局内严格递增，从 1 开始；重放按 seq
  turnId?: string;                 // 来自哪一轮（turn_…）；system 事件没有
  idempotencyKey: string;          // 同一轮提交重试时不重复写（后端生成）
  worldModelVersion: string;
  t: number;                       // 发生时的故事时间；按 seq 不递减
  dt: number;                      // 这件事消耗的故事分钟；本事件之后时钟 = max(之前的时钟, t + dt)
  recordedAt: string;
  actor: "player" | "system" | "narrator" | string;  // 或角色 ID，见第 0 节
  type: "say" | "action" | "move" | "beat" | "learn" | "act-transition" | "correction" | "ending"
      | "forget";                  // （1.1）記憶帳删除让一个约定作废，见第 4 节删除语义第 4 条
  origin?: "turn" | "action" | "schedule" | "plan" | "director" | "act" | "memory";
                                   // （1.1）事件从哪来：玩家一轮对话 / 玩家的动作 / 到点的节拍和期限 / 人物的打算 /
                                   // 导演（S-031 ②）/ 幕切换 / 記憶帳删除。只给评测、Trace 和「その頃」排序，不推前端
                                   // （1.6 写清，W-1 评审）schedule 只用于到点的节拍（type = "beat"，只有一条 beat 结果）和期限
                                   // （type = "action"，每局一条，t 不早于 clock.deadline.t）；幕的开始、钟声、天色等别的系统事件不用它
  beneficiary?: "player" | string; // （1.1）这件事是为谁做的；人物为玩家做的事 = "player"（記憶帳「してくれたこと」、结局）
  confirmed?: true;                // （1.1）提交前经过故事里的意图确认（S-040），一局 0〜3 次
  place: string;
  summary: string;                 // 叙事者写的中性日语摘要：只写故事里的行为，不含玩家原话，不含现实个人信息（违反即 R6 失败）
  utteranceRefs?: string[];        // 相关原话 utt_…（可删除；删除后这里保留 ID 但内容取不到）
  causes: string[];                // 因为哪些事件（ev_…）或节拍（beat.…）
  effects: Effect[];
  keyMoment: boolean;              // 提交时算出，（1.1）按 S-041 的四条，见下
  check: CheckResult;
  supersedes?: string;             // 只用于 type=correction：修正哪一条事件（不改旧事件，只追加修正）
  exitId?: string;                 // 只用于 type=act-transition（actor=player）：玩家选的幕末去处，分析用；
                                   // （1.4）也用于过场二选一的 action 事件（origin = "act"，2.8.1 第 2 步）
  plan?: {                         // （1.2，S-031 ③）只用于 type=act-transition（actor=player）且玩家说出了自己的打算；这时没有 exitId（2.8.1 第 2 步）
    label: string;                 // 叙事者的日语转述，像去处的 label 一样短（「夜明けを待って村へ向かう」）；不逐字引用玩家原话
    toAct: string; place: string; t: number;   // 下一幕、起点、开始时间（不早于 Act.start.t）
    with?: string[];               // 同行的人物
  };
};

type Effect =
  | { op: "set"; var: string; value: unknown; from?: unknown }
  | { op: "inc"; var: string; by: number }
  | { op: "beat"; beat: string; to: "happened" | "prevented" | "delayed" | "hastened" | "altered"; minutes?: number; outcomes?: Effect[]; note?: string }
                                   // altered 时 outcomes = 改变后的结果（代替世界模型里的 outcomes）
                                   // （1.6 写清，W-1 评审）本局对一个还没结果的节拍只有一种改动，玩家先后做的几件事这样合：
                                   //   delayed、hastened 按带符号的分钟相加（推迟为正），净值 0 = 没有改动；prevented 顶掉之前的推迟、提前、改写；
                                   //   别的组合（已登记 prevented 之后再改、altered 和推迟或提前混用、第二次 altered）自检不过（共享规则报 bad-state）
  | { op: "learn"; character: string; fact: string }   // 某角色知道了某事实；（1.1）fact 也可以是 rf_…（别人的即兴设定）；（1.7）character 可以是 "player"（2.1）
  | { op: "relocate"; character: string; place: string; spot?: string }  // （1.7）spot = 站在这个地点的哪个位置点，见 3.1 的站位规则
  | { op: "promise"; promiseId?: string; change: "made" | "kept" | "broken" | "voided";  // （1.1）约定，见 3.1 的 Promise；
                                   // （1.6 写清）promiseId 在提交的事件里必带；世界模型的效果模板（2.10）和候选事件不写，提交时由叙事者分配
      from?: "player" | string; to?: "player" | string; text?: string;     // change = made 时必填
      due?: { t?: number; beat?: string }; template?: string }              // 期限（时刻或节拍）；模板 ID（可选）
  | { op: "improv"; factId: string; character: string; statement: string }   // （1.1）即兴设定（S-030 ②），见 3.1 的 RunFact
  | { op: "hold"; item: string; to: "player" | string | null; from?: "player" | string | null };
                                   // （1.3）物品换手：to = 新的持有者（人物 ID 或 player），null = 被拿走、用掉；只用于 portable 的物品

type CheckResult = {
  status: "passed" | "rewritten" | "downgraded" | "rejected";
  attempts: number;                // 共尝试几次（改写上限 2 次，即最多 3）
  failedRules: ("R1-anchor" | "R2-precondition" | "R3-time" | "R4-knowledge" | "R5-persona" | "R6-safety" | "R7-capability")[];
  reason?: string;                 // 给「なぜこうなった？」和评审看的一句日语
  checker: string;                 // 自检用的模型/规则版本
};
```

| 规则 | 检查什么 | 怎么判 |
|---|---|---|
| R1-anchor | 不推翻锚点（`anchors`、`kind: anchor` 的节拍） | 确定性 |
| R2-precondition | 节拍和状态的前提成立；死者不复活；（1.6）变量改成的值满足 `valueRequires`（2.6） | 确定性 |
| R3-time | 时间来得及：路程（`adjacent`、`crossing`）、2.5.1 的排定时间 | 确定性 |
| R4-knowledge | 行为者此刻知道这件事（2.1 防剧透规则） | 确定性 |
| R5-persona | 这个角色会这么做吗、动机成立吗、和之前的事件矛盾吗 | 模型 |
| R6-safety | 内容安全；`summary` 和记忆不含现实个人信息 | 模型 + 规则 |
| R7-capability | 行为者做得到：和对象在同一地点、身份有权限进入（`Role.access` 或事件给的许可）、手里有需要的东西 | 确定性 |

**关键时刻 `keyMoment`（1.1，S-041；api-contract 3.4.1 的 `reveal.kind`）：** 下面任一条成立就是 `true`。

| # | 条件 | 怎么判 |
|---|---|---|
| 1 | 事件让原作的一个节拍 `prevented` / `delayed` / `hastened` / `altered` | 看 `effects` 里的 `op: "beat"` |
| 2 | 梅洛斯的预计到达越过日没线（来得及 → 来不及，或反过来） | 提交前后各用共享规则算一次 `clock.deadline.watchBeat` 的排定时间，和 `deadline.t` 比 |
| 3 | 预测的世界结局发生实质变化 | 提交前后各预测一次「玩家不再做任何事」的结局，**署名**（2.9.1）不同 |
| 4 | 一个人物兑现了为你做的一件大事 | 事件兑现了 `major` 的互助，或叙事者判定同等分量（`beneficiary: "player"`） |

频率目标一局 3〜5 次，数据在评测里统计（data-design 第 9 节）。`StateVar.keyMoment` 和「时钟一次跳过阈值」这两条 1.0 的判据由第 3 条代替（`keyMoment` 变量就是署名里的变量）。

**本局即兴设定（1.1，S-030 ②；后端评审提案第 4 条）：** 人物在原作没写的地方即兴说的设定（过去、喜好、对别人的看法、日常小事），由叙事者从这一轮提取成一句中性日语，用 `improv` 效果记下（`factId` = `rf_…`）。规则：不和有出处的事实、这个人物之前的即兴设定矛盾；不涉及未来（不出现任何事实的 `spoilerTerms`）；不含现实个人信息。记下以后这个人物同一局里前后一致；别的人物只有通过 `learn` 才知道。删除整局时一起删，不跨局（S-012）。

**只推进时钟的事件（1.1，后端评审提案第 8 条）：** 闲聊的一轮也写一条事件：`type: "say"`、`effects: []`、`dt` 按 2.6.1。它对玩家不可见（不进事件列表、地图和「なぜこうなった？」），只推进时钟。

**被否决和被修正是两回事（后端评审第 1 条）：**

- **角色说了做不到的话**（例：答应陪你去王城，但他正被看守）：这句话不是事件，不需要修正。这一轮提取出的候选事件按规则写一条 `check.status = "rejected"`（`effects` 为空，`dt = 0`，`reason` 写原因），后端在给这个角色的下一次局势说明里加「圆回提示」（后端内部，不进契约）。
- **叙事者撤回自己已提交的事件**（例：事后发现某事件违背了一个当时没检查到的前提）：追加 `type: "correction"`、`actor: "narrator"`、`supersedes` 指向旧事件，`effects` 写抵消和修正后的效果。旧事件不改。（1.6 写清）抵消一次推迟或提前 = 同一个节拍反方向的同样分钟数（按上面 `Effect` 的注释相加）。

```ts
type Utterance = {                 // 玩家和角色的原话，单独存放，可删除
  utteranceId: string;             // utt_…
  playthroughId: string;
  turnId: string;                  // turn_…；記憶帳删除时按轮清空（4 节）
  speaker: "player" | string;      // 或角色 ID
  text: string;                    // 识别后的文字（不存音频）
  t: number; recordedAt: string;
  deletedAt?: string;              // 删除后 text 清空
};
// （1.2）两种一轮会当场清空原话（写 deletedAt），而且这一轮不产生事件和记忆：
//   ① 被作废的一轮（「取り消す／言い直す」、识别改正，api-contract 3.6，S-054 ①）。已经 turn_settled 的一轮不能作废（too_late），后果照常。
//   ② 出戏卡暂停的一轮（S-043、S-057）。安全筛查的判定只在 playthrough_metrics 里计数，不写进事件、记忆、局势说明。
```

### 3.1 WorldState（由事件推出，不是第二份事实）

```ts
type Promise = {                   // （1.1）由 promise 效果推出，不单独写（代码里可叫 StoryPromise，避开 JS 的 Promise）
  promiseId: string;               // prm_…
  from: "player" | string;         // 许下的一方
  to: "player" | string;           // 对方
  text: string;                    // 约定的内容（日语，中性，不是原话）
  due?: { t?: number; beat?: string };
  template?: string;               // PromiseTemplate.id
  status: "open" | "kept" | "broken" | "voided";  // まだ / 果たされた / 破られた / 作废（記憶帳删了这条约定的记忆）
  madeBy: string;                  // 成立的事件 ev_…
  resolvedBy?: string;             // 兑现、违背或作废的事件 ev_…
};
// API 里的 direction：from = player → "playerToCharacter"，to = player → "characterToPlayer"（api-contract 2.7）。
// 规则：玩家对人物的约定，相关事件发生时 kept；期限过了还没做到 broken。人物对玩家的约定是他打算的一部分，
// 可以在玩家不在场时兑现。broken 也是有后果的事件（S-029 ③）。只有 open 的约定能变成别的状态。

type RunFact = {                   // （1.1）本局即兴设定
  factId: string;                  // rf_…
  character: string;               // 谁说的（归属于谁）
  statement: string;               // 一句中性日语
  madeBy: string;                  // 记下它的事件 ev_…
};

type WorldState = {
  playthroughId: string;
  asOfSeq: number;                 // 推导到第几个事件
  t: number;                       // 时钟 = 所有事件 max(t + dt)
  vars: Record<string, unknown>;   // 所有 stateVar 的当前值（含 var.act.current、var.player.*）
  beats: Record<string, "pending" | "happened" | "prevented" | "delayed" | "hastened" | "altered">;
  schedule: Record<string, number>;   // 还没结果的节拍的本局排定时间（2.5.1）
  knowledge: Record<string, string[]>; // 角色（1.7：含 "player"）→ 运行时新学到的 fact
  locations: Record<string, string>;   // 角色 → 地点
  spots?: Record<string, string>;      // （1.7）角色 → 指定的位置点：relocate 写了 spot 才有，换到别的地点时去掉
  promises?: Record<string, Promise>;  // （1.1）promiseId → 约定
  runFacts?: Record<string, RunFact>;  // （1.1）factId → 即兴设定
  holdings?: Record<string, "player" | string | null>;  // （1.3）portable 物品 → 现在谁拿着；初值来自 Role.items、Character.items
};
```

规则：`WorldState` = 世界模型初值（身份决定 `var.player.location`、`var.act.current`；（1.3）`holdings` 来自 `Role.items` 和 `Character.items`）+ 按 `seq` 依次应用全部事件的 `effects`。存储时可以缓存，但必须能随时从事件日志重放出完全相同的结果（评测 E7）。

（1.7，C-18）**位置点**（spot）：地点是世界的事实（在不在场按地点算，2.4.1 第 4 条），位置点只是同一个地点里站在哪儿，给前端摆人、给结局演出用，不进任何判定。名字由前端在场景布局（`assets/scenes/<场景>/layout.json` 的 `spots`）里定，世界模型和事件只引用。
- `relocate` 写了 `spot` → `spots[角色] = spot`。没写 `spot`：换到别的地点时去掉这个角色的 `spots`；还在同一个地点时不动（节拍发生时先把参与人物移到节拍地点，已经在那里的人保持原来的位置点）。初值为空。
- 没有 `spots` 的角色由后端按布局的站位规则排：按布局里这个地点的位置点顺序站第一个空着的，`way.*` 和标了 `auto: false` 的除外（那些只给指定用）；玩家站的算占着；`group: true` 的人物不占位置点。
- 玩家的位置点不进 `WorldState`（玩家的地点是 `var.player.location`）：后端在快照里给，跳幕时按 `ActExit.spot` 或 `Act.plan.spot`，做完情境动作按 `Affordance.playerSpot`，都没写就是这个地点的起点（`startSpots`）或原地。
- 校验工具查：`spot`（relocate、`ActExit`、`Act.plan`、`Affordance.playerSpot`）在这个地点所在场景的布局里存在，而且属于这个地点（`scene.json` 的 `spots[].place`）。

### 3.2 导演事件（1.1，S-031 ②、S-045）

叙事者按玩家的行动主动制造变化（有人改主意、新的麻烦、新的机会），写成 `origin: "director"` 的事件；`actor` 是故事里的行为者（第 0 节）。和别的事件一样过 R1〜R7，另加公平规则（后端实现为 D1〜D5，backend-design 2.6）：

1. 不能单独把梅洛斯推过日没线：越线的那一步必须是玩家的选择或玩家知情后的不作为。
2. 造成的时间损失至少留给玩家一次补救机会（够得着的 `hasten` 动作）。
3. 玩家在场时从人物或环境进来，不插在玩家说话的那一轮里；不在场时在「その頃」交代。
4. 每幕在玩家面前最多 1 次；幕切换时最多交代 3 件。
5. 能追到原因：`causes` 里至少有一个玩家或人物的事件。

评测：E7 的 `director_not_sole_cause`（越线的原因链上必须有玩家的举动）。不过的候选直接丢掉，不写成 rejected 事件。

---

## 4. Memory（角色对玩家的记忆）

**只由已提交的事件生成**（叙事者写入），不直接从对话自动抽取，避免角色记住被否决的事。

```ts
type MemoryItem = {
  schemaVersion: "1.0" | "1.1" | "1.2" | "1.3" | "1.4" | "1.5" | "1.6";
  memoryId: string;                // mem_…
  playthroughId: string;
  character: string;               // 谁记得
  kind: "promise" | "help" | "harm" | "shared-moment" | "claim" | "impression";
  text: string;                    // 角色视角的一句日语，給記憶帳显示，如「あの夜、隣に座っていてくれた人」；不含现实个人信息
  fromEvents: string[];            // 来自哪些事件
  t: number;
  trustDelta: number;              // 这条记忆对信任的影响，-20..+20
  salience: number;                // 0..1，检索排序用
  via?: "witnessed" | "told" | "rumor";   // （1.1，UX 10.1）見た / 聞いた / 噂で：按他当时在不在场、事件怎么传到他那里确定性地填
  promiseId?: string;              // （1.1）这条记忆属于哪个约定（prm_…）
  createdAt: string;
  deletedAt?: string;              // 删除后：text 清空，只留 ID 和删除时间（审计用）
};

type Relationship = {              // 不单独存，按记忆推出
  character: string;
  trust: number;                   // = 初值（身份认识则 +10，否则 0）+ 未删除记忆的 trustDelta 之和，截断到 -100..100
  label: string;                   // 由 trust 区间映射，见下表
  level: 1 | 2 | 3 | 4 | 5;        // （1.5 补）同一区间的档位，接口里叫 relationLevel（記憶帳的 5 格刻度，ux-design 10.1）
};
```

| trust | level | label |
|---|---|---|
| ≤ -40 | 1 | 敵意を抱いている |
| -39 〜 -10 | 2 | 警戒している |
| -9 〜 9 | 3 | 様子を見ている |
| 10 〜 39 | 4 | 気を許している |
| ≥ 40 | 5 | 信じている |

文案由 UX 可以改，区间和 level 由数据维护（改了要重跑 E6）。（1.1）最上一档按 UX 10.1 改成「信じている」，区间不变。

**删除语义（S-009 已定）：**

1. 在記憶帳删一条，**立即生效**：该记忆的 `text` 清空、写 `deletedAt`；产生它的事件所在**整轮**的原话（玩家和角色的都清，按 `fromEvents → Event.turnId → Utterance.turnId`）同时清空；信任按剩余记忆重算；后端重写这个角色的局势说明，如果他的语音会话正开着就关掉重建（玩家看到约 1 秒的等待演出）。之后无论问什么，这个角色都不会再提起这件事。
2. **世界里已经发生的事不撤销。** 比如你帮梅洛斯渡了河，删掉梅洛斯的这条记忆后，他照样按时到了，只是不记得是你帮的。结局尾声引用到这件事时，不写「他记得你」。
3. 删除整局（L2）或删除我的全部数据（L3）：硬删除，见 `data-design.md` 5.2、5.3。
4. **（1.1）删除约定类的记忆**（`promiseId` 指向一个 `open` 的约定）：人物不记得这个约定，所以不会再去兑现，也不算违背。叙事者追加一条 `type: "forget"`、`origin: "memory"`、`actor: "player"`、`dt: 0` 的事件，效果 `{op: "promise", change: "voided"}`，`summary` 只写「〜は、その約束を覚えていない」，不写约定内容以外的东西。已经 `kept` / `broken` 的约定不受影响，已经兑现的帮助不撤销（S-009、S-029 ④）。删除确认里加一行「この約束も、なかったことになります。」（api-contract 2.7 的 `voidsPromise`）。

**記憶帳在删除前要让玩家知道的三件事（给 UX 写文案用，PM 评审第 6 条）：**

1. **会删掉的：** 这个角色对你的这条记忆，以及那一轮你和他说的原话。删了以后他不会再提起这件事，对你的态度按剩下的记忆重新算。
2. **不会删掉的：** 世界里已经发生的事。故事记录、连锁反应地图和「なぜこうなった？」里仍然有你当时做了什么（一句中性的描述，不含你的原话）。
3. **想全部删掉：** 删除这一局。这一局的记录、记忆、原话、结局和分析明细都会删除（备份里最长 7 天后消失）。

字段给 UX/前端：記憶帳显示 `character`、`text`、`kind`、`tLabel`、关系 `label`；删除按钮调 `DELETE /v1/playthroughs/{id}/memories/{memoryId}`。

---

## 5. Ending（结局）

```ts
type Ending = {
  schemaVersion: "1.0" | "1.1" | "1.2" | "1.3" | "1.4" | "1.5" | "1.6";
  endingId: string;                // end_…
  playthroughId: string;
  worldModelVersion: string;
  trigger: "deadline" | "story-closed" | "abandoned";   // story-closed = 最后一幕的收幕节拍有了结果
  t: number; decidedAt: string;
  world: {
    outcome: string;               // WorldModel.endings.world[].id（底线类），如 "canon-reunion"
    summary: string;               // 日语
    changedBeats: { beat: string; to: string; causedBy: string[] }[];  // 和原著不同的节拍，各自指回事件
    finalVars: Record<string, unknown>;
    title?: string;                // （1.1）世界结局的一句标题，如「メロスは、間に合った。」
    variant?: {                    // （1.1，S-031 ①）这一局生成的世界结局；没有 = 就是底线类本身（API 的 baseline = true）
      id: string;                  // 本局内唯一，如 "gen.king-abdicates"（API 的 outcomeId）
      title: string; summary: string;
      claims: { var: string; value: unknown }[];  // 它主张的最终状态，必须和 finalVars 一致
      causedBy: string[];          // 至少 2 个本局事件（「讲得通」）
    };
    signature?: Record<string, unknown>;  // （1.1）按 endings.signature 算出的署名（2.9.1），多样性统计用
    contrast?: { original: string; yours: string; beat?: string };  // （1.1，S-026）「原作では…／あなたの世界では…」，选变化最大的节拍
  };
  player: {
    fate: { id: string; label: string; causedBy: string[] };   // 顾问、人质、同行者、目击者、被处刑…
    relationships: { character: string; trust: number; label: string; line?: string; memoryIds: string[] }[];
    title: { text: string; causedBy: string[] };               // 「王に信を説いた旅人」
    epilogue: { sentence: string; cites: string[] }[];         // 每句至少引用一个事件（API 放在 world 下，api-contract 2.8）
    lastScene: { place: string; description: string; present?: string[] };  // （1.1）present = 结局演出里在场的人物（S-053）
    didForYou?: { sentence: string; cites: string[] }[];       // （1.1，D-012）人物为你做的事
    youDid?: { sentence: string; cites: string[] }[];          // （1.1）你为人物做的事
  };
  characters?: CharacterEnding[];  // （1.1，D-015、S-032）7 个可对话人物都在
  card?: {                         // （1.1，S-049、S-051）结局卡，字数由这里保证
    title: string;                 // 称号 ≤ 14 字
    subtitle: string;              // 世界的去向 ≤ 26 字
    contrast: string;              // 「原作との違い」≤ 48 字
    characterLines: { character: string; line: string }[];  // 影响最深的 1〜3 人（1.6 起；1.5 是 2〜3 人），每句 ≤ 40 字
  };
  share?: { cardImageRef?: string; videoRef?: string; branchTreeRef?: string };  // 生成产物的存储引用
};

type CharacterEnding = {           // （1.1）
  character: string;
  rank: number | null;             // 受影响深浅，从 1 起；unchanged 时 null
  unchanged: boolean;              // 玩家没碰过、世界变化也没波及到：只显示「原作どおり」，不生成句子
  original?: string;               // 原作里他的结局，一句（日语）
  yours?: { sentence: string; cites: string[] }[];  // 1〜3 句，「あなたの世界では」，每句至少一个本局事件
};
```

**校验规则：** `world.outcome` 必须等于按 2.9 的顺序对最终状态判出的那一类；`epilogue` 每句 `cites` 非空且都是本局存在的事件；`title`、`fate` 的 `causedBy` 非空；`changedBeats` 与 `WorldState.beats` 一致；全部文字是日语、不含现实个人信息（E8）。不满足就重写一次，仍不满足用模板尾声（后端 6.2）。（1.6 改）模板尾声的局也出结局卡，见下面 1.6 那一段。

（1.1）另加：

- `world.variant.claims` 和 `finalVars` 一致，`causedBy` 至少 2 个本局事件；人物结局和世界结局不矛盾（同样按主张核对）。
- `characters` 每个可对话人物一条；`unchanged: false` 的 `yours` 1〜3 句，每句 `cites` 非空且都是本局事件；`rank` 从 1 起连续。
- `card` 的字数上限按上面（S-051）；`characterLines` 取 `rank` 最前的 1〜3 人（1.6 改，原来是 2〜3 人）。
- **不逐字引用玩家原话**（S-046）：每个文字字段和这一局玩家的每句原话比，先把世界模型里的专有名词（人物名、地名、引文）换成占位符，最长公共子串 ≥ 8 字就不过。这一步在清空原话之前做（S-035）。
- 删过记忆的人物，他的结局和尾声里不写「他记得你」（第 4 节删除语义第 2 条）。
- `lastScene.present` 默认有セリヌンティウス（S-053）；这一局的事件让他不可能在场时不放，`description` 交代他在哪里。
- 越过日没线的原因链上必须有玩家的举动（3.2 第 1 条），评测 E7 `director_not_sole_cause`。

（1.6，C-17）结局卡和必写的字段：

- **每一局都出结局卡。** 生成的结局：`characterLines` 取 `rank` 最前的 1〜3 人，排得上几人放几人。一个人物也没排上名（全部 `unchanged`）时，放梅洛斯一句，按他的 `original` 写（每一局的世界结局都围着他）。所以卡上至少 1 行。
- **模板尾声的局也出卡**（S-065 降级）：按这一局的 `world.outcome`，以及 `var.player.custody`、`var.melos.custody`，挑 ux-design 11.4 对应的那一组，`card` 的字段全用那一组的预写句子（称号里填开局身份）。人物行只放那一组写好的（1〜2 行）。句子不抄进本契约，以 ux-design 11.4 为准。
- **1.6 起写入的结局，这几个字段必写**（类型里仍是可选，1.5 及以前的文档照旧合法；Schema 按 `schemaVersion` 判）：`world.title`（模板尾声的局写世界模型 `endings.world` 里这一类的 `label`）、`player.didForYou` 和 `player.youDid`（没有就写空数组）、`characters`、`card`。接口（api-contract 2.8）要这几个字段。

---

## 6. 『走れメロス』片段示例

完整草稿见 `worlds/hashire-merosu/1.0.0-draft/world.json`（由 `world.src.json` 经校验工具生成：出处全部逐字核对通过，错误 0；数字见那里的 `report.md`）。下面是其中几条。

```json
{
  "facts": [
    { "id": "fact.promise", "statement": "王はメロスに三日目の日没までに戻れと命じ、遅れたら身代りを殺すと言った。身代りはセリヌンティウス。",
      "trueFrom": "beat.05", "visibility": "public",
      "cite": [{ "source": "aozora:1567_ruby_4948@sha256:2a437c047d7f", "para": 22, "quote": "三日目には日没までに帰って来い。" }] }
  ],
  "beats": [
    { "id": "beat.11", "order": 11, "title": "真昼の婚礼", "summary": "婚礼が真昼に行われる。",
      "window": { "earliest": 3300, "latest": 4000, "canonical": 3600 },
      "place": "place.melos-home", "participants": ["char.melos", "char.sister", "char.groom"],
      "kind": "mutable", "preconditions": [{ "var": "var.groom.agreed", "op": "==", "value": true }],
      "outcomes": [{ "op": "set", "var": "var.wedding.status", "value": "held" }],
      "cite": [{ "source": "aozora:1567_ruby_4948@sha256:2a437c047d7f", "para": 32, "quote": "結婚式は、真昼に行われた。" }] }
  ],
  "causal": [
    { "id": "edge.10-11", "from": "beat.10", "to": "beat.11", "type": "requires",
      "note": "花婿の同意がなければ婚礼は挙げられない", "inferred": false,
      "cite": [{ "source": "aozora:1567_ruby_4948@sha256:2a437c047d7f", "para": 32, "quote": "説き伏せた。結婚式は、真昼に行われた。" }] }
  ]
}
```

（`canonical: 3600` = Day 2 12:00 = 2×1440 + 720。）

一个事件的样子（玩家在约定的场面嘲弄王）：

```json
{ "schemaVersion": "1.0", "eventId": "ev_01J…", "playthroughId": "pt_01J…", "seq": 7, "turnId": "turn_01J…",
  "idempotencyKey": "turn_01J…#0", "worldModelVersion": "hashire-merosu@1.0.0",
  "t": 1235, "dt": 5, "recordedAt": "2026-10-06T12:00:00Z",
  "actor": "player", "type": "say", "place": "place.castle",
  "summary": "旅人は王の前で、人を信じられぬ王を嘲った",
  "utteranceRefs": ["utt_01J…"], "causes": ["beat.05"], "origin": "turn",
  "effects": [{ "op": "inc", "var": "var.king.trust", "by": -20 }],
  "keyMoment": false,
  "check": { "status": "passed", "attempts": 1, "failedRules": [], "checker": "rules@1.0+gemini-3.8-flash" } }
```

（1.1）一个约定成立的事件（石屋の弟子答应替师父看工坊，S-048 的开局互助）：

```json
{ "seq": 4, "t": 1080, "dt": 10, "actor": "player", "type": "say", "origin": "turn", "place": "place.stonemason-workshop",
  "summary": "弟子は、親方の留守のあいだ工房を守ると約束した", "causes": [],
  "effects": [{ "op": "promise", "promiseId": "prm_01J…", "change": "made", "from": "player", "to": "char.selinuntius",
                "text": "工房を守る", "template": "promise.selinuntius.workshop" }],
  "keyMoment": false, "check": { "status": "passed", "attempts": 1, "failedRules": [], "checker": "rules@1.1+…" } }
```

---

## 7. 已定和待定

| # | 问题 | 结果 |
|---|---|---|
| C-1 | 删记忆要不要撤销后果 | **已定**：不撤销，只让角色忘记（S-009） |
| C-2 | 记忆用 Memory Bank 还是自己的表 | **已定**：自己的表（S-016） |
| C-3 | Firestore 还是 PostgreSQL | **已定**：Cloud SQL PostgreSQL（S-016） |
| C-4 | summary、記憶帳文案的语言 | **已定**：日语（S-008） |
| C-5 | 年龄段、昵称 | **已定**：都不收集，字段保留但没有入口（S-010） |
| C-6 | 故事时间怎么走 | **已定**：按行动消耗时间，只由事件推进（S-005、S-021）；参数按 S-038 写进 `pacing`（2.6.1） |
| C-7 | 「王先改心、梅洛斯却迟到」落不进 4 类世界结局 | **已定**：加第 5 类底线「王が先に変わった」（S-034，2.9） |
| C-8 | 玩家什么都不做时数据留多久 | **已定**：进行中的局 30 天没操作自动删，原话在结局生成后立即清空等（S-035，data-design 5.5） |
| C-9 | 模型服务商侧的保存条款 | **已定**（S-059）：只用正式版模型；正式环境不开 Live 会话恢复，关掉模型侧 24 小时缓存；被判为可疑的请求可能留 90 天供滥用审查，写进隐私政策（data-design 5.3、第 11 节） |
| C-10 | 原著路径余量为零：梅洛斯晚一分钟就来不及 | **已定**：保持为零，帮他快和让他慢一样容易（S-036；2.10 的检查） |
| C-11 | 结局多样性的门槛：最常见的世界结局占比上限、不同署名至少几种（S-031 ⑤） | **已定**（S-061）：200 局模拟局（10 种画像各 20 局）里，最常见的底线类 ≤ 60%，不同署名 ≥ 8，5 类底线都到达〔待验证，R1 后调〕 |
| C-12 | 导演事件用 `origin: "director"` 标出，`actor` 写故事里的行为者，而不是 S-031 ② 原文写的 `actor: "narrator"` | **已定**（S-062）：`actor` 保持 1.0 的含义，和后端设计 2.6、api-contract 2.6 一致 |
| C-13 | 2.4.1 第 3 条的例外（有时间边的节拍当场记 prevented）和 2.5.1 的 `timeLink: "order"` 是写清，不是改语义 | **已定**（S-063）：记为写清；默认值和 1.0 行为一样 |
| C-14 | 能带在身上的物品（如妹妹给的便当）和「交给」的效果 | **已定**（1.3，按 UX 5.1「随身的东西」）：`Item.portable`、`Role.items`、`Character.items`、`MutualAid.gives`、`hold` 效果、`WorldState.holdings`（2.10） |
| C-15 | 第三、四幕「帮他快」的动作全做，梅洛斯最多早到多少；超过一个半小时左右第四幕就不紧张（UX 校对 1.1） | **已定**（S-066）：不设上限能早 190 分，封顶在 17:30（`clock.deadline.earliestArrival`，日没前 90 分）〔待验证，R1 后调〕；单个动作分钟数不变；拖慢不受上限影响；按钮显示按本局实际还能早多少（2.10） |
| C-16 | 有两条取值条件只写在说明文字里，第 3 步判不了（S-2 标注时发现）：王的心设成「揺れている」要 `var.king.trust` ≥ 40，期限前改心要 ≥ 70；`var.river.crossing = bridge` 要桥还在 | **已定**（后端、PM 2026-10-10）：1.5 照约定冻结（C-2），冻结后第一个加字段的版本 1.6 加 `StateVar.valueRequires?: { value; when: Condition[]; note: string; inferred: true; cite?: Cite[] }[]`。后端不写死阈值，叙事者第 3 步只读数据，所以 **S-2 测量集开跑前要合并 1.6**。语义（也写进 Schema 的 description）：① 只管非 `system` 的事件，节拍的结果由节拍前提管（例：刑场的 `beat.26`）；② 只在值真的变化时判，设成和现在一样的值不判；③ 按这个 effect 之前的状态判（同一事件里前面的 effect 已生效，先升信任再设 `wavering` 能过，反过来不过）；④ `when` 用和节拍前提同一个 `Condition` 类型和求值函数，不成立报 R2，`reason` 带变量、`value` 和这一条的 `note`；⑤ 设好以后条件不再成立（信任又掉到 40 以下）不自动改回、不算违规，改不改回是剧情的事。世界模型自检加两项：`value` 在这个 StateVar 的取值里；`when` 引用的变量和节拍都存在。W-1 黄金测试加：39 被拒、40 能过；顺序两种；系统事件不受限；桥不在时设 `bridge` 被拒；值没变不判。参考实现、Schema、world.json 同一个 PR 改，后端评审。**1.6 已落地**（2.6「取值条件」） |
| C-17 | 结局卡的人物 2〜3 人时，只有 1 个人物排得上的局没有卡；模板尾声的局也没有卡（UX 10-10 发现） | **已定**（UX ux-design 11.3、11.4，PM 2026-10-10）：1.6 放宽到 1〜3 人，一个也没排上名时放梅洛斯；模板尾声的局也出卡，字段取 ux-design 11.4 那一组；1.6 起写入的结局 `world.title`、`didForYou`、`youDid`、`characters`、`card` 必写（第 5 节） |
| C-18 | M2 切片要写清谁站在刑场的哪儿（柱上的セリヌンティウス、群众背后的王、玩家身边的老爺）和去处落地的那一行；位置点名只在前端的布局里，世界模型写不了 | **已定**（数据、前端 10-10，UX 10-10）：1.7 加 relocate 和 `ActExit` 的 `spot`、`WorldState.spots`、`Character.group`、`ActExit.arrival`（3.1 站位规则；前端 #22 加了 `auto: false` 的点）；幕末页副题的后半 `ActExit.sub`（UX、前端在 #24 评审时提，PM 同意） |
| C-19 | 幕末说出的打算成行时，下一幕从哪儿、几点开始，落在哪个位置点、落地说什么（2.8.1 第 2 步的 `plan` 由叙事者写，切片要一个固定的默认） | **已定**（后端 10-10）：1.7 给 `Act` 加可选的 `plan`（toAct、place、t、spot、effects、arrival，同 ActExit 的同名字段），不用「第一个去处」：显式、不依赖去处的顺序。叙事者成行时下一幕、地点、时间、落点、落地和固定的效果都从这里读，打算自己的效果照常提取、检查后加在同一条事件上，`plan.label` 是叙事者的转述。没有 `Act.plan` 的幕（完整版）由叙事者按世界模型判，M3 再定 |

---

变更记录：

- v0.1（2026-10-06）：初稿。
- v0.1.1（2026-10-06）：新增 `globalRules`、`Clock.onDeadline`、`Place.crossing`、`Place.inferred`、`Role.note`。
- **v1.0（2026-10-06）**：按后端、PM 评审修改。
  - 新增：`Scene`、`Act`/`ActExit`（S-004）、`WorldEnding`（S-007）、`Clock.labels`、`pacing`、`Role.release`/`startAct`（S-002）、`Fact.spoilerTerms`、`Condition.inferred/note`、`CausalEdge.minutes`、`StateVar.keyMoment`/`visibleToPlayer`/`valueLabels`、`Event.turnId`/`keyMoment`/`exitId`、`Utterance.turnId`、`WorldState.schedule`、`Playthrough.lastActiveAt`、`turn_` 前缀、R7-capability。
  - 改动：`Event.type` 的 `"act"` 改名为 `"action"`（避免和「幕」混淆），新增 `"act-transition"`，去掉 `"clock"`（时钟由 `dt` 推进）；`actor` 含义写清（system = 到点自然发生，narrator 只用于 correction）；`Ending.trigger` 去掉 `player-death`。
  - 写清：节拍是默认时间表（2.4.1）、时间传播规则（2.5.1）、幕切换顺序（2.8.1）、被否决和被修正的区别、L1 删除按整轮清原话并立即生效、个人信息规则扩到 summary 和结局。
  - 世界模型 ID 和前端、后端对齐：`char.king`、`place.syracuse-square`、`place.stonemason-workshop`、`place.mountain-pass`、`place.spring`。
- **v1.1（2026-10-06）**：只做加法（S-033）。对应 D-012〜D-015、S-029〜S-053、后端设计 v1.0 第 12 节 13 条、UX 设计 v1.0 第 18.3 节。
  - WorldModel：`CausalEdge.timeLink`（2.5.1）、`endings.signature`（2.9.1）、`pacing` 的键（2.6.1）、`pacingNote`、`affordances` 和 `items`（2.10）；`Character.mutualAid` / `promiseTemplates` / `plans` / `initialActivity`，`traits` / `goals` / `sampleLines` 的 `since` / `until`；`Beat.activities`；`Clock.deadline.watchBeat`、`Clock.labels.format` 改为模板（『走れメロス』用「{day}・{band}」）、`labels.cite`；`Role.conditionalAccess`。
  - Event：`origin`、`beneficiary`、`confirmed`；`type: "forget"`；效果 `promise`、`improv`；`learn` 可以学即兴设定；`keyMoment` 按 S-041 的四条。WorldState：`promises`、`runFacts`。新增 3.2 导演事件。
  - Memory：`via`、`promiseId`；最上一档标签「信じている」；删除约定类记忆让约定作废（删除语义第 4 条）。
  - Ending：`world.title` / `variant` / `signature` / `contrast`，`player.didForYou` / `youDid`，`lastScene.present`，`characters`（`CharacterEnding`），`card`；不逐字引用原话等校验规则。
  - 写清：2.4.1 第 3 条的例外（有时间边的节拍当场记 prevented，C-13）；「その頃」的范围和排序（2.8.1 第 5 步）；R7 的进入权限和物品。
  - 世界结局底线改为五类（S-034）；第 7 节 C-7、C-8、C-10 已定，新增 C-11〜C-13。
- **v1.2（2026-10-06）**：只做加法。
  - 幕末去处改称推荐去处，玩家可以说出自己的打算（S-031 ③）：`Event.plan`，2.8.1 第 2、4 步。
  - 写清：被作废的一轮和出戏卡暂停的一轮当场清空原话、不产生事件和记忆（S-054 ①、S-043、S-057，Utterance 下的注释）。
  - 第 7 节：C-9（S-059）、C-11（S-061）、C-12（S-062）、C-13（S-063）已定；新增 C-14 能带在身上的物品。
- **v1.3（2026-10-06）**：只做加法。随身的东西（UX 5.1，C-14 结案）：`Item.portable`、`Role.items`、`Character.items`、`MutualAid.gives`、效果 `hold`、`WorldState.holdings`；R7 的「拿得到」加上「在玩家手上」。
- **v1.5（2026-10-06）**：只做加法。按 UX 对 1.4 的复核（`ux/reviews/data-world-draft3.md` 第 7 节）和后端 api-contract v0.3.4。
  - WorldModel：`EnRouteChoice`（从 `EnRoute.choices` 抽出来）加 `melosMinutes`、`after`（2.8、2.8.1 第 2 步）。
  - （2026-10-07 补，接口一致性核对 D-1）第 4 节：关系表加 `level` 列（1〜5），`Relationship.level` 就是 api-contract 的 `relationLevel`。区间和标签不变。
  - WorldModel：`Clock.deadline.earliestArrivalCue`（第一次到下限时说的一句，S-066 ①，ux-design 4.3）。
  - **改正 1.4 的到达下限算法**（2.5.1）：改为按节拍顺序逐步算，到了下限再帮快是 0、拖慢照算、拖慢之后再帮快最多回到下限。1.4 的写法让拖慢之后的帮快也是 0，和 S-066 ①、ux-design 4.3 不一致。
  - 写清：按钮实际值放在哪个接口字段、怎么算（2.10）；按钮上的时间用半角数字（2.10 的例子）。
  - 『走れメロス』（draft.3）：山口的脇道只给牧童和听花婿说过路的人，按钮不写「山賊」；人人可用的改成「先に登って様子を見る」（10 分，不省体力，梅洛斯照样倒下、照样怀疑）；`edge.18-20` 只管先后。
- **v1.4（2026-10-06）**：只做加法。按 UX 对世界模型 draft.3 的校对（`ux/reviews/data-world-draft3.md`）和 S-064。
  - WorldModel：`Clock.deadline.earliestArrival`（S-066，2.5.1）；`traits` / `goals` / `sampleLines` 的 `when`；`speech.designLines`（`DesignLine`）；`MutualAid.effects`；`PromiseTemplate.note`；`Beat.variants`（`BeatVariant`，2.4.1 第 2 步）；`ActExit.enRoute`（`EnRoute`，2.8.1 第 2 步）；`Affordance.melosMinutes`（2.10）；`globalRules` 的 `cite`。
  - Event：`exitId` 也用于过场二选一的 action 事件。
  - 写清：`requires` 的「发生了」包括 `altered`；`Fact.trueFrom` 的节拍本局没发生，这条事实本局不成立（2.3）；`valueLabels` 没写的取值不当场显示（S-067）；按钮上的实际分钟数用共享规则的 `arrival_delta`（S-066）。
  - 第 7 节新增 C-15，已定（S-066）。
- **1.5 冻结（2026-10-10，M2-0，C-2）**：字段不变；以后只做加法，新增可选字段走 1.6、1.7…；Schema 在 `packages/contracts/schemas/data/`，CI 按它校验世界模型和评测集，并和本文的类型逐个对照。同时写清：第 0 节静态 ID 补上 `world.json` 已在用的 `exit.`、`rule.` 前缀，世界结局的 ID 不带前缀；第 6 节事件例子去掉和类型（`reason?: string`）不一致的 `"reason": null`。
- **v1.6（2026-10-10）**：冻结后第一个加法版本。
  - WorldModel：`StateVar.valueRequires`（2.6「取值条件」，C-16）。『走れメロス』（draft.3）写上王的心（信任 40 / 70）和过桥（桥还在）三条；情景「王が先に変わった」的事件先把信任设到 70。
  - Ending：`card.characterLines` 放宽到 1〜3 人，一个也没排上名时放梅洛斯；模板尾声的局也出卡；1.6 起写入的结局 `world.title`、`player.didForYou` / `youDid`、`characters`、`card` 必写（第 5 节，C-17）。读的一方要能排 1 行。
  - 写清（C-2 评审定的两件事）：状态变量 ID 的段里可以用驼峰（第 0 节）；`Effect.promise` 的 `promiseId` 在类型里可选，提交的事件必带（第 3 节）。
  - R2 加上 `valueRequires`（第 3 节规则表）。只有到点的节拍和期限（`origin: "schedule"`）不判；导演事件的 `actor` 也是 `system`，照样判（后端评审）。
  - 写清（后端评审 W-1，2026-10-10）：同一个节拍的几次改动怎么合（第 3 节 `Effect` 的注释；以前共享规则换方向时整条替换，先拖慢 30 再帮快 10 成了帮快 10）；`origin: "schedule"` 只用于到点的节拍和期限（第 3 节）。
- **v1.7（2026-10-10）**：只做加法（C-18）。M2 切片要的位置点和落地。
  - WorldModel：`Character.group`；`ActExit.spot`、`ActExit.arrival`（2.8、2.8.1 第 4 步）；`ActExit.sub`（幕末页副题的后半，以前写在 UX 的文案表里、前端按去处 ID 对）；`Affordance.playerSpot`（做完以后玩家站哪，后端 10-10 提）；`Act.plan`（打算成行时的落点，2.8.1 第 2 步，C-19）；`WorldModel.setPieces`（固定演出：节拍或玩家的动作上写好的地の文和预录句，2.11，S-080 ④，PM 10-10 定放进切片世界模型）；`WorldModel.objects`（可调查物，2.12，后端 10-10 提：服务端按它出快照的 interactables）；`SetPiece.learns`（演出里说出的事，听的人就知道了，S-077 ⑪，PM 10-10 定：城门的警吏立约以后赶人时说出约定）。
  - Event：`relocate` 效果的 `spot`。WorldState：`spots`。站位规则和校验写在 3.1。
  - 玩家知道什么（2.1，PM、后端 10-10 评审 #33 时提）：`learn` 的 `character` 可以是 `"player"`；人物告诉玩家时叙事者提取，玩家在节拍的地点时共享规则库给 public 事实写进节拍的系统事件；R4 对玩家 = 身份的 `initialKnowledge` + 学到的。
  - 第 7 节新增 C-18、C-19（已定：打算成行时的落点用 `Act.plan`）。
  - 『走れメロス』（draft.3）：群众、警吏、山贼、一团旅人 `group: true`；beat.s1 セリヌンティウス站 `stake`、王站 `king-west`，beat.24 梅洛斯站 `scaffold`（布局见前端 #22）。同一个 PR 里的世界模型修正：群众、少女第一幕在广场的家里（`absent`），beat.s1 到刑场；beat.04（捕缚）挪到王城前庭（`place.execution-ground`）；送老爺回家记 `var.player.walkedOldManHome`（说话兑现，或第一幕的情境动作「家まで送る」`aff.walk-old-man-home`，30 分，UX 10-10）；警吏从 beat.05 起知道约定（`knows`，PM 10-10：警吏在殿上，城门的固定演出靠它说出约定，S-077 ⑪）。
