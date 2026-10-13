# Casting fallback candidates (when a voice returns no text) / キャスティングの予備候補（音声がテキストを返さないとき）

UX · 2026-10-06 · Reply to PM's 13:55 request · Corresponds to ux-design §16.1

UX · 2026-10-06 · PM の 13:55 の依頼への回答 · ux-design §16.1 に対応

> **Status (13:57)**: PM has decided: the fallback candidates and the 「刑場：老爺 vs 王」 blind-listening pair go into the casting rerun together with the original §16.1 candidates, saving a round. Why 19 voices returned no text is still undetermined: in s3 the Iapetus scenario did have text, so it looks more like the text for long lines arrives late; the new package will record `transcript_late_ms`. If all 30 voices have text after the rerun, listen to the original §16.1 candidates and use the fallbacks only for comparison.
>
> **状態（13:57）**：PM が決定した。予備候補と「刑場：老爺 vs 王」のブラインド試聴の組は、§16.1 の元の候補と一緒に casting の再実行に入れ、1 回分を節約する。19 個の音声にテキストがなかった原因はまだ結論が出ていない。s3 では Iapetus のシナリオにテキストがあったので、長いセリフのテキストが遅れて届いている可能性が高い。新しいパッケージでは `transcript_late_ms` を記録する。再実行後に 30 個の音声すべてにテキストがあれば、§16.1 の元の候補どおりに試聴し、予備は比較用にとどめる。

## 0. Conclusions / 結論

- **妹**: fallbacks Despina (Smooth) → Erinome (Clear).
  **妹**：予備は Despina（Smooth）→ Erinome（Clear）。
- **町の老爺**: Rasalgethi goes to the 老爺, and フィロストラトス switches to Enceladus. The 老爺 also gets Zubenelgenubi (Casual) → Algieba (Smooth) as fallbacks.
  **町の老爺**：Rasalgethi は老爺に回し、フィロストラトス は Enceladus に変える。老爺にはさらに Zubenelgenubi（Casual）→ Algieba（Smooth）を予備として加える。
- メロス, 王 and セリヌンティウス each have only one candidate left. If that one does not sound like the character, another round would be needed, so this time each also gets one fallback (see §2). Each (character, voice) combination costs about 0.02 USD more, under 0.2 USD in total.
  メロス、王、セリヌンティウス はそれぞれ候補が 1 つしか残っていない。その 1 つが人物らしく聞こえなければもう 1 回実行し直すことになるので、今回はそれぞれに予備を 1 つずつ加える（§2 参照）。（人物、音声）の組み合わせごとに約 0.02 米ドル増え、合計でも 0.2 米ドル以内。
- The premise follows what PM said: if a voice still has no text after the rerun, it cannot be used (S-056: the gateway needs the text of both sides). If all 30 have text after the rerun, these fallbacks are not used, and we listen to the original §16.1 candidates.
  前提は PM の言うとおり：再実行後もテキストのない音声は使えない（S-056 ゲートウェイは双方のテキストを必要とする）。再実行後に 30 個すべてにテキストがあれば、この予備は使わず、§16.1 の元の候補どおりに試聴する。

## 1. The full lineup in the worst case (only the 11 voices with text) / 最悪の場合の配役一式（テキストのある 11 個だけを使う）

The 11 with text are 9 male voices and 2 female voices. The characters are 6 male and 1 female, so each character can get its own voice with no repeats.

テキストのある 11 個は男声 9 個と女声 2 個。人物は男 6 人と女 1 人なので、1 人に 1 つの声を重複なく割り当てられる。

| Character / 登場人物 | First choice / 第一候補 | Fallback / 予備 | Reason / 理由 |
|---|---|---|---|
| メロス | Fenrir（Excitable） | Sadachbia（Lively） | Young, hurried, easily out of breath / 若く、せっかちで、すぐ息が上がる |
| 王ディオニス | Charon（Informative） | Algieba（Smooth） | Low, cold, slow; Smooth can play “calm cruelty” / 低く、冷たく、遅い。Smooth なら「冷静な残酷さ」を演じられる |
| セリヌンティウス | Umbriel（Easy-going） | Schedar（Even） | Steady, a man of few words / 落ち着いていて、口数が少ない |
| 妹 | Despina（Smooth） | Erinome（Clear） | 16 years old, introverted, soft. Both lean mature; use direction to make them lighter and slower / 16 歳、内気、やわらかい。どちらも大人びているので、direction で軽く、ゆっくりに抑える |
| 花婿 | Schedar（Even） | Sadachbia（Lively） | Honest, earnest / 実直で、まじめ |
| フィロストラトス | Enceladus（Breathy） | — | The breathy voice is exactly “grief” / 息まじりの声がちょうど「悲痛」に合う |
| 町の老爺 | Rasalgethi（Informative） | Zubenelgenubi（Casual）→ Algieba（Smooth） | Old and frightened; use direction to lower it, slow it down and add pauses / 年老いて、怯えている。direction で低く、ゆっくりにし、間を入れる |

