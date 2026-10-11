"""自动检查和挑选（B-6 卡「自动检查」，backend-design 3.6）。

每句三遍（相槌六遍），逐遍查：
1. 长度：有声长度比几遍的中位数长一倍以上或不到一半的不要；再和拍数估的长度比（每拍 0.08〜0.25 秒），超出的不要。
   中位数只取长度在拍数范围里的几遍（两遍坏了时不让坏的拉偏中位数）。
2. 截断：原始那一遍最后 0.1 秒还有声音的不要。
3. 读错、读两遍：补转写和原文按字算错误率，超过 20% 的不要；补转写里原文出现两遍的不要。
4. 相槌另有三条（UX 量测 20261011-121014）：有声范围（`audio.level`，UX 的量法）超过 0.5 秒的不要，裁好的文件超过
   0.6 秒的不要（补 AAC 帧之前；相槌两头合计只留 0.1 秒），有音高的窗不到四成的（耳语、气声）不要。都不过就再跑
   一次，不放宽。
5. 不扔、标给 UX 的：相槌只在字错率上不过（「うむ」听成「うん」），相槌原始那遍一开头就有声（可能切了头）。
6. 人物的「听不清」「等一下」和同一人物的自由对话比（B-6 卡、UX 量测）：音高中位差 ±2 半音、语速差 ±25% 以内的优先；
   过了的几遍都不在范围里就挑最近的一遍，标出来留给 zg 听，不再跑。
过了的里面先挑没有要标的，再挑像自由对话的，再挑有声长度最接近中位数的一遍；都不过，这句不进声音清单，审查单
写明原因。
"""

from __future__ import annotations

import math
import statistics
import unicodedata
from dataclasses import dataclass, field

from zoujin_backend.voice.audio import Shape, aizuchi_pads, head_voiced, released_seconds

MAX_CER = 0.2
SEC_PER_MORA = (0.08, 0.25)
# 拍数估的长度另给句中停顿的余量：「、」「。」「！」后面和「……」都会停一下，只放宽上限
PAUSE_ALLOWANCE_S = 0.35
AIZUCHI_MAX_S = 0.5  # 有声范围（ux-design 16.2 第 4 样）
AIZUCHI_FILE_MAX_S = 0.6  # 裁好的整个文件
AIZUCHI_MIN_PITCHED = 0.4  # UX 量过的：过的相槌 0.56〜0.84，气声的「ああ。」0.07，耳语的「ああ、ああ。」0.04
# 两三拍的短句（「うむ。」「へえ。」）上限按拍数只有 0.5 秒上下，太紧：上限至少给到 0.8 秒（相槌另有 0.5 秒那条管着）
MIN_UPPER_S = 0.8
TALK_MAX_ST = 2.0  # 和自由对话的音高中位差（半音）
TALK_MAX_RATE = 0.25  # 语速差（比例）

_PUNCT = set(" 　、。，．,.!?！？「」『』（）()・…ー〜~")
_SMALL = set("ゃゅょぁぃぅぇぉゎャュョァィゥェォヮ")  # 和前一个假名合成一拍（っ、ん、ー各算一拍）
_PAUSES = ("、", "。", "！", "？", "……")
KANJI_MORA = 2  # 汉字没有读音表，一个字按 2 拍估（音读多是 1〜2 拍）〔估〕


def mora(text: str) -> float:
    """拍数（估）：假名一个一拍、拗音的小字不另算、汉字一个按 2 拍、标点不算。"""
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
    t = text.rstrip("。！？")  # 句末的标点后面不停
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
    """去掉标点和空格，片假名换平假名，全角半角统一，「ー」换成前一个假名的元音（あー→ああ、へー→へえ）：
    补转写的写法不一样时不算读错。"""
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
    speech: float | None = None  # 有声长度（秒）；None = 这遍没录到（出错）
    transcript: str | None = None
    cer: float | None = None
    problems: list[str] = field(default_factory=list)
    soft: list[str] = field(default_factory=list)  # 不扔、标给 UX 的（相槌只在字错率上不过、开头就有声）
    talk: str | None = None  # 和自由对话比的音高、语速（要比的句子才有）
    talk_off: float = 0.0  # 离范围多远：两样各除以允许的差取大的，≤ 1 在范围里
    heard_as: bool = False  # 字错率只靠源文件 heardAs 的写法才过（对原文和读音替换后的都不过）

    @property
    def ok(self) -> bool:
        return self.speech is not None and not self.problems


@dataclass
class Verdict:
    takes: list[TakeCheck]
    median: float | None
    expected: tuple[float, float]
    chosen: int | None  # 选中的第几遍；None = 都不过
    flags: list[str] = field(default_factory=list)  # 标给 UX 的（不扔）


