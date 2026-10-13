"""PCM from read-aloud (16-bit, 24 kHz, mono, Live's downstream format): analysis, silence trimming, volume
adjustment, AAC encoding.

- The voiced range is judged by RMS over 10 ms frames: above `SILENCE_DBFS` counts as voiced. Used for truncation and
  for trimming the ends.
- Truncation: the raw take is still voiced in its last 0.1 seconds (it didn't fall to silence).
- Trimming the ends: check truncation first, then trim, keeping 80 ms on each side of the voiced range (aizuchi: 20 at
  the head, 80 at the tail; 50 each for a hard onset); where the raw take has too little at either end, pad silence.
- Loudness and aizuchi length follow the UX measurement method (`level`): 40 ms windows with a 10 ms hop; windows within
  30 dB of the loudest (and above −55 dBFS) count as voiced; loudness = the RMS of those windows. Pitch (`pitched`): the
  share of windows where YIN finds a period; whispers have none.
- Volume: for speakers with a target loudness (the source file's `loudness`, the loudness of the same character's free
  talk) the whole line is brought to the target; others are left alone. True peak is always held below −1 dBTP
  (ux-design 16.2 item 3, UX measurement).
- Encoding: AAC-LC, mono, 24 kHz, 48 kbps `.m4a` (ffmpeg on the Mac); `durationMs` is computed from the encoded file
  (ffprobe).

読み上げで得た PCM（16 ビット、24 kHz、モノラル、Live の下りの形式）：解析、無音のトリム、音量調整、AAC への
エンコード。

- 有声の範囲は 10 ミリ秒 1 フレームの RMS で判定する：`SILENCE_DBFS` より大きければ有声。途切れの判定と頭尾のトリムに
  使う。
- 途切れ：元のテイクの最後の 0.1 秒にまだ音がある（無音まで落ちていない）。
- 頭尾のトリム：先に途切れを調べてからトリムし、有声範囲の前後に 80 ミリ秒ずつ残す（相槌は頭 20、尾 80。硬い立ち上がり
  なら各 50）。元のテイクの頭尾が足りなければ無音を補う。
- ラウドネスと相槌の長さは UX の計測方法（`level`）に従う：40 ミリ秒の窓を 10 ミリ秒ずつずらし、最も大きい窓から
  30 dB 以内（かつ −55 dBFS より大きい）の窓を有声とする。ラウドネス = それらの窓の RMS。ピッチ（`pitched`）：YIN が
  周期を見つけられる窓の割合。ささやき声では見つからない。
- 音量：目標ラウドネスのある話者（元ファイルの `loudness`、同じ人物の自由会話のラウドネス）はセリフ全体を目標に合わせ、
  ない話者はそのままにする。真のピークはすべて −1 dBTP 未満に抑える（ux-design 16.2 の 3 つ目、UX 計測）。
- エンコード：AAC-LC、モノラル、24 kHz、48 kbps の `.m4a`（Mac では ffmpeg）。`durationMs` は変換後のファイルから
  求める（ffprobe）。
"""

from __future__ import annotations

import io
import math
import shutil
import statistics
import subprocess
import sys
import tempfile
import wave
from array import array
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

