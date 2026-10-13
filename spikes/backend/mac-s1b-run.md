# Handoff to "Check the computer's dev environment": S-1b voice proxy (one part locally on the Mac + one part on iPhone 4G) / 「パソコンの開発環境チェック」への引き継ぎ：S-1b 音声プロキシ（Mac ローカルで 1 段 + iPhone 4G で 1 段）

From: backend · 2026-10-06 · Basis: zg chose a temporary deployment (`pm/decisions.md` D-017, with three conditions: a random URL, no product name and no zg name on the URL or the page, and a one-time test code to enter); plan: `backend/spikes/s1b-plan.md`.

発信：バックエンド · 2026-10-06 · 根拠：zg が一時的なデプロイを選んだ（`pm/decisions.md` D-017。3 つの条件付き：URL はランダム、URL とページに製品名と zg の名前を出さない、使い捨てのテストコードの入力が必要）。計画：`backend/spikes/s1b-plan.md`。

Background: how long "release to hearing the answer" takes on phone 4G, barge-in, AirPods, the LINE in-app browser and quiet speech can only be tested on an iPhone. Backend wrote a voice proxy with only one character, メロス, and frontend wrote the test page. There are two parts: the first runs only locally on the Mac, with no deployment; the second is temporarily deployed to the 物語 (Monogatari) GCP project and deleted the same day after testing.

背景：スマホの 4G で「離してから回答が聞こえるまで」にかかる時間、割り込み、AirPods、LINE のアプリ内ブラウザ、小声での発話は、iPhone でしか測れない。バックエンドはメロス 1 人だけの音声プロキシを書き、フロントエンドはテストページを書いた。2 段に分ける：第 1 段は Mac のローカルだけで動かし、デプロイしない。第 2 段は 物語 (Monogatari) の GCP プロジェクトに一時的にデプロイし、テストした当日に削除する。

## Common rules / 共通のルール

- In every new shell, first run (same as `pm/handoffs/mac-spike-run.md`):
  新しいシェルでは毎回まず次を実行する（`pm/handoffs/mac-spike-run.md` と同じ）：
  ```bash
  cd ~/Developer/zoujin-spike && export CLOUDSDK_ACTIVE_CONFIG_NAME=zoujin && export ZJ_PROJECT="$(gcloud config get-value project 2>/dev/null)"
  ```
  Confirm that `ZJ_PROJECT` is not empty and is not the 日々の森 project before continuing.
  `ZJ_PROJECT` が空でなく、日々の森 のプロジェクトでもないことを確認してから続ける。
- **Addresses, test codes and project IDs never go into chat or any message.** They live only in `~/.zoujin-spike/` (readable only by zg). Do not `cat` these files, and do not paste the contents of `~/.zoujin-spike/s1b-deploy.log`; on errors, relay only the error line, with any URL removed first.
  **アドレス、テストコード、プロジェクト ID はチャットにもどんなメッセージにも入れない。** これらは `~/.zoujin-spike/` の中にだけある（zg だけが読める）。これらのファイルを `cat` せず、`~/.zoujin-spike/s1b-deploy.log` の内容も貼らない。エラーのときはエラーの 1 行だけを伝え、その中の URL は先に消す。