def judge(
    text: str,
    takes: dict[int, tuple[Shape, str | None] | str],
    *,
    aizuchi: bool,
    spoken: str | None = None,
    talk: tuple[float, float] | None = None,
    heard_as: tuple[str, ...] = (),
) -> Verdict:
    """takes：第几遍 → (形状, 补转写) 或出错的原因。补转写对原文 `text` 和送给 Live 的 `spoken`（读音替换后）都比，
    取小的；拍数按 `spoken` 估（替换后的假名更准）。"""
    lo, hi = expected_range(spoken or text)
    checks: list[TakeCheck] = []
    speeches = [v[0].speech for v in takes.values() if not isinstance(v, str)]
    # 中位数只取长度在拍数范围里的几遍：三遍里两遍坏了（一遍太长、一遍读两遍）时，三遍的中位数本身就偏了，会把唯一
    # 好的那遍当成「不到一半」扔掉。范围里一遍都没有才用全部的
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
            c.problems.append("没有声音")
        else:
            if median is not None and len(plausible or speeches) >= 2:
                if s.speech > 2 * median:
                    c.problems.append(f"比中位数 {median:.2f}s 长一倍以上（读两遍？）")
                elif s.speech < 0.5 * median:
                    c.problems.append(f"不到中位数 {median:.2f}s 的一半（截断？）")
            if s.speech < lo:
                c.problems.append(f"比拍数估的下限 {lo:.2f}s 短")
            elif s.speech > hi:
                c.problems.append(f"比拍数估的上限 {hi:.2f}s 长")
            if aizuchi:
                _aizuchi(s, c)
            if talk is not None:
                _talk(s, c, talk, mora(spoken or text))
        if s.tail_voiced:
            c.problems.append("最后 0.1 秒还有声音（截断）")
        if heard is None:
            c.problems.append("没有补转写")
        else:
            refs = [text] if not spoken or spoken == text else [text, spoken]  # 补转写可能写汉字也可能写假名
            plain = min(cer(r, heard) for r in refs)
            refs += heard_as  # 源文件 heardAs：补转写固定写错的（「ちと」写成「ちょっと」），只对这一句
            c.cer = min(cer(r, heard) for r in refs)
            c.heard_as = plain > MAX_CER >= c.cer
            if any(read_twice(r, heard) for r in refs):
                c.problems.append("补转写里原文出现两遍（读两遍）")
            elif c.cer > MAX_CER:
                why = f"字错率 {c.cer:.0%} 超过 {MAX_CER:.0%}"
                # 相槌（「うむ」听成「うん」）多半是补转写的毛病，不是读错：只在字错率上不过时不扔，标给 UX（UX #82）
                (c.soft if aizuchi else c.problems).append(f"的补转写「{heard}」{why}")
        checks.append(c)
    passed = [c for c in checks if c.ok]
    chosen = None
    if passed and median is not None:
        # 没有软问题的优先；其次在自由对话的范围里的，都不在就挑最近的；再其次长度最接近中位数
        chosen = min(
            passed,
            key=lambda c: (bool(c.soft), max(1.0, c.talk_off), abs((c.speech or 0) - median), c.take),
        ).take
    flags = []
    if chosen is not None:
        pick = next(c for c in checks if c.take == chosen)
        flags = [f"相槌{why}，不扔，请听一下" for why in pick.soft]
        if pick.heard_as:
            flags.append(f"补转写「{pick.transcript}」只对上 heardAs 的写法才过，请听一下读的是不是原文")
        if pick.talk_off > 1:
            flags.append(f"和自由对话比 {pick.talk}，过了的几遍都不在范围里，挑了最近的一遍，请听一下")
    return Verdict(checks, median, (round(lo, 2), round(hi, 2)), chosen, flags)


def _talk(s: Shape, c: TakeCheck, talk: tuple[float, float], moras: float) -> None:
    hz, rate = talk
    parts, off = [], 0.0
    if s.pitch_hz:
        st = 12 * math.log2(s.pitch_hz / hz)
        parts.append(f"音高 {s.pitch_hz:.0f} Hz（{st:+.1f} 半音）")
        off = max(off, abs(st) / TALK_MAX_ST)
    else:
        parts.append("没量到音高")
        off = max(off, 2.0)
    if s.sounding:
        r = moras / s.sounding
        dev = r / rate - 1
        parts.append(f"语速 {r:.1f} 拍/秒（{dev:+.0%}）")
        off = max(off, abs(dev) / TALK_MAX_RATE)
    c.talk, c.talk_off = "，".join(parts), round(off, 3)


def _aizuchi(s: Shape, c: TakeCheck) -> None:
    span = s.span if s.span is not None else s.speech
    if span > AIZUCHI_MAX_S:
        c.problems.append(f"相槌有声 {span:.2f}s，超过 {AIZUCHI_MAX_S}s")
    file_s = released_seconds(s, aizuchi_pads(s))
    if file_s > AIZUCHI_FILE_MAX_S:
        c.problems.append(f"相槌裁好是 {file_s:.2f}s，超过 {AIZUCHI_FILE_MAX_S}s")
    if s.pitched is not None and s.pitched < AIZUCHI_MIN_PITCHED:
        c.problems.append(f"有音高的只有 {s.pitched:.0%}（耳语或气声？）")
    if head_voiced(s):
        c.soft.append("原始那遍一开头就有声（可能切了头；已在前面补够静音）")