RATE = 24_000
FRAME = RATE // 100  # 10 ms
SILENCE_DBFS = -45.0
TAIL_S = 0.1
PAD_S = 0.08
# Aizuchi keep only 0.1 seconds in total at both ends: only then do UX's two rules "voiced ≤ 0.5 seconds, whole file
# ≤ 0.6 seconds" mean the same thing (with 80 ms at each end the file rule is tighter and voiced can only reach 0.44
# seconds; in the second real run on the Mac several of the 15 takes missed by just that). 20 ms at the head and 80 ms
# at the tail (the sound comes in early, the tail is kept for the decay); with a step at the onset (the first voiced
# frame is within 6 dB of the loudest frame, a hard onset) 50 ms at each end (UX)
# 相槌は両端合わせて 0.1 秒しか残さない：こうして初めて UX の「有声 ≤ 0.5 秒、ファイル全体 ≤ 0.6 秒」の 2 条件が同じ
# 意味になる（両端 80 ミリ秒ずつだとファイルの条件のほうが厳しく、有声は 0.44 秒までしか許されない。Mac での 2 回目の
# 本番実行では 15 テイクのうち何本もがこの差だけで落ちた）。頭 20 ミリ秒、尾 80 ミリ秒（声は早めに出し、尾は余韻を
# 残す）。立ち上がりに段差があるもの（最初の有声フレームが最も大きいフレームから 6 dB 以内、硬い立ち上がり）は頭尾
# 各 50 ミリ秒（UX）
AIZUCHI_PADS = (0.02, 0.08)
AIZUCHI_STEP_PADS = (0.05, 0.05)
ONSET_STEP_DB = 6.0
PEAK_DBFS = -1.0  # True peak ceiling (dBTP) / 真のピークの上限（dBTP）
WIN = 4  # Window for level: 4 frames = 40 ms / level の窓：4 フレーム = 40 ミリ秒
REL_GATE_DB = 30.0
FLOOR_DBFS = -55.0
MERGE_GAP_S = 0.06
# Pitch is computed at 8 kHz (pure Python, 3x faster) / ピッチは 8 kHz に落として計算する（純 Python で 3 倍速い）
PITCH_RATE = 8_000
PITCH_GATE_DB = 20.0
YIN_THRESH = 0.15
F0_RANGE = (60.0, 400.0)


