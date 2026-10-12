# 第二〜四幕的用例和画像（清单第 14、15 步）

第一幕在 `evals/seeds`（编写源 `evals/gen_seeds.py`，数据工程）。第二、三、四幕各一个目录，各由一个线程写，互不改别人的目录：

| 目录 | 幕 | 用例 ID | 画像 ID |
|---|---|---|---|
| `act2/` | 第二幕「その夜」（t 1440〜2280：夜道、川、守夜的王城） | `E1-201`〜`E8-299` | `persona.a2-…` |
| `act3/` | 第三幕「村の二日」（t 1980〜4900：村、婚礼、大雨；市里的人质） | `E1-301`〜`E8-399` | `persona.a3-…` |
| `act4/` | 第四幕「三日目」（t 4590〜5520：川、峠、泉、野の道、刑场） | `E1-401`〜`E8-499` | `persona.a4-…` |

- 只改自己目录的 `cases.py`：`CASES`（用例，写法同 `gen_seeds.py`，helpers 在 `helpers.py`）和 `PERSONAS`（模拟局画像，格式同 `evals/personas.json`：id、role、goal、style）。`E*.jsonl`、`personas.json` 是生成物。
- 套件 E1〜E8 的意思同 `evals/README.md`。检查点写这一幕里的节拍或时刻（`sc.canon@beat.NN`、`sc.canon@t=NNNN`），模拟局 `setup.persona` 用自己的画像。世界模型是完整版 `worlds/hashire-merosu/1.0.0-draft`（契约 1.14，W-2）。
- 校验（从仓库根目录，先 `uv sync`）：`bash .github/scripts/check_world.sh`。它重新生成三幕的文件、对完整版跑 check_evals，最后要求生成物和提交的一致：错误 0、「生成物一致」才合。
- D-040 是此前暂停真实评测的历史决定。2026-10-12 用户已授权恢复真实四幕文字评测和 B-22 模拟；评审员校准与预录语音仍暂缓。有限批次命令和留证要求见 `evals/README.md` 的 R1 部分。
- `helpers.write` 为非 persona 用例显式布置 `var.act.current=act.N`。检查点推进时间和原著事实不会自动替玩家选择幕末去处；不设置这一项会让第四幕提示仍看到第一幕。这里不改变人物知识、因果或结局分类。Persona 用例始终从正式开局玩起。
