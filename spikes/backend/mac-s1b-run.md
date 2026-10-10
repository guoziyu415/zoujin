# 交给「检查电脑开发环境」：S-1b 语音代理（Mac 本地一段 + iPhone 4G 一段）

来自：后端 · 2026-10-06 · 依据：zg 选了临时部署（`pm/decisions.md` D-017，附三个条件：网址随机、网址和页面上不出现产品名和 zg 的名字、要输一次性测试码）；方案 `backend/spikes/s1b-plan.md`。

背景：手机 4G 下「松手到听见回答」要多久、打断、AirPods、LINE 内置浏览器、小声说话，这些只能在 iPhone 上测。后端写了一个只有メロス一个人物的语音代理，前端写测试页。分两段：第一段只在 Mac 本地跑，不部署；第二段临时部署到走进物语的 GCP 项目，测完当天删除。

## 共同规则

- 每个新 shell 先执行（和 `pm/handoffs/mac-spike-run.md` 一样）：
  ```bash
  cd ~/Developer/zoujin-spike && export CLOUDSDK_ACTIVE_CONFIG_NAME=zoujin && export ZJ_PROJECT="$(gcloud config get-value project 2>/dev/null)"
  ```
  确认 `ZJ_PROJECT` 非空、不是日々の森的项目，再继续。
- **地址、测试码、项目 ID 不进聊天、不进任何消息。** 它们只在 `~/.zoujin-spike/` 里（只有 zg 能读）。不要 `cat` 这些文件，也不要把 `~/.zoujin-spike/s1b-deploy.log` 的内容贴出来；出错时只转述错误那一行，先删掉其中的网址。
- 只执行这份说明里的命令。超出范围（建别的东西、开别的 API、改 gcloud 的默认配置、`docker` 的永久设置）先问 zg。
- 任何一步失败就停下，把错误告诉 zg 和后端（session cse_01Xq2jvETnKTfAxwLjVYfLcx），不要自己绕过。
- 把当前在做哪一步写在状态清单里。

## 换新包（和 casting、s4 的补跑一起做）

zg 下载新的 `zoujin-spike.zip` 后：解压到临时目录，只把代码覆盖进 `~/Developer/zoujin-spike/`：`README.md`、`s1b-plan.md`、`s1b_deploy.sh`、`s1b/`、`pyproject.toml`、`uv.lock`、`zj_spike/`、`tests/`，有 `page/` 也一起。**保留原来的 `out/`。** 然后：

```bash
uv sync
uv run python -m unittest tests.test_offline tests.test_s1b    # 离线自检，应为 43 项全过（e1bcb3ca886f 起的包）
```

`casting` 和 `s4_model_armor` 还没补跑的话，照 PM 交接文件的「补充」先跑完。

## 第一段：Mac 本地（不部署，现在就可以做）

1. 生成测试码：`uv run python -m zj_spike.s1b_proxy newcode`。屏幕上不显示码。告诉 zg：码在 `~/.zoujin-spike/s1b-code`，请他自己在终端 `cat` 看。
2. 在一个单独的终端里启动代理（一直开着）：
   ```bash
   # 包里有 page/（前端的测试页）时加上这一行；没有就跳过
   export ZJ_S1B_STATIC="$PWD/page"
   uv run python -m zj_spike.s1b_proxy serve
   ```
3. 在另一个终端（同样先执行开头那三行）跑冒烟测试，约 1 分钟、约 0.02 美元：
   ```bash
   uv run python -m zj_spike.s1b_proxy smoke
   ```
   每一项都应该是 `[OK]`。
4. 有 `page/` 时，请 zg 在 Mac 的 Safari 打开 `http://localhost:8080`，输入测试码，和メロス说几句、试一次打断。页面会显示计时。
5. 停掉代理（Ctrl+C）。用 send_message 把下面的数字发给后端和 PM（cse_0181jxeb77TxjmVYVSyhqxon）：
   - `out/s1b/smoke-*.json` 里的 `focusToReadyMs`，以及每一轮的 `serverReleaseToFirstAudioMs`、`clientReleaseToFirstAudioMs`；
   - `out/s1b/serve-*.jsonl` 里 `"event": "turn"` 那几行的数字（文件里只有数字，没有说话的内容）；
   - zg 在页面上试的感受，一两句。

## 第二段：iPhone 4G（D-017 已同意这一次；等 zg 说「4G 测试开始」再做）