def samples(pcm: bytes) -> array[int]:
    a = array("h")
    a.frombytes(pcm[: len(pcm) // 2 * 2])
    if sys.byteorder == "big":
        a.byteswap()
    return a


def to_bytes(a: array[int]) -> bytes:
    if sys.byteorder == "big":
        a = array("h", a)
        a.byteswap()
    return a.tobytes()


def dbfs(rms: float) -> float:
    return -120.0 if rms <= 0 else 20 * math.log10(rms / 32768)


def _rms(a: array[int], start: int, end: int) -> float:
    n = end - start
    if n <= 0:
        return 0.0
    return math.sqrt(sum(a[i] * a[i] for i in range(start, end)) / n)


@dataclass(frozen=True)
class Shape:
    seconds: float  # The whole clip / 全体
    # Start of the first voiced frame (seconds); = seconds when the whole clip is silent
    # 最初の有声フレームの開始（秒）。全体が無音なら = seconds
    voiced_start: float
    voiced_end: float  # End of the last voiced frame / 最後の有声フレームの終わり
    tail_voiced: bool  # Still voiced in the last 0.1 seconds: truncated / 最後の 0.1 秒にまだ音がある：途切れ
    peak_dbfs: float
    # How many dB the first voiced frame is below the loudest frame (≥ 0); None = no sound
    # 最初の有声フレームが最も大きいフレームより何 dB 低いか（≥ 0）。None = 音がない
    onset_db: float | None = None
    # Voiced span measured by level (the UX method); None = not measured, use speech
    # level で測った有声範囲（UX の方法）。None = 測っていないので speech を使う
    span: float | None = None
    loudness_dbfs: float | None = None
    # Share of pitched windows; None = not measured (only measured for lines being compared, it's slow)
    # ピッチのある窓の割合。None = 測っていない（比べる句だけ測る。遅いため）
    pitched: float | None = None
    pitch_hz: float | None = None  # Median F0 of the pitched windows / ピッチのある窓の基本周波数の中央値
    sounding: float | None = None  # Voiced time excluding pauses / 間を除いた有声時間

    @property
    def speech(self) -> float:
        """Length of the voiced range (pauses in between included). All length checks use this rather than the whole
        clip (the leading and trailing silence differs from take to take).

        有声範囲の長さ（途中の間も含む）。長さの検査はすべてこれを使い、全体の長さは使わない（頭尾の無音はテイクごとに
        違うため）。
        """
        return max(0.0, self.voiced_end - self.voiced_start)


def shape(pcm: bytes, *, pitch: bool = False) -> Shape:
    a = samples(pcm)
    n = len(a)
    frame_db = [dbfs(_rms(a, i, min(n, i + FRAME))) for i in range(0, n, FRAME)]
    voiced = [d > SILENCE_DBFS for d in frame_db]
    first = next((i for i, v in enumerate(voiced) if v), None)
    last = next((i for i in range(len(voiced) - 1, -1, -1) if voiced[i]), None)
    tail = max(0, n - int(RATE * TAIL_S))
    peak = max((abs(x) for x in a), default=0)
    lv = level(pcm)
    pt = pitch_of(pcm) if pitch else None
    return Shape(
        seconds=n / RATE,
        voiced_start=(first * FRAME / RATE) if first is not None else n / RATE,
        voiced_end=min(n, (last + 1) * FRAME) / RATE if last is not None else n / RATE,
        tail_voiced=n > 0 and dbfs(_rms(a, tail, n)) > SILENCE_DBFS,
        peak_dbfs=dbfs(peak),
        onset_db=None if first is None else round(max(frame_db) - frame_db[first], 1),
        span=lv.span,
        loudness_dbfs=lv.loudness_dbfs,
        sounding=lv.sounding,
        pitched=pt.pitched if pt else None,
        pitch_hz=pt.median_hz if pt else None,
    )


def trim(pcm: bytes, s: Shape, pads: tuple[float, float] = (PAD_S, PAD_S)) -> bytes:
    """Keep 80 ms on each side of the voiced range (for aizuchi see `aizuchi_pads`). If the raw take is voiced from
    the very start (UX measured メロス「ああ。」 at −29 dB in its first 10 ms) or is short at the end, pad enough
    silence.

    有声範囲の前後に 80 ミリ秒ずつ残す（相槌は `aizuchi_pads` を参照）。元のテイクが冒頭から有声（UX の計測では
    メロス「ああ。」の頭 10 ミリ秒が −29 dB）だったり、末尾が足りなかったりするときは、無音を十分に補う。
    """
    n = len(pcm) // 2
    start = round(s.voiced_start * RATE) - round(pads[0] * RATE)
    end = round(s.voiced_end * RATE) + round(pads[1] * RATE)
    body = pcm[max(0, start) * 2 : min(n, end) * 2]
    return bytes(2 * max(0, -start)) + body + bytes(2 * max(0, end - n))


def aizuchi_pads(s: Shape) -> tuple[float, float]:
    step = s.onset_db is not None and s.onset_db < ONSET_STEP_DB
    return AIZUCHI_STEP_PADS if step else AIZUCHI_PADS


def released_seconds(s: Shape, pads: tuple[float, float]) -> float:
    """Length after trimming and padding silence. Computed before AAC frame padding (what's padded is silence, UX).

    トリムして無音を補った後の長さ。AAC のフレームを補う前で計算する（補うのは無音、UX）。
    """
    return round(s.speech + pads[0] + pads[1], 3)


def head_voiced(s: Shape) -> bool:
    """The raw take is voiced from its first frame: the onset may have been cut.

    元のテイクが最初のフレームから有声：頭が切れているかもしれない。
    """
    return s.voiced_start < FRAME / RATE


@dataclass(frozen=True)
class Level:
    # From the first voiced window to the last (seconds), pauses in between included
    # 最初の有声の窓から最後まで（秒）。途中の間も含む
    span: float
    loudness_dbfs: float  # RMS of the voiced windows / 有声の窓の RMS
    # Voiced time excluding pauses (pauses under 60 ms are merged): for speech rate
    # 間を除いた有声時間（60 ミリ秒未満の間はつなげる）：話速に使う
    sounding: float = 0.0


def _block_energy(a: array[int]) -> list[float]:
    return [float(sum(x * x for x in a[i : i + FRAME])) for i in range(0, len(a) - FRAME + 1, FRAME)]


def level(pcm: bytes) -> Level:
    """The UX measurement method (ux/tools/b6-measure/measure.py): 40 ms windows with a 10 ms hop; windows within 30 dB
    of the loudest and above −55 dBFS count as voiced.

    UX の計測方法（ux/tools/b6-measure/measure.py）：40 ミリ秒の窓を 10 ミリ秒ずつずらし、最も大きい窓から 30 dB 以内
    かつ −55 dBFS より大きい窓を有声とする。
    """
    e = _block_energy(samples(pcm))
    wins = [sum(e[k : k + WIN]) / (WIN * FRAME) for k in range(len(e) - WIN + 1)]  # Window mean square / 窓の二乗平均
    if not wins:
        return Level(0.0, -120.0)
    db = [dbfs(math.sqrt(w)) for w in wins]
    gate = max(max(db) - REL_GATE_DB, FLOOR_DBFS)
    on = [k for k, d in enumerate(db) if d > gate]
    if not on:
        return Level(0.0, -120.0)
    hop, win = FRAME / RATE, WIN * FRAME / RATE
    segs = [[on[0], on[0]]]
    for k in on[1:]:
        if (k - segs[-1][1] - 1) * hop < MERGE_GAP_S:
            segs[-1][1] = k
        else:
            segs.append([k, k])
    sounding = sum((b - a) * hop + win for a, b in segs)
    span = (on[-1] - on[0]) * hop + win
    loud = dbfs(math.sqrt(sum(wins[k] for k in on) / len(on)))
    return Level(round(span, 3), round(loud, 2), round(sounding, 3))


def _yin(fr: list[float], rate: int) -> float | None:
    """F0 of this window (Hz); None when no period is found (no cumulative mean normalized difference below the
    threshold). Same as UX: after crossing the threshold, keep going down to the trough, then parabolic interpolation.

    この窓の基本周波数（Hz）。周期が見つからない（累積平均正規化差分がどれも閾値を下回らない）ときは None。UX と同じく、
    閾値を下回ったあとも谷底まで進み、放物線補間する。
    """
    w = len(fr)
    mean = sum(fr) / w
    x = [v - mean for v in fr]
    tmin, tmax = int(rate / F0_RANGE[1]), min(int(rate / F0_RANGE[0]), w // 2)
    cmnd = [1.0]
    total = 0.0
    found: int | None = None
    for tau in range(1, tmax + 1):
        d = sum((x[i] - x[i + tau]) ** 2 for i in range(w - tau))
        total += d
        cmnd.append(d * tau / total if total > 0 else 1.0)
        if found is None and tau >= tmin and cmnd[tau] < YIN_THRESH:
            found = tau
        elif found is not None and cmnd[tau] >= cmnd[tau - 1]:
            break
    if found is None:
        return None
    best = found
    while best + 1 < len(cmnd) and cmnd[best + 1] < cmnd[best]:
        best += 1
    off = 0.0
    if best + 1 < len(cmnd):
        a, b, c = cmnd[best - 1], cmnd[best], cmnd[best + 1]
        den = a - 2 * b + c
        off = 0.5 * (a - c) / den if den else 0.0
    return rate / (best + off)


@dataclass(frozen=True)
class Pitch:
    pitched: float  # Share of pitched windows / ピッチのある窓の割合
    median_hz: float | None  # Median F0 of the pitched windows / ピッチのある窓の基本周波数の中央値


def pitch_of(pcm: bytes) -> Pitch:
    """Among windows within 20 dB of the loudest, the share where YIN (threshold 0.15, 60–400 Hz) finds a period, and
    the median F0. Computed after averaging every three samples down to 8 kHz (pure Python). Whispers and breathy voice
    have no period (UX measured メロス「ああ。」 as pitched only in its first 0.09 seconds).

    最も大きい窓から 20 dB 以内の窓のうち、YIN（閾値 0.15、60〜400 Hz）が周期を見つけられた割合と、基本周波数の中央値。
    3 サンプルずつ平均して 8 kHz に落としてから計算する（純 Python）。ささやき声や息まじりの声では周期が見つからない
    （UX の計測ではメロス「ああ。」は頭の 0.09 秒しかピッチがなかった）。
    """
    a = samples(pcm)
    step = RATE // PITCH_RATE
    x = [sum(a[i : i + step]) / step for i in range(0, len(a) - step + 1, step)]
    hop, win = PITCH_RATE // 100, WIN * PITCH_RATE // 100
    frames = [x[k : k + win] for k in range(0, len(x) - win + 1, hop)]
    if not frames:
        return Pitch(0.0, None)
    db = [dbfs(math.sqrt(sum(v * v for v in f) / win)) for f in frames]
    loud = [f for f, d in zip(frames, db, strict=True) if d > max(db) - PITCH_GATE_DB]
    f0 = [f for f in (_yin(fr, PITCH_RATE) for fr in loud) if f is not None]
    return Pitch(round(len(f0) / len(loud), 2), round(statistics.median(f0), 1) if f0 else None)


def pitched(pcm: bytes) -> float:
    return pitch_of(pcm).pitched


def wav(pcm: bytes, rate: int = RATE) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm)
    return buf.getvalue()


def read_wav(path: Path) -> bytes:
    with wave.open(str(path), "rb") as w:
        if w.getframerate() != RATE or w.getnchannels() != 1 or w.getsampwidth() != 2:
            raise ValueError(
                f"{path.name}: must be 24 kHz, mono, 16-bit / {path.name}：24 kHz、モノラル、16 ビットが必要"
            )
        return w.readframes(w.getnframes())


# —— Encoding / エンコード ——

TP_TRIES = 6
TP_MARGIN_DB = 0.2


@dataclass(frozen=True)
class Encoded:
    data: bytes
    duration_ms: int
    # True peak of the output (fake encoder: sample peak) / 出力の真のピーク（偽エンコーダーではサンプルピーク）
    true_peak_dbtp: float
    loudness_dbfs: float  # Voiced loudness of the output (level) / 出力の有声ラウドネス（level）


class Encoder(Protocol):
    suffix: str

    def encode(self, pcm: bytes, gain_db: float = 0.0) -> Encoded: ...


class FfmpegEncoder:
    """AAC-LC, mono, 24 kHz, 48 kbps m4a. Metadata stripped and bit-for-bit reproducible (so the hash in the file name
    is stable).

    `gain_db` adjusts the whole line's volume; after encoding, the true peak is measured (ebur128), and above −1 dBTP a
    limiter is added (alimiter, no automatic makeup gain, latency compensated) and it is re-encoded, lowering the limit
    by the overshoot, at most 6 times. No limiter when nothing goes over.

    AAC-LC、モノラル、24 kHz、48 kbps の m4a。メタデータを除き、ビット単位で再現できる（ファイル名の hash が安定する
    ように）。

    `gain_db` でセリフ全体の音量を調整する。エンコード後に真のピークを測り（ebur128）、−1 dBTP を超えたらリミッター
    （alimiter、自動のゲイン補正なし、遅延は補正）を加えて再エンコードし、超えた分だけリミットを下げる。最大 6 回。
    超えなければリミッターは加えない。
    """

    suffix = ".m4a"

    def __init__(self) -> None:
        for tool in ("ffmpeg", "ffprobe"):
            if shutil.which(tool) is None:
                raise RuntimeError(
                    f"{tool} not found (on the Mac: brew install ffmpeg) / "
                    f"{tool} がない（Mac では brew install ffmpeg）"
                )

    def encode(self, pcm: bytes, gain_db: float = 0.0) -> Encoded:
        limit: float | None = None  # Limit (dBFS) / リミット（dBFS）
        with tempfile.TemporaryDirectory() as d:
            src, dst = Path(d) / "in.wav", Path(d) / "out.m4a"
            src.write_bytes(wav(pcm))
            for _ in range(TP_TRIES):
                filters = []
                if gain_db:
                    filters.append(f"volume={gain_db:.2f}dB")
                if limit is not None:
                    filters.append(f"alimiter=limit={10 ** (limit / 20):.4f}:level=disabled:latency=1")
                subprocess.run(
                    [
                        "ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-i", str(src),
                        *(["-af", ",".join(filters)] if filters else []),
                        "-c:a", "aac", "-profile:a", "aac_low", "-ac", "1", "-ar", str(RATE), "-b:a", "48k",
                        "-map_metadata", "-1", "-fflags", "+bitexact", "-flags:a", "+bitexact",
                        "-movflags", "+faststart", str(dst),
                    ],
                    check=True,
                )  # fmt: skip
                tp = true_peak(dst)
                if tp <= PEAK_DBFS:
                    return Encoded(dst.read_bytes(), probe_ms(dst), tp, level(decode(dst)).loudness_dbfs)
                limit = (PEAK_DBFS if limit is None else limit) - (tp - PEAK_DBFS) - TP_MARGIN_DB
        raise RuntimeError(
            f"After {TP_TRIES} tries the true peak is still {tp:.1f} dBTP, over {PEAK_DBFS} dBTP / "
            f"{TP_TRIES} 回抑えても真のピークが {tp:.1f} dBTP で、{PEAK_DBFS} dBTP を超えている"
        )


def probe_ms(path: Path) -> int:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return max(1, round(float(out) * 1000))


def true_peak(path: Path) -> float:
    """True peak (dBTP) from ffmpeg ebur128, the same one UX measures with.

    ffmpeg ebur128 による真のピーク（dBTP）。UX の計測と同じもの。
    """
    err = subprocess.run(
        ["ffmpeg", "-nostdin", "-nostats", "-i", str(path), "-af", "ebur128=peak=true", "-f", "null", "-"],
        check=True,
        capture_output=True,
        text=True,
    ).stderr
    summary = err[err.rfind("Summary:") :]
    for line in summary[summary.find("True peak:") :].splitlines():
        if line.strip().startswith("Peak:"):
            value = line.split(":", 1)[1].split()[0]
            return -120.0 if value == "-inf" else float(value)
    raise RuntimeError("ebur128 gave no true peak / ebur128 が真のピークを出さなかった")


def decode(path: Path) -> bytes:
    return subprocess.run(
        ["ffmpeg", "-nostdin", "-v", "error", "-i", str(path), "-f", "s16le", "-ac", "1", "-ar", str(RATE), "-"],
        check=True,
        capture_output=True,
    ).stdout


class FakeEncoder:
    """For CI: no ffmpeg; the "encoded" result is just WAV and the length is computed from the PCM. Volume is adjusted
    in Python and peaks are hard-clipped to −1 dBFS.

    CI 用：ffmpeg を呼ばず、「エンコード」結果はそのまま WAV で、長さは PCM から求める。音量は Python で調整し、ピークは
    −1 dBFS で強制的にクリップする。
    """

    suffix = ".wav"

    def encode(self, pcm: bytes, gain_db: float = 0.0) -> Encoded:
        if gain_db:
            g = 10 ** (gain_db / 20)
            ceiling = int(32768 * 10 ** (PEAK_DBFS / 20))
            pcm = to_bytes(array("h", (max(-ceiling, min(ceiling, round(x * g))) for x in samples(pcm))))
        peak = dbfs(max((abs(x) for x in samples(pcm)), default=0))
        return Encoded(wav(pcm), max(1, round(len(pcm) / 2 / RATE * 1000)), round(peak, 2), level(pcm).loudness_dbfs)
