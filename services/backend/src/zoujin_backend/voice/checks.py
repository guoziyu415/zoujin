"""Automatic checks and take selection (B-6 card "automatic checks", backend-design 3.6).

Three takes per line (six for aizuchi), each checked:
1. Length: reject takes whose voiced length is more than twice or under half the median of the takes; then compare with
   the mora-based length (0.08–0.25 seconds per mora) and reject those outside it. The median uses only the takes
   whose length is within the mora range (so two bad takes don't skew it).
2. Truncation: reject takes still voiced in the last 0.1 seconds of the raw take.
3. Misreading, reading twice: character error rate of the transcript against the original text; reject over 20%;
   reject when the original text appears twice in the transcript.
4. Aizuchi have three more rules (UX measurement 20261011-121014): reject a voiced span (`audio.level`, the UX method)
   over 0.5 seconds, a trimmed file over 0.6 seconds (before AAC frame padding; aizuchi keep only 0.1 seconds in total
   at both ends), and fewer than 40% pitched windows (whisper, breathy). If none pass, run again; don't loosen.
5. Kept but flagged for UX: an aizuchi failing only on character error rate (「うむ」 heard as 「うん」), an aizuchi
   whose raw take is voiced from the very start (the onset may be cut).
6. A character's "unheard" and "wait" lines against the same character's free talk (B-6 card, UX measurement): takes
   within ±2 semitones of median pitch and ±25% speech rate are preferred; if no passing take is within range, the
   closest is picked and flagged for zg to listen to, without another run.
Among passing takes, first prefer ones with nothing flagged, then ones like free talk, then the one whose voiced length
is closest to the median; if none pass, the line stays out of the voice manifest and the audit sheet states why.

自動検査とテイクの選択（B-6 カード「自動検査」、backend-design 3.6）。

1 句につき 3 テイク（相槌は 6 テイク）を、1 つずつ検査する：
1. 長さ：有声の長さが各テイクの中央値の 2 倍以上、または半分未満のものは不採用。さらにモーラ数から見積もった長さ
   （1 モーラ 0.08〜0.25 秒）と比べ、外れるものは不採用。中央値は長さがモーラ数の範囲内にあるテイクだけで取る
   （2 テイクが壊れていても、壊れたものが中央値を引きずらないように）。
2. 途切れ：元のテイクの最後の 0.1 秒にまだ音があるものは不採用。
3. 読み誤り、二度読み：文字起こしと原文の文字誤り率が 20% を超えるものは不採用。文字起こしに原文が 2 回出てくる
   ものも採用しない。
4. 相槌にはさらに 3 条件（UX 計測 20261011-121014）：有声範囲（`audio.level`、UX の測り方）が 0.5 秒を超えるもの、
   トリム後のファイルが 0.6 秒を超えるもの（AAC のフレームを補う前。相槌は両端合わせて 0.1 秒しか残さない）、
   ピッチのある窓が 4 割未満のもの（ささやき声、息まじり）は不採用。どれも合格しなければもう一度実行し、基準は緩めない。
5. 捨てずに UX 向けに印を付けるもの：文字誤り率だけで不合格の相槌（「うむ」が「うん」と聞き取られる）、元のテイクが
   冒頭から有声の相槌（頭が切れているかもしれない）。
6. 人物の「聞き返し」「待って」は同じ人物の自由会話と比べる（B-6 カード、UX 計測）：ピッチ中央値の差 ±2 半音、
   話速の差 ±25% 以内のものを優先する。合格したテイクがどれも範囲外なら最も近いものを選び、印を付けて zg が聞けるよう
   にし、再実行はしない。
合格したものの中から、まず印のないもの、次に自由会話に近いもの、次に有声の長さが中央値に最も近いものを選ぶ。どれも
不合格なら、その句は音声マニフェストに入れず、監査シートに理由を書く。
"""

from __future__ import annotations

import math
import statistics
import unicodedata
from dataclasses import dataclass, field

from zoujin_backend.voice.audio import Shape, aizuchi_pads, head_voiced, released_seconds

