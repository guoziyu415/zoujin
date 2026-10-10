# 『走れメロス』切片版世界模型（hashire-merosu@1.0.0-slice）

负责人：数据工程 · 契约：`data/contracts.md` v1.7 · 依据：S-077（`pm/decisions.md`）、dev-plan「完整世界模型 + 一份切片配置」

M2 竖切片（R1 试玩）用的世界模型。和完整版同一个 Schema，B-0、worldsim、评测照读；**不手写**，由 `make_slice.py` 从 `1.0.0-draft/world.src.json` 生成，切片和完整版的差别全在这个脚本里，每一处改动注明 S-077 的哪一条。

| 文件 | 是什么 |
|---|---|
| `make_slice.py` | 生成脚本。**只改这个文件**（或完整版的编写源） |
| `world.src.json` | 生成的编写源，build_world 读它 |
| `world.json` | build_world 生成：后端运行时读它 |
| `report.md` | 校验报告。情景用完整版的 `scenarios.json`，24 次推演的结果应和完整版一样 |

`bash .github/scripts/check_world.sh` 一起重新生成和校验（CI 也跑，生成物和仓库里的不一样就失败）。

## 和完整版的差别

| S-077 | 改动 |
|---|---|
| ① | 只开旅人，王城的三条 `conditionalAccess` 不开；旅人去不了的地点上的情境动作去掉（王城的「保証する」、归途和村子的；剩下第一幕的「家まで送る」）；没人拿得到的物品去掉。第一幕、第四幕的 `scenes` 只有广场 |
| ② | `var.player.custody` 去掉 `arrested`：叙事者提交它会被第 3 步按取值拒掉（`bad-value`） |
| ④⑤ | 第一幕的去处换成两个，都跳到 act.4、三日目 17:30（`t: 5370`）、刑场：`exit.1.city`「市に残り、メロスの帰りを待つ」落在 `ground-west`；`exit.1.old-man`「老爺の家に身を寄せる」要送过老爺（`var.player.walkedOldManHome`），落在 `stake-front`，老爺站旁边、先开口。两个都把老爺移到刑场、フィロストラトス移到进城的路，都带副题的后半（`sub`）和落地句（`arrival`，UX `ux/slice/jump-transition.md`）。「ほかの考えがある」是前端的固定选项，不是去处；成行时落在第一幕的 `plan`（契约 1.7 的 `Act.plan`，C-19）：同样到三日目 17:30 的刑场，玩家站 `stake-front`，老爺在西头 `ground-west`，落地句是 UX 的「三日目の夕方。あなたは、刑場の近くに来ていた。」 |
| ⑤ | 第二、三幕原样留着，跳转时在后台结算；落在归途的 `exit.3.road` 去掉（切片里不会出现） |
| S-050 | 只有梅洛斯和老爺能对话（`talkable`），别的人物只有走动版（S-078 ①） |
| ⑩ | セリヌンティウス、フィロストラトス开局 `initialActivity: absent`：石工房开着，第一幕见不到两人 |

切片用例在 `evals/slice/`（`evals/gen_slice.py` 生成），`uv run zoujin-eval --slice` 跑。
