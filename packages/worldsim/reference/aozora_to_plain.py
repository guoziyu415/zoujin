#!/usr/bin/env python3
"""Convert an Aozora Bunko file (ruby .txt from the zip, or the XHTML page)
into one-paragraph-per-line plain and ruby-in-parentheses text.

Usage:
  python3 -I aozora_to_plain.py --txt 1567_ruby_4948/hashire_merosu.txt \
      [--html 1567_14913.html] --out OUTDIR

Writes OUTDIR/melos_plain.txt, OUTDIR/melos_ruby.txt, OUTDIR/NOTES.md.
When both --txt and --html are given, the two plain renderings are diffed
paragraph by paragraph and the result goes into NOTES.md (the .txt is canonical).
Only the standard library is used.
"""
import argparse
import difflib
import html
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

KANJI = r"[㐀-䶿一-鿿豈-﫿\U00020000-\U0002FFFF々〆〇ヶ仝]"
RE_RUBY_BAR = re.compile(r"｜([^｜《]+?)《([^》]+)》")
RE_RUBY_KANJI = re.compile(rf"({KANJI}+)《([^》]+)》")
RE_ANNOT = re.compile(r"［＃[^］]*］")
RE_GAIJI = re.compile(r"※［＃[^］]*］")

SANITY_START = "メロスは激怒した。"
SANITY_SENTENCES = [
    "三日目には日没までに帰って来い。",
    "結婚式は、真昼に行われた。",
    "眼が覚めたのは翌る日の薄明の頃である。",
    "勇者は、ひどく赤面した。",
]