When fallbacks collide: Sadachbia is the fallback for both メロス and 花婿, Schedar is both the fallback for セリヌンティウス and the first choice for 花婿, and Algieba is the fallback for both the king and the 老爺. Only one side will end up using it; if both sides need it, 花婿 gives it up, because 花婿 appears only in the village and has the fewest lines.

予備が重なるとき：Sadachbia はメロスと花婿の両方の予備、Schedar はセリヌンティウス の予備と花婿の第一候補を兼ね、Algieba は王と老爺の両方の予備。実際に使うのはどちらか一方だけ。両方で必要になったら花婿が譲る。花婿は村にしか登場せず、出番がいちばん少ないからだ。

**妹 has only two candidates; this is a risk.** If neither Despina nor Erinome sounds 16, this goes to PM: either accept a more mature-sounding 妹, or wait to see whether female voices get their text back after the rerun. Do not fill in with a male voice or any other voice.

**妹 は候補が 2 つしかなく、ここがリスク。** Despina も Erinome も 16 歳に聞こえなければ、この件は PM に渡す：大人びた妹を受け入れるか、再実行後に女声のテキストが戻るかを待つか。男声やほかの声で代用してはならない。

## 2. Changes for the backend (`candidates` in s1_casting.json; fallbacks appended, first choices unchanged) / バックエンドへ渡す変更（s1_casting.json の candidates。予備は後ろに足し、第一候補は動かさない）

I do not edit the backend's directory; please copy this over as is:

バックエンドのディレクトリは私は変更しない。バックエンド側でこのまま写してほしい：

```json
{
  "melos":        ["Puck", "Fenrir", "Alnilam", "Sadachbia"],
  "king":         ["Algenib", "Charon", "Orus", "Algieba"],
  "selinuntius":  ["Iapetus", "Achird", "Umbriel", "Schedar"],
  "sister":       ["Leda", "Achernar", "Despina", "Erinome"],
  "groom":        ["Schedar", "Sadachbia"],
  "philostratus": ["Enceladus", "Rasalgethi"],
  "old-man":      ["Sadaltager", "Rasalgethi", "Zubenelgenubi", "Algieba"]
}
```

Combinations already generated cost nothing more (leave out `--redo`); 7 combinations are new.

生成済みの組み合わせには再び費用がかからない（`--redo` は付けない）。新たに加わるのは 7 組。

**One more blind-listening pair**: at the execution ground in the ending, the king and the 老爺 are on stage at the same time (ux-design 11.1; the 老爺 is `in-crowd`), and Charon and Rasalgethi are both tagged Informative, so they are the most likely to be confused.

**ブラインド試聴に 1 組追加**：結末の刑場では王と老爺が同時にその場にいる（ux-design 11.1、老爺は `in-crowd`）。Charon と Rasalgethi はどちらもタグが Informative なので、いちばん聞き間違えやすい。

```json
{ "scene": "刑場", "a": "old-man", "b": "king" }
```

The blind-listening lineup for the worst case:

最悪の場合のブラインド試聴の組み合わせ：

```
--pick melos=Fenrir,king=Charon,selinuntius=Umbriel,sister=Despina,groom=Schedar,philostratus=Enceladus,old-man=Rasalgethi
```

## 3. direction (妹 and 老爺) / direction（妹 と 老爺）

The current direction in s1_casting.json already says 「十六歳の内気な娘。やわらかく、軽い声で」 and 「低く、ゆっくり、弱々しく、ささやくように」, which is enough. The fallback voices are mature at base, so I suggest adding half a sentence to the end of each:

s1_casting.json の現在の direction には、すでに「十六歳の内気な娘。やわらかく、軽い声で」と「低く、ゆっくり、弱々しく、ささやくように」が書いてあり、これで足りる。予備の声は素地が大人びているので、それぞれの末尾に半文ずつ足すことを提案する：

- 妹：「語尾を少し弱く。」
- 町の老爺：「言葉の間に短い間を置く。」

## 4. What to listen for (together with the §16.1 test) / 試聴で確かめること（§16.1 のテストと一緒に）

- Fit with the character: for each combination, 5 listeners hear 3 of the character's own lines and rate it “fits / barely / doesn't fit”.
  人物に合うか：組み合わせごとに 5 人がその人物自身のセリフを 3 つ聞き、「合う／なんとか／合わない」で評価する。
- Distinguishable within a scene: ≥90% per §16.1; 6 pairs plus 1 pair at the execution ground, 7 pairs in total.
  シーンの中で聞き分けられるか：§16.1 の ≥90%。6 組に刑場の 1 組を加えて、計 7 組。
- One extra check for 妹: whether the listeners' age estimates fall under 20. If most estimate 25 or older, record it as “too mature” and hand it to PM.
  妹 だけもう 1 点見る：聞いた人が推定した年齢が 20 歳未満に収まるか。多くの人が 25 歳以上と推定したら「大人びている」と記録し、PM に渡す。
- As before, the results go to PM for zg to decide (Q-004).
  結果はこれまでどおり PM に渡し、zg が決める（Q-004）。
