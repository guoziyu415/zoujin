# 选角后备候选（声音不回传文字时）

UX · 2026-10-06 · 回应 PM 13:55 的请求 · 对应 ux-design §16.1

> **状态（13:57）**：PM 定了，后备候选和「刑場：老爺 vs 王」这组盲听，都和 §16.1 的原候选一起进 casting 重跑，省一轮。19 个声音没文字的原因还没定论：s3 里 Iapetus 的情景有文字，所以更像是长台词的文字晚到，新包会记 `transcript_late_ms`。如果重跑后 30 个声音都有文字，就照 §16.1 的原候选听，后备只做对比。

## 0. 结论

- **妹**：后备 Despina（Smooth）→ Erinome（Clear）。
- **町の老爺**：Rasalgethi 归老爺，フィロストラトス 改用 Enceladus。老爺另加 Zubenelgenubi（Casual）→ Algieba（Smooth）做后备。
- メロス、王、セリヌンティウス 各只剩一个候选。如果这一个听下来不像人物，就得再跑一轮，所以这次每人顺带加一个后备（见 §2）。每个（人物, 声音）组合多花约 0.02 美元，加起来 0.2 美元以内。
- 前提照 PM 说的：重跑后如果某个声音还是没文字，就不能用（S-056 网关要两边文字）。如果重跑后 30 个都有文字，这份后备就不用了，照 §16.1 原候选听。

## 1. 最坏情况下的整套搭配（只用有文字的 11 个）

有文字的 11 个是 9 个男声和 2 个女声。人物里男 6 女 1，所以可以一人一声，不重复。

| 人物 | 首选 | 后备 | 理由 |
|---|---|---|---|
| メロス | Fenrir（Excitable） | Sadachbia（Lively） | 年轻、急、容易喘 |
| 王ディオニス | Charon（Informative） | Algieba（Smooth） | 低、冷、慢；Smooth 可以演出「冷静的残酷」 |
| セリヌンティウス | Umbriel（Easy-going） | Schedar（Even） | 沉稳、话少 |
| 妹 | Despina（Smooth） | Erinome（Clear） | 16 岁、内向、柔。两个都偏成熟，靠 direction 压轻、压慢 |
| 花婿 | Schedar（Even） | Sadachbia（Lively） | 老实、认真 |
| フィロストラトス | Enceladus（Breathy） | — | 气声正好是「悲痛」 |
| 町の老爺 | Rasalgethi（Informative） | Zubenelgenubi（Casual）→ Algieba（Smooth） | 年老、害怕；靠 direction 压低、放慢、加停顿 |

后备有冲突时：Sadachbia 同时是メロス和花婿的后备，Schedar 同时是セリヌンティウス 的后备和花婿的首选，Algieba 同时是王和老爺的后备。只会有一边用上；两边都要用时，花婿让出去，因为花婿只在村里出场，人物最少。

**妹 只有两个候选，是风险点。** 如果 Despina 和 Erinome 听起来都不像 16 岁，这件事交 PM：要么接受偏成熟的妹，要么等重跑后看女声有没有恢复文字。不要拿男声或别的声音顶上。

## 2. 交给后端的改动（s1_casting.json 的 candidates，后备接在后面，首选不动）

后端的目录我不改，请后端照抄：

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

已经生成过的组合不再花钱（`--redo` 不加），新加的是 7 个组合。

**盲听加一组**：结局的刑场上，王和老爺同时在场（ux-design 11.1，老爺是 `in-crowd`），而 Charon 和 Rasalgethi 的标签都是 Informative，最可能听混。

```json
{ "scene": "刑場", "a": "old-man", "b": "king" }
```

最坏情况的盲听搭配：

```
--pick melos=Fenrir,king=Charon,selinuntius=Umbriel,sister=Despina,groom=Schedar,philostratus=Enceladus,old-man=Rasalgethi
```

## 3. direction（妹 和 老爺）

s1_casting.json 里现在的 direction 已经写了「十六歳の内気な娘。やわらかく、軽い声で」和「低く、ゆっくり、弱々しく、ささやくように」，够用。后备声音的底子偏成熟，建议各在末尾加半句：

- 妹：「語尾を少し弱く。」
- 町の老爺：「言葉の間に短い間を置く。」

## 4. 听的时候看什么（和 §16.1 的测试一起）

- 合不合人物：5 个人每个组合听 3 句自己的台词，按「像／勉强／不像」打。
- 场景里分不分得清：§16.1 的 ≥90%，6 组加刑场 1 组，共 7 组。
- 妹 额外看一条：听的人估的年龄有没有落在 20 岁以下。多数人估 25 岁以上，就记成「偏成熟」，交 PM。
- 结果照旧交 PM 给 zg 定（Q-004）。
