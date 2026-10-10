# 走れメロス — text extraction notes

## Method

- Canonical source: Aozora Bunko `hashire_merosu.txt` (txt), converted deterministically by `tools/aozora_to_plain.py` (no model transcription).
- Header (title/author/notation block) and footer (底本 onward) removed; ［＃…］ annotations dropped; leading full-width space stripped; one paragraph per line.
- melos_ruby.txt renders ruby as 漢字（よみ）. Caution: the text's own full-width parentheses (e.g. the closing source note) look the same.

## Stats

- Paragraphs: 75
- Characters (plain, excluding newlines): 9814 (without spaces: 9806)
- Ruby annotations: 88
- Blank-line breaks inside the body (txt only): 0
- Gaiji (※［＃…］) found: 0 
- Annotations removed: 1 ['［＃地から１字上げ］']

## Sanity checks

- Starts with 「メロスは激怒した。」: True
- Length in 9,000–10,500: True
- 「三日目には日没までに帰って来い。」 occurrences: 1
- 「結婚式は、真昼に行われた。」 occurrences: 1
- 「眼が覚めたのは翌る日の薄明の頃である。」 occurrences: 1
- 「勇者は、ひどく赤面した。」 occurrences: 1
- Last paragraph: 「（古伝説と、シルレルの詩から。）」

## Cross-check: ruby .txt vs XHTML

- Paragraphs: txt 75, html 75
- Differing spots (plain text): 0

## Bibliographic information (from the source file)

    底本：「太宰治全集3」ちくま文庫、筑摩書房
    　　　1988（昭和63）年10月25日初版発行
    　　　1998（平成10）年6月15日第2刷
    底本の親本：「筑摩全集類聚版太宰治全集」筑摩書房
    　　　1975（昭和50）年6月～1976（昭和51）年6月
    入力：金川一之
    校正：高橋美奈子
    2000年12月4日公開
    2011年1月17日修正
    青空文庫作成ファイル：
    このファイルは、インターネットの図書館、青空文庫（http://www.aozora.gr.jp/）で作られました。入力、校正、制作にあたったのは、ボランティアの皆さんです。

XHTML version:

    底本：「太宰治全集3」ちくま文庫、筑摩書房
    1988（昭和63）年10月25日初版発行
    1998（平成10）年6月15日第2刷
    底本の親本：「筑摩全集類聚版太宰治全集」筑摩書房
    1975（昭和50）年6月～1976（昭和51）年6月
    入力：金川一之
    校正：高橋美奈子
    2000年12月4日公開
    2011年1月17日修正
    青空文庫作成ファイル：
    このファイルは、インターネットの図書館、青空文庫（http://www.aozora.gr.jp/）で作られました。入力、校正、制作にあたったのは、ボランティアの皆さんです。