MAX_CER = 0.2
SEC_PER_MORA = (0.08, 0.25)
# The mora-based length gets extra allowance for pauses inside the line: there is a short pause after 「、」「。」「！」
# and at 「……」; only the upper bound is loosened
# モーラ数から見積もった長さには文中の間の余裕を足す：「、」「。」「！」の後と「……」では少し間が空くので、上限だけ緩める
PAUSE_ALLOWANCE_S = 0.35
AIZUCHI_MAX_S = 0.5  # Voiced span (ux-design 16.2 item 4) / 有声範囲（ux-design 16.2 の 4 つ目）
AIZUCHI_FILE_MAX_S = 0.6  # The whole trimmed file / トリム後のファイル全体
# Measured by UX: passing aizuchi 0.56–0.84, the breathy 「ああ。」 0.07, the whispered 「ああ、ああ。」 0.04
# UX の計測値：合格した相槌 0.56〜0.84、息まじりの「ああ。」0.07、ささやき声の「ああ、ああ。」0.04
AIZUCHI_MIN_PITCHED = 0.4
# For short lines of two or three morae (「うむ。」「へえ。」) the mora-based upper bound is only about 0.5 seconds, too
# tight: give the upper bound at least 0.8 seconds (aizuchi are also governed by the 0.5-second rule)
# 2〜3 モーラの短い句（「うむ。」「へえ。」）はモーラ数による上限が 0.5 秒前後しかなく厳しすぎる：上限は最低 0.8 秒
# にする（相槌には別に 0.5 秒の条件がある）
MIN_UPPER_S = 0.8
TALK_MAX_ST = 2.0  # Median pitch difference from free talk (semitones) / 自由会話とのピッチ中央値の差（半音）
TALK_MAX_RATE = 0.25  # Speech rate difference (ratio) / 話速の差（比率）

_PUNCT = set(" 　、。，．,.!?！？「」『』（）()・…ー〜~")
# Merge with the preceding kana into one mora (っ, ん, ー each count as one mora)
# 前の仮名と合わせて 1 モーラ（っ、ん、ー はそれぞれ 1 モーラ）
_SMALL = set("ゃゅょぁぃぅぇぉゎャュョァィゥェォヮ")
_PAUSES = ("、", "。", "！", "？", "……")
# No reading table for kanji: each counts as 2 morae (on'yomi are mostly 1–2 morae) [estimate]
# 漢字の読みの表はないので 1 字 2 モーラと見積もる（音読みはたいてい 1〜2 モーラ）〔推定〕
KANJI_MORA = 2


def mora(text: str) -> float:
    """Mora count (estimate): one per kana, small kana of yōon not counted separately, 2 per kanji, punctuation not
    counted.

    モーラ数（推定）：仮名 1 字 1 モーラ、拗音の小書き文字は数えない、漢字 1 字 2 モーラ、句読点は数えない。
    """
    n = 0.0
    for ch in text:
        if ch in _PUNCT and ch != "ー" or ch in _SMALL:
            continue
        name = unicodedata.name(ch, "")
        if "CJK UNIFIED IDEOGRAPH" in name:
            n += KANJI_MORA
        else:
            n += 1
    return n


def pauses(text: str) -> int:
    t = text.rstrip("。！？")  # No pause after sentence-final punctuation / 文末の句読点の後は間を取らない
    return sum(t.count(p) for p in _PAUSES)


def expected_range(text: str) -> tuple[float, float]:
    m = mora(text)
    return (m * SEC_PER_MORA[0], max(MIN_UPPER_S, m * SEC_PER_MORA[1] + pauses(text) * PAUSE_ALLOWANCE_S))


_VOWEL_ROWS = {
    "あ": "あかさたなはまやらわがざだばぱぁゃゎ",
    "い": "いきしちにひみりぎじぢびぴぃ",
    "う": "うくすつぬふむゆるぐずづぶぷぅゅっ",
    "え": "えけせてねへめれげぜでべぺぇ",
    "お": "おこそとのほもよろをごぞどぼぽぉょ",
}
_VOWEL = {ch: v for v, row in _VOWEL_ROWS.items() for ch in row}