zg 要在场、手边有 iPhone 和耳机，所以等他在线程里说「4G 测试开始」。Docker Desktop 要开着（`docker info` 能返回）。**先确认 `page/index.html` 存在**（前端的测试页，随新包一起来）；没有就不要开始，告诉后端「测试页还没到」。每一步之前在线程里用一句话说要做什么，做完说结果。

**重测（10-07 三次都停在 `up`，都已 `down`）：** 每次重测都要 zg 重新同意（经 PM）。要用最新的包（`prepare` 会多开一个 API、多一个角色，见 `s1b-plan.md` v0.7）。`down` 删掉了测试码，所以先执行 `uv run python -m zj_spike.s1b_proxy newcode`（不显示测试码），再从 `prepare` 开始。

```bash
./s1b_deploy.sh check      # 只读：现在有什么
./s1b_deploy.sh prepare    # 开 4 个 API（Cloud Run、Artifact Registry、IAM、IAM Service Account Credentials），建镜像仓库和只能调 Gemini 的服务账号
./s1b_deploy.sh sacheck    # 在 Mac 上以服务账号的身份连一次 Live（不说话、不花钱），最多等 7 分钟；连上才能 up
ZJ_S1B_PAGE="$PWD/page" ./s1b_deploy.sh build    # 在 Mac 上构建镜像，先断网以服务用户检查一次，通过才推送
./s1b_deploy.sh up         # 建成私有服务（只有 zg 的 Google 身份能访问），然后冒烟测试：必须全部 [OK]
./s1b_deploy.sh open       # 打开公开访问，再查一次匿名访问被拒
```

- `build` 推送前会在本机断网跑一次镜像（以 Cloud Run 上同样的非 root 用户），屏幕上应该是「读不了 0 个」「/health → 200，/ → 200（前端测试页）」「镜像检查通过」。镜像是 amd64 的，在 Apple 芯片上要模拟运行，可能慢十几秒。没通过就停下，镜像不会推送；把屏幕上那几行转给后端（里面只有容器里的路径，没有地址和项目 ID），然后 `./s1b_deploy.sh down`。
- `sacheck` 每 20 秒试一次，屏幕上每次失败一行（已去掉项目 ID、地址和账号）；新服务账号的权限可能要几分钟才生效，前几次 `[NG]` 是正常的。7 分钟还连不上就停下，把那几行转给后端，然后 `down`。
- `up` 的冒烟测试没过时，脚本会先显示服务日志里最近的会话错误（已去掉项目 ID、地址和账号），再停下；把那几行转给后端，然后 `down`。
- `up`、`open`、`down` 里的网址检查会每 10 秒问一次，等 Google 那边生效（最多分别 80 秒、3 分钟、2 分钟），中间没有输出是正常的。`up` 的冒烟测试如果只有声音那几项没过、访问保护全过，脚本会说明原因，等 2 分钟整套再跑一次；第二次还不过才算失败。
- `up` 会把测试码的哈希放进服务。服务名是随机的（`s-` 加 8 位），网址里没有产品名。
- `up` 的冒烟测试有任何一项不是 `[OK]`：不要执行 `open`，直接执行 `./s1b_deploy.sh down`，告诉后端。
- `open` 之后，脚本会提示 zg 自己做两件事：把地址用 `pbcopy` 和通用剪贴板发到 iPhone、`cat` 看测试码。**这两件由 zg 自己做，你不要执行。**
- zg 按 `s1b-plan.md` 第 5 节在 iPhone 上测 8 项，约 40 分钟。期间你不需要做任何事。

**zg 说测完以后，当天：**

```bash
./s1b_deploy.sh logs       # 计时数字拉回 out/s1b/logs-*.jsonl（只有时间戳和数字，没有项目 ID 和地址）
./s1b_deploy.sh down       # 删除服务、镜像仓库、服务账号，确认原地址返回 404，删掉本地的测试码和地址文件
./s1b_deploy.sh check      # 应该只剩 4 个开着的 API（不花钱，开发阶段还要用）
uv run python -m zj_spike.ledger
```

最后：在线程里告诉 zg 已经全部删除；把 `out/s1b/logs-*.jsonl` 和测试页导出的结果（zg 从 iPhone 发到 Mac 的话）用 send_message 告诉后端和 PM 在哪里，压缩包照第 5 步的做法交到 PM 线程。

**如果当天没测完**：也先 `down`。重测要再问 zg（D-017 只覆盖这一次）。