- Run only the commands in this note. Anything out of scope (creating other things, enabling other APIs, changing gcloud's default configuration, permanent `docker` settings) needs zg's approval first.
  この説明にあるコマンドだけを実行する。範囲外のこと（ほかのものを作る、ほかの API を有効にする、gcloud のデフォルト設定を変える、`docker` の恒久的な設定）はまず zg に聞く。
- If any step fails, stop and tell zg and backend (session cse_01Xq2jvETnKTfAxwLjVYfLcx) about the error; do not work around it yourself.
  どのステップでも失敗したら止まり、zg とバックエンド（session cse_01Xq2jvETnKTfAxwLjVYfLcx）にエラーを伝える。自分で回避しない。
- Write which step you are currently on in the status checklist.
  今どのステップをやっているかを状態チェックリストに書く。

## Switch to the new package (do it together with the casting and s4 re-runs) / 新しいパッケージへの入れ替え（casting と s4 の再実行と一緒に行う）

After zg downloads the new `zoujin-spike.zip`: extract it to a temporary directory, and copy only the code over into `~/Developer/zoujin-spike/`: `README.md`, `s1b-plan.md`, `s1b_deploy.sh`, `s1b/`, `pyproject.toml`, `uv.lock`, `zj_spike/`, `tests/`, and `page/` too if present. **Keep the existing `out/`.** Then:

zg が新しい `zoujin-spike.zip` をダウンロードしたら、一時ディレクトリに展開し、コードだけを `~/Developer/zoujin-spike/` に上書きする：`README.md`、`s1b-plan.md`、`s1b_deploy.sh`、`s1b/`、`pyproject.toml`、`uv.lock`、`zj_spike/`、`tests/`、`page/` があればそれも。**既存の `out/` は残す。** その後：

```bash
uv sync
# Offline self-check; all 43 should pass (packages from e1bcb3ca886f on)
# オフラインの自己チェック。43 項目すべて合格するはず（e1bcb3ca886f 以降のパッケージ）
uv run python -m unittest tests.test_offline tests.test_s1b
```

If `casting` and `s4_model_armor` have not been re-run yet, finish them first following the "addendum" in PM's handoff file.

`casting` と `s4_model_armor` をまだ再実行していなければ、PM の引き継ぎファイルの「補足」に従って先に済ませる。

## Part 1: local on the Mac (no deployment, can be done now) / 第 1 段：Mac ローカル（デプロイなし、今すぐできる）

1. Generate a test code: `uv run python -m zj_spike.s1b_proxy newcode`. The code is not shown on screen. Tell zg: the code is in `~/.zoujin-spike/s1b-code`, and they should `cat` it in the terminal themselves.
   テストコードを生成する：`uv run python -m zj_spike.s1b_proxy newcode`。コードは画面に表示されない。zg に「コードは `~/.zoujin-spike/s1b-code` にあるので、自分でターミナルで `cat` して見てほしい」と伝える。
2. Start the proxy in a separate terminal (keep it running):
   別のターミナルでプロキシを起動する（起動したままにする）：
   ```bash
   # Add this line when the package has page/ (frontend's test page); otherwise skip it
   # パッケージに page/（フロントエンドのテストページ）があるときはこの行を加える。なければ飛ばす
   export ZJ_S1B_STATIC="$PWD/page"
   uv run python -m zj_spike.s1b_proxy serve
   ```
3. In another terminal (also running the three opening lines first), run the smoke test, about 1 minute and about 0.02 USD:
   もう 1 つのターミナルで（同じく最初の 3 行を先に実行して）スモークテストを実行する。約 1 分、約 0.02 米ドル：
   ```bash
   uv run python -m zj_spike.s1b_proxy smoke
   ```
   Every item should be `[OK]`.
   すべての項目が `[OK]` になるはず。
4. If `page/` exists, ask zg to open `http://localhost:8080` in Safari on the Mac, enter the test code, say a few lines to メロス and try one barge-in. The page shows the timings.
   `page/` があれば、zg に Mac の Safari で `http://localhost:8080` を開いてもらい、テストコードを入力し、メロスと少し話して割り込みを 1 回試してもらう。ページに計測時間が表示される。
5. Stop the proxy (Ctrl+C). Use send_message to send the following numbers to backend and PM (cse_0181jxeb77TxjmVYVSyhqxon):
   プロキシを止める（Ctrl+C）。send_message で次の数字をバックエンドと PM（cse_0181jxeb77TxjmVYVSyhqxon）に送る：
   - `focusToReadyMs` from `out/s1b/smoke-*.json`, and each turn's `serverReleaseToFirstAudioMs` and `clientReleaseToFirstAudioMs`;
     `out/s1b/smoke-*.json` の `focusToReadyMs`、および各ターンの `serverReleaseToFirstAudioMs` と `clientReleaseToFirstAudioMs`；
   - the numbers on the `"event": "turn"` lines in `out/s1b/serve-*.jsonl` (the file contains only numbers, no speech content);
     `out/s1b/serve-*.jsonl` の `"event": "turn"` の行の数字（ファイルには数字だけで、話した内容は入っていない）；
   - one or two sentences on how it felt when zg tried it on the page.
     zg がページで試したときの感想を 1〜2 文。

## Part 2: iPhone 4G (D-017 agreed to this one run; wait until zg says "start the 4G test") / 第 2 段：iPhone 4G（D-017 で今回 1 回だけ同意済み。zg が「4G テスト開始」と言うまで待つ）

zg needs to be present, with an iPhone and earphones at hand, so wait until they say 「4G テスト開始」 / "start the 4G test" in the thread. Docker Desktop must be running (`docker info` returns). **First confirm that `page/index.html` exists** (frontend's test page, which comes with the new package); if it does not, do not start, and tell backend "the test page has not arrived yet". Before each step, say in one sentence in the thread what you are about to do, and report the result when done.

zg がその場にいて、iPhone とイヤホンを手元に用意する必要があるので、スレッドで「4G テスト開始」と言うまで待つ。Docker Desktop は起動しておく（`docker info` が返ってくること）。**まず `page/index.html` があることを確認する**（フロントエンドのテストページで、新しいパッケージに含まれている）。なければ始めず、バックエンドに「テストページがまだ届いていない」と伝える。各ステップの前にスレッドで何をするか一言で伝え、終わったら結果を伝える。

**Retest (on 10-07 all three attempts stopped at `up`, and all were `down`ed):** every retest needs zg's fresh consent (via PM). Use the latest package (`prepare` enables one more API and creates one more role, see `s1b-plan.md` v0.7). `down` deleted the test code, so first run `uv run python -m zj_spike.s1b_proxy newcode` (the test code is not shown), then start from `prepare`.

**再テスト（10-07 の 3 回はいずれも `up` で止まり、いずれも `down` 済み）：** 再テストのたびに zg の改めての同意が必要（PM 経由）。最新のパッケージを使う（`prepare` で API が 1 つ、ロールが 1 つ増える、`s1b-plan.md` v0.7 を参照）。`down` でテストコードが削除されたので、まず `uv run python -m zj_spike.s1b_proxy newcode`（テストコードは表示されない）を実行し、`prepare` からやり直す。

```bash
# Read-only: what exists right now / 読み取りのみ：今何があるか
./s1b_deploy.sh check
# Enable 4 APIs (Cloud Run, Artifact Registry, IAM, IAM Service Account Credentials), create the image repository
# and a service account that can only call Gemini
# 4 つの API（Cloud Run、Artifact Registry、IAM、IAM Service Account Credentials）を有効にし、
# イメージリポジトリと Gemini だけを呼べるサービスアカウントを作る
./s1b_deploy.sh prepare
# On the Mac, connect to Live once as the service account (no speech, no cost), waiting up to 7 minutes;
# up is allowed only after this connects
# Mac 上でサービスアカウントとして Live に 1 回接続する（話さず、費用なし）。最大 7 分待つ。接続できてはじめて up できる
./s1b_deploy.sh sacheck
# Build the image on the Mac, first check it once offline as the service user, push only if it passes
# Mac 上でイメージをビルドし、まずネットワークを切ってサービスユーザーとして 1 回チェックし、通った場合だけプッシュする
ZJ_S1B_PAGE="$PWD/page" ./s1b_deploy.sh build
# Create a private service (only zg's Google identity can access it), then smoke-test: everything must be [OK]
# 非公開のサービスを作り（zg の Google アカウントだけがアクセスできる）、スモークテスト：すべて [OK] でなければならない
./s1b_deploy.sh up
# Open public access, then check once more that anonymous access is rejected
# 公開アクセスを開き、匿名アクセスが拒否されることをもう一度確認する
./s1b_deploy.sh open
```

- Before pushing, `build` runs the image once locally with the network cut off (as the same non-root user as on Cloud Run); the screen should show "0 unreadable", "/health → 200, / → 200 (frontend test page)" and "image check passed". The image is amd64, so on Apple silicon it runs under emulation and may take a dozen or so seconds longer. If it does not pass, stop; the image will not be pushed; forward those lines on screen to backend (they contain only paths inside the container, no addresses or project IDs), then run `./s1b_deploy.sh down`.
  `build` はプッシュの前にローカルでネットワークを切ってイメージを 1 回動かす（Cloud Run と同じ非 root ユーザーとして）。画面には「読めないもの 0 個」「/health → 200、/ → 200（フロントエンドのテストページ）」「イメージのチェック合格」と出るはず。イメージは amd64 なので、Apple シリコンではエミュレーションで動き、十数秒遅くなることがある。通らなければ止まる。イメージはプッシュされない。画面のその数行をバックエンドに転送し（コンテナ内のパスだけで、アドレスやプロジェクト ID は含まない）、`./s1b_deploy.sh down` を実行する。
- `sacheck` tries every 20 seconds and prints one line per failure (project ID, address and account already removed); a new service account's permissions can take a few minutes to take effect, so `[NG]` on the first few tries is normal. If it still cannot connect after 7 minutes, stop, forward those lines to backend, then `down`.
  `sacheck` は 20 秒ごとに試し、失敗のたびに画面に 1 行出す（プロジェクト ID、アドレス、アカウントは削除済み）。新しいサービスアカウントの権限が有効になるまで数分かかることがあるので、最初の数回の `[NG]` は正常。7 分経ってもつながらなければ止まり、その数行をバックエンドに転送してから `down` する。
- When `up`'s smoke test fails, the script first shows the most recent session errors from the service logs (project ID, address and account already removed), then stops; forward those lines to backend, then `down`.
  `up` のスモークテストが通らないとき、スクリプトはまずサービスのログにある直近のセッションのエラーを表示し（プロジェクト ID、アドレス、アカウントは削除済み）、それから止まる。その数行をバックエンドに転送し、`down` する。
- The URL checks in `up`, `open` and `down` poll every 10 seconds, waiting for Google's side to take effect (up to 80 seconds, 3 minutes and 2 minutes respectively); no output in between is normal. If `up`'s smoke test fails only on the voice items while all access-protection items pass, the script explains why, waits 2 minutes and runs the whole set again; only a second failure counts as a failure.
  `up`、`open`、`down` の URL チェックは 10 秒ごとに問い合わせ、Google 側で反映されるのを待つ（それぞれ最大 80 秒、3 分、2 分）。その間に出力がないのは正常。`up` のスモークテストで音声の項目だけが通らず、アクセス保護はすべて通った場合、スクリプトは理由を説明し、2 分待ってから全体をもう一度実行する。2 回目も通らなかった場合だけ失敗とする。
- `up` puts the hash of the test code into the service. The service name is random (`s-` plus 8 characters), and the URL contains no product name.
  `up` はテストコードのハッシュをサービスに入れる。サービス名はランダム（`s-` に 8 文字）で、URL に製品名は入らない。
- If any item of `up`'s smoke test is not `[OK]`: do not run `open`; run `./s1b_deploy.sh down` directly and tell backend.
  `up` のスモークテストで 1 つでも `[OK]` でない項目があれば、`open` は実行せず、そのまま `./s1b_deploy.sh down` を実行してバックエンドに伝える。
- After `open`, the script prompts zg to do two things themselves: send the address to the iPhone with `pbcopy` and Universal Clipboard, and `cat` the test code. **zg does these two things; you do not run them.**
  `open` の後、スクリプトは zg に自分で 2 つのことをするよう促す：`pbcopy` とユニバーサルクリップボードでアドレスを iPhone に送ること、`cat` でテストコードを見ること。**この 2 つは zg 自身が行い、あなたは実行しない。**
- zg tests 8 items on the iPhone following section 5 of `s1b-plan.md`, about 40 minutes. You do not need to do anything in the meantime.
  zg は `s1b-plan.md` の第 5 節に従って iPhone で 8 項目をテストする。約 40 分。その間あなたは何もしなくてよい。

**After zg says testing is done, the same day / zg がテスト終了と言ったら、当日中に：**

```bash
# Pull the timing numbers back into out/s1b/logs-*.jsonl (timestamps and numbers only, no project ID or address)
# 計測値を out/s1b/logs-*.jsonl に取り込む（タイムスタンプと数字だけで、プロジェクト ID とアドレスは含まない）
./s1b_deploy.sh logs
# Delete the service, image repository and service account, confirm the old address returns 404,
# and delete the local test code and address files
# サービス、イメージリポジトリ、サービスアカウントを削除し、元のアドレスが 404 を返すことを確認し、
# ローカルのテストコードとアドレスのファイルを削除する
./s1b_deploy.sh down
# Only the 4 enabled APIs should remain (no cost, still needed during development)
# 有効な API 4 つだけが残っているはず（費用はかからず、開発中はまだ使う）
./s1b_deploy.sh check
uv run python -m zj_spike.ledger
```

Finally: tell zg in the thread that everything has been deleted; use send_message to tell backend and PM where `out/s1b/logs-*.jsonl` and the results exported from the test page (if zg sent them from the iPhone to the Mac) are, and hand the zip to the PM thread the same way as in step 5.

最後に：スレッドで zg にすべて削除したことを伝える。`out/s1b/logs-*.jsonl` とテストページから書き出した結果（zg が iPhone から Mac に送った場合）がどこにあるかを send_message でバックエンドと PM に伝え、圧縮ファイルは第 5 ステップと同じやり方で PM のスレッドに渡す。

**If testing is not finished the same day**: still `down` first. A retest needs zg's consent again (D-017 covers only this one run).

**当日中にテストが終わらなかった場合**：それでもまず `down` する。再テストには zg に改めて聞く必要がある（D-017 は今回 1 回だけが対象）。