def _norm(text: str) -> str:
    """Drop punctuation and spaces, turn katakana into hiragana, unify full- and half-width, replace 「ー」 with the
    preceding kana's vowel (あー→ああ, へー→へえ): a transcript spelled differently doesn't count as a misreading.

    句読点と空白を除き、カタカナをひらがなに、全角・半角をそろえ、「ー」を前の仮名の母音に置き換える（あー→ああ、
    へー→へえ）：文字起こしの書き方が違うだけなら読み誤りとしない。
    """
    out: list[str] = []
    for ch in unicodedata.normalize("NFKC", text):
        code = ord(ch)
        if 0x30A1 <= code <= 0x30F6:
            ch = chr(code - 0x60)
        if ch == "ー":
            if out and out[-1] in _VOWEL:
                out.append(_VOWEL[out[-1]])
            continue
        if ch in _PUNCT:
            continue
        out.append(ch)
    return "".join(out)


def cer(reference: str, hypothesis: str) -> float:
    ref, hyp = _norm(reference), _norm(hypothesis)
    if not ref:
        return 0.0 if not hyp else 1.0
    prev = list(range(len(hyp) + 1))
    for i, rc in enumerate(ref, 1):
        cur = [i] + [0] * len(hyp)
        for j, hc in enumerate(hyp, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (rc != hc))
        prev = cur
    return round(prev[-1] / len(ref), 3)


def read_twice(reference: str, hypothesis: str) -> bool:
    ref = _norm(reference)
    return bool(ref) and _norm(hypothesis).count(ref) >= 2


@dataclass
class TakeCheck:
    take: int
    # Voiced length (seconds); None = this take wasn't recorded (error)
    # 有声の長さ（秒）。None = このテイクは録れていない（エラー）
    speech: float | None = None
    transcript: str | None = None
    cer: float | None = None
    problems: list[str] = field(default_factory=list)
    # Kept but flagged for UX (aizuchi failing only on CER, voiced from the start)
    # 捨てずに UX 向けに印を付けるもの（文字誤り率だけで不合格の相槌、冒頭から有声）
    soft: list[str] = field(default_factory=list)
    # Pitch and speech rate against free talk (only for lines that are compared)
    # 自由会話と比べたピッチと話速（比べる句だけ）
    talk: str | None = None
    # How far outside the range: each of the two divided by its allowed difference, the larger one; ≤ 1 is in range
    # 範囲からどれだけ外れているか：2 つをそれぞれ許容差で割って大きいほう。1 以下なら範囲内
    talk_off: float = 0.0
    # CER passes only thanks to the source file's heardAs spelling (fails against both the original and the reading
    # substitution)
    # 文字誤り率が元ファイルの heardAs の書き方でしか合格しない（原文にも読み替え後にも合格しない）
    heard_as: bool = False
    # Aizuchi in the source file's breathyOk: how far the pitched ratio is below the minimum (to pick the least breathy
    # take); 0 for everything else
    # 元ファイルの breathyOk の相槌：ピッチのある割合が下限からどれだけ足りないか（いちばん息まじりでない
    # テイクを選ぶ）。それ以外はすべて 0
    breathy: float = 0.0

    @property
    def ok(self) -> bool:
        return self.speech is not None and not self.problems


@dataclass
class Verdict:
    takes: list[TakeCheck]
    median: float | None
    expected: tuple[float, float]
    chosen: int | None  # The chosen take; None = none passed / 選んだテイク。None = どれも不合格
    flags: list[str] = field(default_factory=list)  # Flagged for UX (kept) / UX 向けの印（捨てない）


