"""World state → what the frontend sees: the snapshot (api-contract 2.3), the events visible to the player (2.4), and
the commit patch (3.4).

The snapshot and commit use the same projection: patch = the difference between the snapshots before and after commit.

The B-0 projection only does what the skeleton can give: the characters in the scene (spots per contract 3.1: one named
by relocate stands there, `group` ones take no spot, the rest are assigned by layout; activity is the part the world
model gives, W-1's `activity()`; anyone not present right now is absent and can't be talked to (B-2, S-077 ⑩);
relationships are omitted while there are none), whether places can be entered, scene exits, the deadline, and Melos's
expected arrival.

B-3 added: situational actions (the world model's affordances that hold right now), examinable objects (objects), exits
that are always clickable (whether they are blocked is up to the check, S-077 ③), the player's spot (recorded on the
run, `Run.player_spot`), the deadline line depending on whether the player knows about the promise (S-077 ⑫),
`pending.actEnd` and `pending.arrival`. Relationships, memories and other pending things belong to the M2 cards.

世界状態 → フロントエンドに見えるもの：スナップショット（api-contract 2.3）、プレイヤーに見えるイベント（2.4）、
commit の patch（3.4）。

スナップショットと commit は同じ投影を使う：patch = コミット前後の 2 つのスナップショットの差分。

B-0 の投影は骨組みで出せるものだけ：場面にいる登場人物（立ち位置は契約 3.1 に従う。relocate で指定された者は
そこに立ち、`group` の者は立ち位置を取らず、残りはレイアウトで割り当てる。activity は世界モデルが出す部分で
W-1 の `activity()`。いまその場にいない者は absent で話しかけられない（B-2、S-077 ⑩）。関係がまだないものは
関係を省く）、場所に入れるか、場面の出口、期限とメロスの到着予定。

B-3 で追加：状況アクション（世界モデルの affordances のうちいま成り立つもの）、調べられる物（objects）、
出口は常に押せる（止めるかどうかは判定が決める、S-077 ③）、プレイヤーの立ち位置（ゲームに記録したもの、
`Run.player_spot`）、プレイヤーが約束を知っているかで変わる期限の行（S-077 ⑫）、`pending.actEnd` と
`pending.arrival`。関係、記憶、その他の保留中のものは M2 の各カードの担当。
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from zoujin_worldsim import SimState, activity, apply, arrival_delta, flat, initial_state, knows, sees, world_state

from zoujin_backend.db.store import Run
from zoujin_backend.world import Book

Json = Any

# The deadline and expected arrival are shown only once the player knows about the promise (S-077 ⑫, api-contract 2.3).
# 期限と到着予定は、プレイヤーが約束を知ってから表示する（S-077 ⑫、api-contract 2.3）。
PROMISE_FACT = "fact.promise"
# The second half of the deadline line (the example in api-contract 2.3); replace it once UX settles the copy.
# 期限の行の後半（api-contract 2.3 の例）。UX が文言を決めたら差し替える。
DEADLINE_TAIL = "遅れれば、身代わりが死ぬ"
VOICE = {"enabled": True, "degraded": False, "minutesLeftToday": 60}  # the budget is an M2 card / 予算は M2 のカード
PENDING = {"reveal": None, "confirm": None, "actEnd": None, "safetyPause": False, "approach": None}
CLOSED = "いまは入れない"
COMMITTED = ("passed", "rewritten", "downgraded")


# —— Events / イベント ——


def committed(ev: Mapping[str, Any]) -> bool:
    return bool(ev["check"]["status"] in COMMITTED)


def _beat_label(book: Book, beat: str, change: str, variant: str | None = None) -> str:
    b = book.beats[beat]
    if change in ("happened", "altered"):
        if variant:
            for v in b.get("variants", []):
                if v["id"] == variant and v.get("summary"):
                    return str(v["summary"])
        return str(b["title"])
    return f"「{b['title']}」" + {"prevented": "は起きなかった", "delayed": "が遅れる", "hastened": "が早まる"}[change]


def visible_effects(book: Book, effects: Sequence[Mapping[str, Any]]) -> list[Json]:
    """2.4's visibleEffects: visible variables (label only) and beat changes.

    2.4 の visibleEffects：見える変数（ラベルだけ）とビートの変化。
    """
    svars = {v["id"]: v for v in book.world["stateVars"]}
    out: list[Json] = []
    for e in effects:
        if e.get("op") == "set":
            v = svars.get(e.get("var", ""))
            labels = (v or {}).get("valueLabels") or {}
            key = str(e["value"]).lower() if isinstance(e.get("value"), bool) else str(e.get("value"))
            if v and v.get("visibleToPlayer") and key in labels:
                out.append({"kind": "var", "var": e["var"], "label": labels[key]})
        elif e.get("op") == "beat" and e.get("beat") in book.beats:
            out.append(
                {
                    "kind": "beat",
                    "beat": e["beat"],
                    "change": e["to"],
                    "label": _beat_label(book, e["beat"], e["to"], e.get("variant")),
                }
            )
    return out


def promise_change(effects: Sequence[Mapping[str, Any]]) -> Json | None:
    for e in effects:
        if e.get("op") == "promise" and e.get("promiseId"):
            return {"promiseId": e["promiseId"], "change": e["change"]}
    return None


class Away:
    """Events settled in step 3 of an act transition (contract 2.8.1) always count as the player not being present and
    aren't pushed (they are left for 「その頃」). Judged from the events themselves: after the player's step-2
    `act-transition` (origin act) and before the system's step-4 `act-transition`, the ones whose origin isn't act
    (settled by the data side in #149, no field added). Feed every event in seq order (including ones outside the
    range that gets pushed); those that return True aren't pushed.

    幕切り替えの第 3 ステップ（契約 2.8.1）で精算するイベントは、プレイヤーは常にその場にいないとみなし、
    プッシュしない（「その頃」に回す）。イベント自体から判断する：第 2 ステップのプレイヤーの `act-transition`
    （origin act）の後、第 4 ステップのシステムの `act-transition` の前で、origin が act でないもの（データ側が #149 で
    決めたもので、フィールドは追加しない）。seq 順にすべてのイベントを渡す（プッシュ対象の範囲外のものも渡す）。
    True を返したものはプッシュしない。
    """

    def __init__(self) -> None:
        self.on = False

    def __call__(self, ev: Mapping[str, Any]) -> bool:
        if ev.get("origin") == "act" and ev.get("type") == "act-transition":
            self.on = ev.get("actor") == "player"
            return False
        return self.on and ev.get("origin") != "act"


def is_visible(book: Book, ev: Mapping[str, Any], player_place: str) -> bool:
    """Section 0: it changes a visible variable or a beat (or a promise), and the player can see it (`sees()` from data
    contract 1.12 section 3: the player did it, the player is at the event's place, or it is a beat with no
    participating characters that lands in the same scene as the player). player_place is the player's place before
    this event. Rejected events aren't pushed.

    第 0 節：見える変数かビート（または約束）を変え、しかもプレイヤーに見えるもの（データ契約 1.12 第 3 節の
    `sees()`：プレイヤーがしたこと、プレイヤーがイベントの場所にいる、または参加する登場人物のいないビートで
    プレイヤーと同じ場面で起きる）。player_place はこのイベントの前のプレイヤーの場所。却下されたものはプッシュしない。
    """
    if not committed(ev):
        return False
    if not visible_effects(book, ev["effects"]) and promise_change(ev["effects"]) is None:
        return False
    return sees(book.world, player_place, ev)


YOU = "あなた"
ENDS = ("。", "！", "？", "!", "?")


def as_you(book: Book, role_id: str, text: str, *, period: bool = False) -> str:
    """In event sentences sent to the frontend the player is always 「あなた」: replace this game's role name (the
    stored summary keeps the role name; the model, the checks and evals read that one). Characters whose names contain
    the role name are left alone (a fallback: since contract 1.8 the data self-check doesn't let character names
    contain a role name).
    period: add 「。」 if the sentence doesn't end with one (recapLines, 「その頃」; a commit summary gets none, since
    the frontend puts it in brackets).

    フロントエンドに送るイベント文では、プレイヤーは常に「あなた」：このゲームの役柄名を置き換える（保存する summary は
    役柄名のままで、モデル・チェック・評価はそちらを読む）。名前に役柄名を含む登場人物は置き換えない（保険：契約 1.8
    以降、データのセルフチェックで登場人物名に役柄名を含めないようにしている）。
    period：文末に「。」がなければ補う（recapLines、「その頃」。commit の summary には補わず、
    フロントエンドが括弧に入れる）。
    """
    name = str(book.roles[role_id]["name"])
    keep = sorted(
        {str(c["name"]) for c in book.characters.values() if name in str(c["name"]) and c["name"] != name},
        key=len,
        reverse=True,
    )
    for i, k in enumerate(keep):
        text = text.replace(k, f"\x00{i}\x00")
    text = text.replace(name, YOU)
    for i, k in enumerate(keep):
        text = text.replace(f"\x00{i}\x00", k)
    if period and text and not text.endswith(ENDS):
        text += "。"
    return text


def visible_event(book: Book, ev: Mapping[str, Any], role_id: str) -> Json:
    out: Json = {
        "eventId": ev["eventId"],
        "seq": ev["seq"],
        "t": ev["t"],
        "dt": ev["dt"],
        "tLabel": book.label(ev["t"]),
        "type": ev["type"],
        "actor": ev["actor"],
        "forPlayer": ev.get("beneficiary") == "player",
        "place": ev["place"],
        "summary": as_you(book, role_id, str(ev["summary"])),
        "causes": list(ev["causes"]),
        "visibleEffects": visible_effects(book, ev["effects"]),
        "promise": promise_change(ev["effects"]),
        "keyMoment": ev["keyMoment"],
        "supersedes": ev.get("supersedes"),
    }
    if ev.get("turnId"):
        out["turnId"] = ev["turnId"]
    return out


def visible_events(
    book: Book, role_id: str, log: Sequence[Mapping[str, Any]], after_seq: int, limit: int | None = None
) -> list[Json]:
    """2.4: the game's events visible to the player with seq greater than after_seq, at most limit of them (shared by
    the gateway's `GET …/events` and the eval's `view()`). Presence is judged by the state before each event; events
    that only change time, that the player wasn't present for, or that were rejected take a seq but aren't here.

    2.4：ゲームのイベントのうち、プレイヤーに見えて seq が after_seq より大きいもの、最大 limit 件（ゲートウェイの
    `GET …/events` と評価の `view()` で共通）。その場にいたかは各イベントの直前の状態で判断する。時間だけを変えたもの、
    プレイヤーがいなかったもの、却下されたものは seq を使うがここには出ない。
    """
    state = initial_state(book.world, role_id)
    away = Away()
    out: list[Json] = []
    for ev in log:
        skipped = away(ev)
        if ev["seq"] > after_seq and not skipped and is_visible(book, ev, state["vars"]["var.player.location"]):
            out.append(visible_event(book, ev, role_id))
            if limit is not None and len(out) >= limit:
                break
        state = apply(book.world, state, ev)
    return out


# —— Snapshot / スナップショット ——


def _holds(conds: Sequence[Mapping[str, Any]], values: Mapping[str, Any]) -> bool:
    ops = {
        "==": lambda a, b: a == b,
        "!=": lambda a, b: a != b,
        ">=": lambda a, b: a >= b,
        "<=": lambda a, b: a <= b,
        ">": lambda a, b: a > b,
        "<": lambda a, b: a < b,
    }
    return all(ops[c["op"]](values.get(c["var"]), c["value"]) for c in conds)


def place_open(book: Book, role_id: str, place: str, state: SimState) -> bool:
    role = book.roles[role_id]
    if place in role.get("access", []):
        return True
    vals = flat(state)
    return any(c["place"] == place and _holds(c["when"], vals) for c in role.get("conditionalAccess", []))


def action_id(affordance: str) -> str:
    """The ID of a situational action in the snapshot: `act_` plus the Affordance ID without `aff.` (B-3); the frontend
    sends it back unchanged.

    スナップショットの状況アクションの ID：`act_` に Affordance ID から `aff.` を除いた部分を付けたもの（B-3）。
    フロントエンドはそのまま送り返す。
    """
    return "act_" + affordance.removeprefix("aff.")


def item_ready(book: Book, state: SimState, item: str | None) -> bool:
    """The item a situational action needs is available right now (the same test as narrator R7): a non-portable one is
    at this place, a portable one is in the player's hands.

    状況アクションに要る物がいま手に入る（ナレーターの R7 と同じ判定）：持ち運べない物はこの場所にあり、
    持ち運べる物はプレイヤーが持っている。
    """
    it = next((x for x in book.world.get("items", []) if x["id"] == item), None)
    if it is None:
        return True
    if it.get("portable"):
        return bool(state["holdings"].get(it["id"]) == "player")
    return state["vars"]["var.player.location"] in it.get("at", [])


def open_affordances(book: Book, state: SimState) -> list[Json]:
    """Situational actions that hold right now (B-3 item 1): at the player's place, in this act, for this role, `when`
    holds, the target character is here and not absent, and the needed item is available.

    いま成り立つ状況アクション（B-3 第 1 項）：プレイヤーのいる場所、この幕、この役柄で、when が成り立ち、
    対象の登場人物がここにいて absent でなく、要る物が手に入るもの。
    """
    vars_ = state["vars"]
    place, act, values = vars_["var.player.location"], book.act_of(vars_), flat(state)
    out = []
    for a in book.world.get("affordances", []):
        if a["place"] != place or a.get("act", act) != act:
            continue
        if a.get("roles") and state["role"] not in a["roles"]:
            continue
        if a.get("when") and not book.sim.holds(a["when"], values):
            continue
        who = a.get("target")
        if who is not None and (state["locations"].get(who) != place or activity(book.world, state, who) == "absent"):
            continue
        if not item_ready(book, state, a.get("item")):
            continue
        out.append(a)
    return out


def affordance_minutes(book: Book, a: Json) -> int:
    return int(a.get("minutes", book.world["pacing"]["situationalMinMinutes"]))


def situational(book: Book, state: SimState, a: Json) -> Json:
    """The snapshot's SituationalAction. For ones with melos, compute from this game's current state how many minutes
    Melos would lose and whether he would still make it (W-1 arrival_delta).

    スナップショットの SituationalAction。melos があるものは、このゲームの現在の状態から、メロスが何分遅れるか、
    まだ間に合うかを計算する（W-1 arrival_delta）。
    """
    out: Json = {"actionId": action_id(a["id"]), "kind": a["kind"]}
    if a.get("target"):
        out["target"] = a["target"]
    out |= {
        "label": a["label"],
        "estimatedMinutes": affordance_minutes(book, a),
        "melos": a.get("melos"),
        "melosMinutes": None,
        "melosInTime": None,
        "enabled": True,
    }
    if a.get("melos"):
        effects = [e for e in a.get("effects", []) if e.get("op") not in ("promise", "improv")]
        try:
            d = arrival_delta(book.world, state, effects, state["t"])
            out["melosMinutes"], out["melosInTime"] = int(d["minutes"]), bool(d["inTime"])
        # Can't be combined with the changes already registered: use the minutes written in the world model, and
        # whether he makes it follows the current forecast.
        # 登録済みの変更と合わせられない：世界モデルに書かれた分数を使い、間に合うかは現在の予測に従う。
        except ValueError:
            out["melosMinutes"] = int(a.get("melosMinutes", 0))
            out["melosInTime"] = True
    return out


def player_spot(book: Book, state: SimState, run: Run | None) -> str:
    """The spot the player stands on: the one recorded on the run (when it belongs to the player's current place),
    otherwise the place's starting spot (contract 3.1, B-3 item 1).

    プレイヤーの立ち位置：ゲームに記録したもの（プレイヤーの現在の場所に属するとき）、なければこの場所の起点
    （契約 3.1、B-3 第 1 項）。
    """
    place: str = state["vars"]["var.player.location"]
    scene = book.scenes.get(book.scene_of(place, book.act_of(state["vars"])))
    if scene is None:
        return place.removeprefix("place.")
    if run is not None and run.player_spot and scene.spots.get(run.player_spot) == place:
        return run.player_spot
    return scene.player_spot(place)


def pending(run: Run | None, confirm: Json | None = None, *, safety_pause: bool = False) -> Json:
    """welcome.pending (section 4). confirm: an unanswered intent confirmation (B-4, with remainingSec), which the
    gateway looks up from the draft; safety_pause: the out-of-story card is open (B-12, `playthroughs.safety.paused`).

    welcome.pending（第 4 節）。confirm：まだ答えていない意図の確認（B-4、remainingSec 付き）で、ゲートウェイが
    下書きから引いて渡す。safety_pause：物語の外に出るカードが開いている（B-12、`playthroughs.safety.paused`）。
    """
    out: Json = dict(PENDING)
    out["confirm"] = confirm
    out["safetyPause"] = safety_pause
    if run is not None:
        out["actEnd"] = run.act_end
        if run.arrival and run.arrival.get("opener"):
            out["arrival"] = {k: run.arrival[k] for k in ("line", "opener")}
    return out


def snapshot(
    book: Book, pid: str, role_id: str, status: str, state: SimState, last_seq: int, run: Run | None = None
) -> Json:
    """The snapshot of 2.3. state is the SimState at last_seq; run holds the spot and pending items recorded on the run
    (none given = the starting spot and nothing pending).

    2.3 のスナップショット。state は last_seq 時点の SimState。run はゲームに記録した立ち位置と保留中のもの
    （渡さなければ起点で、保留中のものなし）。
    """
    vars_ = state["vars"]
    act = book.act_of(vars_)
    player_place: str = vars_["var.player.location"]
    scene_id = book.scene_of(player_place, act)
    scene = book.scenes.get(scene_id)
    scene_places = list(scene.places) if scene else [player_place]
    deadline_t: int = book.world["clock"]["deadline"]["t"]
    promised = knows(book.world, state, "player", PROMISE_FACT)

    present = [(c, state["locations"][c]) for c in book.characters if state["locations"].get(c) in scene_places]
    # W-1: the activity the beats give; absent = not present / W-1：ビートが与える activity、absent = その場にいない
    doing = {c: activity(book.world, state, c) for c, _ in present}
    away = {c for c, a in doing.items() if a == "absent"}
    me = player_spot(book, state, run)
    # Contract 3.1's standing rules: group characters take no spot; one whose relocate names a spot stands there (the
    # place must have that spot in the layout); everyone else takes free spots in layout order, with the player's spot
    # and named spots counted as taken.
    # 契約 3.1 の立ち位置の規則：group の登場人物は立ち位置を取らない。relocate に spot があればそこに立つ
    # （レイアウトのその場所にその立ち位置が必要）。残りはレイアウト順に空いた立ち位置に立ち、
    # プレイヤーと指定済みの立ち位置は埋まっているとみなす。
    group = {c for c, _ in present if book.characters[c].get("group")}
    named = state.get("spots", {})
    fixed = {
        c: named[c] for c, p in present if c not in group and c in named and scene and scene.spots.get(named[c]) == p
    }
    rest = [x for x in present if x[0] not in group and x[0] not in fixed]
    # Visible characters get spots first and absent ones last: the frontend doesn't draw them, so they mustn't push
    # visible characters off their spots.
    # 見える登場人物から立ち位置を割り当て、いない者は最後：フロントエンドは描かないので、
    # 見える者の立ち位置を奪わせない。
    order = [x for x in rest if x[0] not in away] + [x for x in rest if x[0] in away]
    if scene:
        spots = {**scene.character_spots(order, {me, *fixed.values()}), **fixed}
    else:
        spots = {c: p.removeprefix("place.") for c, p in order}
    characters = []
    for c, p in present:
        who: Json = {"id": c, "place": p}
        if c in group:
            who["group"] = True
        else:
            who["spot"] = spots[c]
        who["activity"] = doing[c]
        who["talkable"] = c not in away and bool(book.characters[c].get("talkable"))
        characters.append(who)
    places = []
    for p in scene_places:
        entry: Json = {"id": p, "enabled": place_open(book, role_id, p, state)}
        if not entry["enabled"]:
            entry["reason"] = CLOSED
        places.append(entry)
    interactables = []
    # 調べる (contract 2.12): those in this scene that have a spot in the layout.
    # 調べる（契約 2.12）：この場面にあり、レイアウトに立ち位置があるもの。
    for obj in book.world.get("objects", []):
        if obj["place"] in scene_places and obj.get("spot"):
            interactables.append(
                {
                    "id": obj["id"],
                    "kind": "examine",
                    "spot": obj["spot"],
                    "label": obj["label"],
                    "enabled": place_open(book, role_id, obj["place"], state),
                    "estimatedMinutes": 0,
                }
            )
    # Exits are always clickable; whether they are blocked is up to the check (S-077 ③).
    # 出口は常に押せる。止めるかどうかは判定が決める（S-077 ③）。
    for ex in scene.exits if scene else ():
        interactables.append(
            {
                "id": ex["spot"],
                "kind": "go",
                "spot": ex["spot"],
                "label": book.places[ex["place"]]["name"],
                "enabled": True,
                "estimatedMinutes": _travel(book, player_place, ex["place"]),
            }
        )

    forecast = None
    if promised:
        watch: str = book.world["clock"]["deadline"]["watchBeat"]
        eta = state["times"].get(watch)
        if eta is None:
            eta = world_state(book.world, state, pid)["schedule"].get(watch)
        if eta is not None:
            forecast = {"melosEtaT": eta, "beforeDeadline": eta <= deadline_t}
    deadline: Json = {"shown": promised}
    if promised:
        deadline["line"] = f"期限　{book.world['clock']['deadline']['label']}／{DEADLINE_TAIL}"

    return {
        "playthroughId": pid,
        "lastSeq": last_seq,
        "status": status,
        "actId": act,
        "sceneId": scene_id,
        "clock": {"t": state["t"], "tLabel": book.label(state["t"]), "deadlineT": deadline_t},
        "deadline": deadline,
        "forecast": forecast,
        "player": {
            "roleId": role_id,
            "place": player_place,
            "spot": me,
        },
        "places": places,
        "characters": characters,
        "interactables": interactables,
        "actions": [situational(book, state, a) for a in open_affordances(book, state)],
        "pending": pending(run),
        "voice": dict(VOICE),
    }


def _travel(book: Book, a: str, b: str) -> int:
    for adj in book.places.get(a, {}).get("adjacent", []):
        if adj["place"] == b:
            return int(adj.get("travelMinutes", 0))
    return 0


# —— patch ——


def _by_id(xs: Sequence[Json], key: str) -> dict[str, Json]:
    return {x[key]: x for x in xs}


def _add_remove(before: Sequence[Json], after: Sequence[Json], key: str) -> Json | None:
    a, b = _by_id(before, key), _by_id(after, key)
    add = [x for k, x in b.items() if a.get(k) != x]
    remove = [k for k in a if k not in b]
    out: Json = {}
    if add:
        out["add"] = add
    if remove:
        out["remove"] = remove
    return out or None


def patch(before: Json, after: Json) -> Json:
    """commit.patch: the delta of the snapshot fields, merged by id (3.4). clock is always included.

    commit.patch：スナップショットのフィールドの差分で、id ごとにまとめる（3.4）。clock は毎回含める。
    """
    out: Json = {"clock": {"t": after["clock"]["t"], "tLabel": after["clock"]["tLabel"]}}
    for k in ("deadline", "forecast"):
        if before[k] != after[k]:
            out[k] = after[k]
    a, b = _by_id(before["characters"], "id"), _by_id(after["characters"], "id")
    chars: list[Json] = []
    for cid, now in b.items():
        was = a.get(cid)
        if was is None:
            chars.append(now)
        elif was != now:
            chars.append({"id": cid, **{k: v for k, v in now.items() if was.get(k) != v}})
    for cid in a:
        if cid not in b:
            chars.append({"id": cid, "place": after["_locations"][cid]})
    if chars:
        out["characters"] = chars
    pa, pb = _by_id(before["places"], "id"), _by_id(after["places"], "id")
    places = [x for k, x in pb.items() if pa.get(k) != x]
    if places:
        out["places"] = places
    player = {k: v for k, v in after["player"].items() if k != "roleId" and before["player"].get(k) != v}
    if player:
        out["player"] = player
    for k, key in (("actions", "actionId"), ("interactables", "id")):
        d = _add_remove(before[k], after[k], key)
        if d:
            out[k] = d
    return out


def with_locations(snap: Json, state: SimState) -> Json:
    """patch needs to know where characters who left went; the snapshot leaves out those not present, so they hang on
    `_locations` separately (never sent out).

    patch は退場した登場人物の行き先を知る必要がある。スナップショットにはいない者を載せないので、
    別に `_locations` に付ける（外には送らない）。
    """
    return {**snap, "_locations": dict(state["locations"])}