def decode(raw: bytes) -> str:
    for enc in ("utf-8", "cp932"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    raise SystemExit("cannot decode input as UTF-8 or Shift_JIS(cp932)")


# ---------------------------------------------------------------- .txt
def parse_txt(text: str):
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    # header: title/author, then a block fenced by two rules of hyphens
    rules = [i for i, l in enumerate(lines[:80]) if re.fullmatch(r"-{20,}", l.strip())]
    if len(rules) >= 2:
        start = rules[1] + 1
    else:  # no notation block: skip title/author up to the first blank line
        start = next(i for i, l in enumerate(lines) if not l.strip()) + 1
    end = next((i for i, l in enumerate(lines) if l.startswith("底本：")), len(lines))
    header = [l for l in lines[: rules[0] if rules else start] if l.strip()]
    biblio = [l for l in lines[end:] if l.strip()]

    gaiji, annots, blank_runs = [], [], 0
    paras_ruby, paras_plain = [], []
    pending_blank = False
    for l in lines[start:end]:
        gaiji += RE_GAIJI.findall(l)
        annots += RE_ANNOT.findall(l)
        body = RE_ANNOT.sub("", l).rstrip()
        if not body.strip():
            if l.strip() == "" and paras_plain:
                pending_blank = True
            continue
        if pending_blank:  # a blank run between two paragraphs = section break
            blank_runs += 1
            pending_blank = False
        body = body.lstrip("　 ")
        ruby = RE_RUBY_KANJI.sub(r"\1（\2）", RE_RUBY_BAR.sub(r"\1（\2）", body))
        plain = re.sub(r"《[^》]*》", "", body).replace("｜", "")
        paras_ruby.append(ruby)
        paras_plain.append(plain)
    return dict(header=header, biblio=biblio, plain=paras_plain, ruby=paras_ruby,
                gaiji=gaiji, annots=annots, blank_breaks=blank_runs)


# ---------------------------------------------------------------- .html
class MainText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth = 0          # div depth inside main_text (0 = outside)
        self.bib_depth = 0
        self.skip = 0           # inside span.notes / rp
        self.in_rt = False
        self.buf_plain, self.buf_ruby = [""], [""]
        self.bib = []
        self.gaiji = []
        self.annots = []
        self.title = []
        self.in_title = False

    def _emit(self, plain, ruby=None):
        self.buf_plain[-1] += plain
        self.buf_ruby[-1] += plain if ruby is None else ruby

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        cls = a.get("class", "") or ""
        if tag == "div" and self.depth:
            self.depth += 1
        elif tag == "div" and "main_text" in cls.split():
            self.depth = 1
        elif tag == "div" and self.bib_depth:
            self.bib_depth += 1
        elif tag == "div" and "bibliographical_information" in cls.split():
            self.bib_depth = 1
        if tag in ("h1", "h2") and not self.depth:
            self.in_title = True
        if not self.depth:
            if self.bib_depth and tag == "br":
                self.bib.append("\n")
            return
        if tag == "br":
            self.buf_plain.append("")
            self.buf_ruby.append("")
        elif tag == "span" and "notes" in cls.split():
            self.skip += 1
        elif tag == "rp":
            self.skip += 1
        elif tag == "rt":
            self.in_rt = True
            self.buf_ruby[-1] += "（"
        elif tag == "img" and "gaiji" in cls.split():
            alt = a.get("alt", "")
            self.gaiji.append(alt)
            self._emit("※", "※")
        elif self.skip and tag == "span":
            self.skip += 1

    def handle_endtag(self, tag):
        if tag in ("h1", "h2"):
            self.in_title = False
        if tag == "div" and self.depth:
            self.depth -= 1
            return
        if tag == "div" and self.bib_depth:
            self.bib_depth -= 1
            return
        if not self.depth:
            return
        if tag in ("span", "rp") and self.skip:
            self.skip -= 1
        elif tag == "rt":
            self.in_rt = False
            self.buf_ruby[-1] += "）"

    def handle_data(self, data):
        if self.in_title:
            self.title.append(data.strip())
        if self.bib_depth and not self.depth:
            self.bib.append(data)
            return
        if not self.depth:
            return
        if self.skip:
            self.annots.append(data)
            return
        data = data.replace("\r", "").replace("\n", "")
        if self.in_rt:
            self.buf_ruby[-1] += data
        else:
            self._emit(data)


def parse_html(text: str):
    p = MainText()
    p.feed(text)
    plain, ruby = [], []
    for pl, ru in zip(p.buf_plain, p.buf_ruby):
        pl = RE_ANNOT.sub("", pl).rstrip()
        ru = RE_ANNOT.sub("", ru).rstrip()
        if not pl.strip():
            continue
        plain.append(pl.lstrip("　 "))
        ruby.append(ru.lstrip("　 "))
    bib = [l.strip() for l in html.unescape("".join(p.bib)).split("\n") if l.strip()]
    return dict(header=[t for t in p.title if t], biblio=bib, plain=plain, ruby=ruby,
                gaiji=p.gaiji, annots=p.annots, blank_breaks=None)


# ---------------------------------------------------------------- checks
def sanity(plain):
    joined = "".join(plain)
    out = {
        "paragraphs": len(plain),
        "chars": len(joined),
        "chars_no_space": len(re.sub(r"[\s　]", "", joined)),
        "starts_ok": joined.startswith(SANITY_START),
        "in_range": 9000 <= len(joined) <= 10500,
        "sentences": {s: joined.count(s) for s in SANITY_SENTENCES},
        "first": plain[0] if plain else "",
        "last": plain[-1] if plain else "",
    }
    return out


def diff_versions(a, b):
    sm = difflib.SequenceMatcher(a=a, b=b, autojunk=False)
    spots = []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            continue
        # character-level detail inside paired paragraphs
        for k in range(max(i2 - i1, j2 - j1)):
            pa = a[i1 + k] if i1 + k < i2 else ""
            pb = b[j1 + k] if j1 + k < j2 else ""
            cm = difflib.SequenceMatcher(a=pa, b=pb, autojunk=False)
            for cop, a1, a2, b1, b2 in cm.get_opcodes():
                if cop != "equal":
                    spots.append((i1 + k + 1, cop, pa[max(0, a1 - 8):a2 + 8], pb[max(0, b1 - 8):b2 + 8]))
    return spots


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--txt")
    ap.add_argument("--html")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    if not (args.txt or args.html):
        ap.error("give --txt and/or --html")

    res = {}
    if args.txt:
        res["txt"] = parse_txt(decode(Path(args.txt).read_bytes()))
    if args.html:
        res["html"] = parse_html(decode(Path(args.html).read_bytes()))
    canon_key = "txt" if "txt" in res else "html"
    canon = res[canon_key]

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "melos_plain.txt").write_text("\n".join(canon["plain"]) + "\n", encoding="utf-8")
    (out / "melos_ruby.txt").write_text("\n".join(canon["ruby"]) + "\n", encoding="utf-8")

    s = sanity(canon["plain"])
    n_ruby = sum(r.count("（") - p.count("（") for p, r in zip(canon["plain"], canon["ruby"]))
    notes = ["# 走れメロス — text extraction notes", "",
             "## Method", "",
             f"- Canonical source: Aozora Bunko `{Path(args.txt or args.html).name}` ({canon_key}), "
             "converted deterministically by `tools/aozora_to_plain.py` (no model transcription).",
             "- Header (title/author/notation block) and footer (底本 onward) removed; "
             "［＃…］ annotations dropped; leading full-width space stripped; one paragraph per line.",
             "- melos_ruby.txt renders ruby as 漢字（よみ）. Caution: the text's own full-width "
             "parentheses (e.g. the closing source note) look the same.", "",
             "## Stats", "",
             f"- Paragraphs: {s['paragraphs']}",
             f"- Characters (plain, excluding newlines): {s['chars']} (without spaces: {s['chars_no_space']})",
             f"- Ruby annotations: {n_ruby}",
             f"- Blank-line breaks inside the body (txt only): {canon['blank_breaks']}",
             f"- Gaiji (※［＃…］) found: {len(canon['gaiji'])} {canon['gaiji'] if canon['gaiji'] else ''}",
             f"- Annotations removed: {len(canon['annots'])} {sorted(set(canon['annots']))[:20]}", "",
             "## Sanity checks", "",
             f"- Starts with 「{SANITY_START}」: {s['starts_ok']}",
             f"- Length in 9,000–10,500: {s['in_range']}"]
    notes += [f"- 「{k}」 occurrences: {v}" for k, v in s["sentences"].items()]
    notes += [f"- Last paragraph: 「{s['last']}」", ""]

    if "txt" in res and "html" in res:
        spots = diff_versions(res["txt"]["plain"], res["html"]["plain"])
        notes += ["## Cross-check: ruby .txt vs XHTML", "",
                  f"- Paragraphs: txt {len(res['txt']['plain'])}, html {len(res['html']['plain'])}",
                  f"- Differing spots (plain text): {len(spots)}"]
        notes += [f"  - para {p} {op}: txt 「{a}」 / html 「{b}」" for p, op, a, b in spots[:50]]
        notes.append("")

    notes += ["## Bibliographic information (from the source file)", ""]
    notes += [f"    {l}" for l in canon["biblio"]] or ["    (not found)"]
    if "html" in res and canon_key == "txt" and res["html"]["biblio"]:
        notes += ["", "XHTML version:", ""] + [f"    {l}" for l in res["html"]["biblio"]]
    (out / "NOTES.md").write_text("\n".join(notes) + "\n", encoding="utf-8")

    print("\n".join(notes[notes.index("## Stats"):]))


if __name__ == "__main__":
    main()