def judge(
    text: str,
    takes: dict[int, tuple[Shape, str | None] | str],
    *,
    aizuchi: bool,
    spoken: str | None = None,
    talk: tuple[float, float] | None = None,
    heard_as: tuple[str, ...] = (),
    breathy_ok: bool = False,
) -> Verdict:
    """takes: take number → (shape, transcript) or the reason it failed. The transcript is compared with both the
    original `text` and the `spoken` sent to Live (after reading substitutions), taking the smaller; morae are estimated
    from `spoken` (the substituted kana are more accurate).

    takes：テイク番号 → （形、文字起こし）または失敗の理由。文字起こしは原文 `text` とも Live に送った `spoken`
    （読み替え後）とも比べて小さいほうを取る。モーラ数は `spoken` で見積もる（置き換え後の仮名のほうが正確）。
    """
    lo, hi = expected_range(spoken or text)
    checks: list[TakeCheck] = []
    speeches = [v[0].speech for v in takes.values() if not isinstance(v, str)]
    # The median uses only takes whose length is within the mora range: when two of three takes are bad (one too long,
    # one read twice), the median of all three is itself skewed and would throw away the only good take as "under
    # half". Use all takes only when none is in range
    # 中央値は長さがモーラ数の範囲内にあるテイクだけで取る：3 テイク中 2 つが壊れている（1 つは長すぎ、1 つは
    # 二度読み）と、3 つの中央値そのものが偏り、唯一の良いテイクを「半分未満」として捨ててしまう。範囲内のものが
    # 1 つもないときだけ全部を使う
    plausible = [x for x in speeches if lo <= x <= hi]
    median = statistics.median(plausible or speeches) if speeches else None
    for n in sorted(takes):
        v = takes[n]
        if isinstance(v, str):
            checks.append(TakeCheck(n, problems=[v]))
            continue
        s, heard = v
        c = TakeCheck(n, speech=round(s.speech, 3), transcript=heard)
        if s.speech <= 0:
            c.problems.append("No audio / 音声がない")
        else:
            if median is not None and len(plausible or speeches) >= 2:
                if s.speech > 2 * median:
                    c.problems.append(
                        f"More than twice the median {median:.2f}s (read twice?) / "
                        f"中央値 {median:.2f}s の 2 倍以上（二度読み？）"
                    )
                elif s.speech < 0.5 * median:
                    c.problems.append(
                        f"Under half the median {median:.2f}s (truncated?) / "
                        f"中央値 {median:.2f}s の半分未満（途切れ？）"
                    )
            if s.speech < lo:
                c.problems.append(
                    f"Shorter than the mora-based lower bound {lo:.2f}s / モーラ数から見積もった下限 {lo:.2f}s より短い"
                )
            elif s.speech > hi:
                c.problems.append(
                    f"Longer than the mora-based upper bound {hi:.2f}s / モーラ数から見積もった上限 {hi:.2f}s より長い"
                )
            if aizuchi:
                _aizuchi(s, c, breathy_ok)
            if talk is not None:
                _talk(s, c, talk, mora(spoken or text))
        if s.tail_voiced:
            c.problems.append("Still voiced in the last 0.1 s (truncated) / 最後の 0.1 秒にまだ音がある（途切れ）")
        if heard is None:
            c.problems.append("No transcript / 文字起こしがない")
        else:
            # The transcript may be written in kanji or in kana / 文字起こしは漢字で書くことも仮名で書くこともある
            refs = [text] if not spoken or spoken == text else [text, spoken]
            plain = min(cer(r, heard) for r in refs)
            # Source file heardAs: a transcript that is always wrong in the same way (「ちと」 written
            # 「ちょっと」), for this line only
            # 元ファイルの heardAs：文字起こしがいつも同じように間違える（「ちと」を「ちょっと」と書く）もの。
            # この句だけに効く
            refs += heard_as
            c.cer = min(cer(r, heard) for r in refs)
            c.heard_as = plain > MAX_CER >= c.cer
            if any(read_twice(r, heard) for r in refs):
                c.problems.append(
                    "The original text appears twice in the transcript (read twice) / "
                    "文字起こしに原文が 2 回出てくる（二度読み）"
                )
            elif c.cer > MAX_CER:
                why = (
                    f"Transcript 「{heard}」: CER {c.cer:.0%} over {MAX_CER:.0%} / "
                    f"文字起こし「{heard}」：文字誤り率 {c.cer:.0%} が {MAX_CER:.0%} を超える"
                )
                # For aizuchi (「うむ」 heard as 「うん」) it's mostly the transcript's fault, not a misreading:
                # when failing only on CER, keep it and flag it for UX (UX #82)
                # 相槌（「うむ」が「うん」と聞き取られる）はたいてい文字起こしの問題で、読み誤りではない：
                # 文字誤り率だけで不合格なら捨てずに UX 向けに印を付ける（UX #82）
                (c.soft if aizuchi else c.problems).append(why)
        checks.append(c)
    passed = [c for c in checks if c.ok]
    chosen = None
    if passed and median is not None:
        # Prefer no soft problems; next, within the free-talk range, or the closest if none is; next, length closest
        # to the median
        # ソフトな問題がないものを優先。次に自由会話の範囲内のもの（なければ最も近いもの）。その次に長さが中央値に最も
        # 近いもの
        chosen = min(
            passed,
            key=lambda c: (bool(c.soft), c.breathy, max(1.0, c.talk_off), abs((c.speech or 0) - median), c.take),
        ).take
    flags = []
    if chosen is not None:
        pick = next(c for c in checks if c.take == chosen)
        flags = [f"Aizuchi / 相槌: {why} — kept, please listen / 捨てずに残す、聞いて確認を" for why in pick.soft]
        if pick.heard_as:
            flags.append(
                f"Transcript 「{pick.transcript}」 passes only with the heardAs spelling; please listen to check "
                f"it reads the original / 文字起こし「{pick.transcript}」は heardAs の書き方でしか合格しない。"
                "原文どおりに読んでいるか聞いて確認を"
            )
        if pick.talk_off > 1:
            flags.append(
                f"Against free talk / 自由会話との比較: {pick.talk} — no passing take is within range, picked the "
                "closest, please listen / 合格したテイクがどれも範囲外なので最も近いものを選んだ。聞いて確認を"
            )
    return Verdict(checks, median, (round(lo, 2), round(hi, 2)), chosen, flags)


