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
- 按 D-040 开发期不跑评测；全部用例第 26 步一起跑：`uv run zoujin-eval --cases evals/acts/actN`（和 `evals/seeds` 各跑一次）。