def _talk(s: Shape, c: TakeCheck, talk: tuple[float, float], moras: float) -> None:
    hz, rate = talk
    en: list[str] = []
    ja: list[str] = []
    off = 0.0
    if s.pitch_hz:
        st = 12 * math.log2(s.pitch_hz / hz)
        en.append(f"pitch {s.pitch_hz:.0f} Hz ({st:+.1f} semitones)")
        ja.append(f"ピッチ {s.pitch_hz:.0f} Hz（{st:+.1f} 半音）")
        off = max(off, abs(st) / TALK_MAX_ST)
    else:
        en.append("pitch not measured")
        ja.append("ピッチを測れなかった")
        off = max(off, 2.0)
    if s.sounding:
        r = moras / s.sounding
        dev = r / rate - 1
        en.append(f"speech rate {r:.1f} morae/s ({dev:+.0%})")
        ja.append(f"話速 {r:.1f} モーラ/秒（{dev:+.0%}）")
        off = max(off, abs(dev) / TALK_MAX_RATE)
    c.talk, c.talk_off = f"{', '.join(en)} / {'、'.join(ja)}", round(off, 3)


def _aizuchi(s: Shape, c: TakeCheck, breathy_ok: bool = False) -> None:
    span = s.span if s.span is not None else s.speech
    if span > AIZUCHI_MAX_S:
        c.problems.append(
            f"Aizuchi voiced for {span:.2f}s, over {AIZUCHI_MAX_S}s / "
            f"相槌の有声 {span:.2f}s が {AIZUCHI_MAX_S}s を超える"
        )
    file_s = released_seconds(s, aizuchi_pads(s))
    if file_s > AIZUCHI_FILE_MAX_S:
        c.problems.append(
            f"Aizuchi is {file_s:.2f}s after trimming, over {AIZUCHI_FILE_MAX_S}s / "
            f"相槌はトリム後 {file_s:.2f}s で {AIZUCHI_FILE_MAX_S}s を超える"
        )
    if s.pitched is not None and s.pitched < AIZUCHI_MIN_PITCHED:
        why = (
            f"Only {s.pitched:.0%} pitched (whisper or breathy?) / "
            f"ピッチのある部分が {s.pitched:.0%} しかない（ささやき声か息まじり？）"
        )
        # Source file breathyOk: keep it, pick the least breathy take and flag it for UX
        # 元ファイルの breathyOk：捨てずに、いちばん息まじりでないテイクを選んで UX 向けに印を付ける
        if breathy_ok:
            c.soft.append(why)
            c.breathy = round(AIZUCHI_MIN_PITCHED - s.pitched, 3)
        else:
            c.problems.append(why)
    if head_voiced(s):
        c.soft.append(
            "The raw take is voiced from the very start (the onset may be cut; enough silence was padded in front) / "
            "元のテイクが冒頭から有声（頭が切れているかもしれない。前に十分な無音を補った）"
        )
