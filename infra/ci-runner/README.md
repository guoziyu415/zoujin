# Self-hosted CI machine (zg's Mac) / CI 用セルフホストマシン（zg の Mac）

From 2026-10-11, the repository's GitHub Actions no longer run on GitHub's own machines: the free minutes are used up and the spending limit is $0. All jobs run on zg's Mac instead; self-hosted machines cost nothing and use no minutes. The workflows say
`runs-on: ${{ fromJSON(vars.CI_RUNS_ON || '["self-hosted","zoujin-mac"]') }}`.

2026-10-11 から、リポジトリの GitHub Actions は GitHub 標準のマシンでは実行しない。無料枠の分数を使い切り、支出上限が $0 のため。すべての job を zg の Mac で実行する。セルフホストのマシンは無料で、分数も消費しない。ワークフローには
`runs-on: ${{ fromJSON(vars.CI_RUNS_ON || '["self-hosted","zoujin-mac"]') }}` と書かれている。

## How it is isolated / 分離の方法

The runner is not installed directly on the Mac; it runs in a Linux container inside Docker (`Dockerfile`, x86_64, via Rosetta on Apple silicon). Code from every PR branch runs here, so:

runner は Mac に直接インストールせず、Docker 内の Linux コンテナで動かす（`Dockerfile`、x86_64、Apple シリコンでは Rosetta 経由）。すべての PR ブランチのコードがここで実行されるため：

- The container mounts no folder from the Mac, is given no Docker socket, and gets no `--privileged` (only `NET_ADMIN` is added, see below): it cannot reach the keychain, gcloud config, the `~/.zoujin` ledger, or the checkouts under `~/Developer`.
  コンテナは Mac のフォルダを一切マウントせず、Docker のソケットも渡さず、`--privileged` も付けない（`NET_ADMIN` だけ追加。下記参照）。キーチェーン、gcloud の設定、`~/.zoujin` の台帳、`~/Developer` 以下のチェックアウトには触れられない。
- No environment variable holding a key is given; CI still uses only fake models and replays.
  鍵を含む環境変数は一切渡さない。CI はこれまでどおり偽モデルとリプレイだけを使う。
- It is registered only on this repository, with the label `zoujin-mac`, and only this repository's workflows can use it.
  このリポジトリにだけ登録し、ラベルは `zoujin-mac`。このリポジトリのワークフローだけが使える。
- After each job, the working directory and temp directories are cleaned (`job-done.sh`).
  各 job の終了後に作業ディレクトリと一時ディレクトリを削除する（`job-done.sh`）。
- Public internet only: the container starts as root, and the entrypoint (`entrypoint.sh`) uses iptables to reject all connections to the Mac itself (`host.docker.internal`), Docker's virtual machine and the LAN, leaving only Docker's DNS. So local services running on the Mac (the development database on 5432, 8001/8787, and ports that can execute code such as Blender MCP) are unreachable from jobs. If the rules are not installed, the runner does not start.
  外向きは公衆インターネットのみ：コンテナは root で起動し、エントリポイント（`entrypoint.sh`）が iptables で Mac 本体（`host.docker.internal`）、Docker の仮想マシン、LAN へのあらゆる接続を拒否し、Docker の DNS だけを残す。そのため Mac で動いているローカルサービス（5432 の開発用データベース、8001/8787、Blender MCP のようなコードを実行できるポート）には job から接続できない。ルールが入らなかった場合は runner を起動しない。
- Jobs have no privileges: after installing the rules, the entrypoint switches to the runner user, drops all capabilities (including the NET_ADMIN needed to change the rules) and forbids further privilege escalation; there is no sudo in the image. System packages the workflows need are preinstalled in the `Dockerfile` (environment variable `ZOUJIN_CI_PREINSTALLED=1`; the workflows skip `apt-get` when they see it). To add a system package: change the `Dockerfile`, and after merging rerun `setup.sh` on the Mac.
  job には特権がない：エントリポイントはルールを入れた後 runner ユーザーに切り替え、すべての capability（ルールを変更するのに必要な NET_ADMIN を含む）を捨て、再度の権限昇格を禁止する。イメージに sudo はない。ワークフローが必要とするシステムパッケージは `Dockerfile` に事前インストールしてある（環境変数 `ZOUJIN_CI_PREINSTALLED=1`。ワークフローはこれを見たら `apt-get` を省略する）。システムパッケージを追加するには `Dockerfile` を変更し、マージ後に Mac で `setup.sh` を再実行する。
- There is no Docker inside the container, so workflows cannot use `services:`; the db job starts PostgreSQL 17 inside the job with `.github/scripts/start_postgres.sh`, listening only on the container's own 127.0.0.1, unrelated to the development database on port 5432 of the Mac.
  コンテナ内には Docker がないので、ワークフローは `services:` を使えない。db job は `.github/scripts/start_postgres.sh` で job 内に PostgreSQL 17 を起動し、コンテナ自身の 127.0.0.1 だけで待ち受ける。Mac の 5432 番ポートの開発用データベースとは無関係。

## Install and update / インストールと更新

On the Mac, with Docker Desktop open and gh logged in (as a repository admin):

Mac で、Docker Desktop を起動し、gh にログインした状態（リポジトリ管理者）で：

```bash
bash infra/ci-runner/setup.sh
```

It reads the latest actions/runner version and checksum, builds the image, on the first run registers using a freshly fetched registration token (the token is neither printed nor written to disk), and starts the container `zoujin-ci-runner` (`--restart unless-stopped`, so it also starts when Docker Desktop starts at boot). Running it again rebuilds the image and replaces the container without registering again. The runner updates itself automatically, and updates stay in the named volume `zoujin-ci-runner`.

最新の actions/runner のバージョンとチェックサムを読み、イメージをビルドし、初回はその場で取得した登録トークンで登録し（トークンは表示もディスクへの書き込みもしない）、コンテナ `zoujin-ci-runner` を起動する（`--restart unless-stopped`。Docker Desktop が起動時に自動起動すれば、このコンテナも起動する）。再実行するとイメージを再ビルドしてコンテナを入れ替えるが、再登録はしない。runner は自動で更新され、更新は名前付きボリューム `zoujin-ci-runner` に残る。

When the Mac's lid is closed, it is asleep, or Docker is not running, jobs queue and resume when the machine is back.

Mac の蓋を閉じている、スリープ中、または Docker が起動していないときは job が待機し、マシンが戻ると再開する。

## Private art inputs / 非公開のアート入力

Web browser acceptance needs the actual character files and crowd animations. Model sources and generated outputs do not go into Git; inside each isolated runner's container, place separately
`/home/runner/ci-assets/cast/<character>/{walk,talk_std,talk_high,anims}.glb` and
`/home/runner/ci-assets/UAL1_Standard.glb`. This is a directory containing only art resources; it does not copy credentials, ledgers or the host working directory, and adds no host mounts. Other runners can point to an equivalent private resource directory through the repository variable `CI_ASSET_SOURCE_ROOT`.

Web ブラウザでの受け入れには、実際の人物ファイルと群衆のアニメーションが必要。モデルのソースと生成物は Git に入れない。隔離された各 runner のコンテナ内に、別途
`/home/runner/ci-assets/cast/<人物>/{walk,talk_std,talk_high,anims}.glb` と
`/home/runner/ci-assets/UAL1_Standard.glb` を置く。これはアート資源だけを含むディレクトリで、認証情報、台帳、ホストの作業ディレクトリはコピーせず、ホストのマウントも追加しない。他の runner はリポジトリ変数 `CI_ASSET_SOURCE_ROOT` で同等の非公開リソースディレクトリを指定できる。

After the first setup or after character assets are updated, copy the character resources from the locally reviewed `assets/cast/build`, and copy the UAL file whose SHA-256 is pinned by `assets/pipeline/crowd/build.sh` into the directories above. Each time, `web.yml` first uses `.github/scripts/stage_web_assets.mjs` to verify the byte sizes and the committed-manifest SHA-256 of all four tiers of every character's files, and the source hash of the UAL, and then writes them into a clean job temp directory. If any is missing or mismatched it fails; acceptance cannot pass with placeholder models or by filtering out 404s. Character quality and rebuilding remain the responsibility of the cast pipeline; this step verifies that the browser uses the reviewed artifacts, and does not claim that CI rebuilt the character sources. The crowd pack uses this UAL source to generate animations in CI, and its cache key is kept separate from that of the earlier pack without animations.

初回設定後、または人物アセットの更新後に、ローカルで審査済みの `assets/cast/build` から人物リソースをコピーし、`assets/pipeline/crowd/build.sh` が SHA-256 を固定している UAL ファイルを上記のディレクトリにコピーする。`web.yml` は毎回まず `.github/scripts/stage_web_assets.mjs` で、全人物の 4 段階のファイルのバイト数とコミット済みマニフェストの SHA-256、および UAL のソースハッシュを検証し、それからクリーンな job 一時ディレクトリに書き込む。一つでも欠けているか不一致なら失敗し、プレースホルダーモデルや 404 のフィルタリングで受け入れを通すことはできない。キャラクターの品質と再構築は引き続き cast パイプラインの責任であり、この手順は、ブラウザが使うのが審査済みの成果物であることを検証するもので、CI で人物のソースファイルを再構築したとは主張しない。群衆パックはこの UAL ソースを使って CI でアニメーションを生成し、キャッシュキーはアニメーションのなかった以前のパックとは分けてある。

The container keeps this directory across restarts, but it must be reconfigured after `setup.sh` rebuilds the container; it is not in the named volume that stores the registration information. It is also needed when a new runner is added. When switching to a GitHub-hosted runner, equivalent private inputs must be provided first; changing only `CI_RUNS_ON` does not skip this condition.

コンテナを再起動してもこのディレクトリは保持されるが、`setup.sh` がコンテナを再構築した後は再設定が必要。登録情報を保存する名前付きボリュームには入っていないため。新しい runner を追加するときも設定が必要。GitHub ホストの runner に切り替える場合は、先に同等の非公開入力を用意する必要があり、`CI_RUNS_ON` を変えるだけでこの条件を飛ばすことはできない。

## Common tasks / よく使う操作

- Check status: `docker logs --tail 20 zoujin-ci-runner`; on GitHub: repository Settings → Actions → Runners.
  状態の確認：`docker logs --tail 20 zoujin-ci-runner`。GitHub 上では：リポジトリの Settings → Actions → Runners。
- Stop: `docker stop zoujin-ci-runner`; start again: `docker start zoujin-ci-runner`.
  停止：`docker stop zoujin-ci-runner`。再開：`docker start zoujin-ci-runner`。
- Remove completely: delete this runner on GitHub, then `docker rm -f zoujin-ci-runner && docker volume rm zoujin-ci-runner`.
  完全に撤去：GitHub 上でこの runner を削除し、その後 `docker rm -f zoujin-ci-runner && docker volume rm zoujin-ci-runner`。
- Switch back to GitHub's own machines (e.g. once the minutes are restored): set the repository's Actions variable `CI_RUNS_ON` to `"ubuntu-24.04"` (with quotes; it is JSON). The workflows need no change; the db job installs 17 there from the official PostgreSQL source.
  GitHub 標準のマシンに戻す（例：分数が回復した後）：リポジトリの Actions 変数 `CI_RUNS_ON` を `"ubuntu-24.04"` に設定する（引用符付き。JSON である）。ワークフローは変更不要。db job は向こうでは PostgreSQL 公式のソースから 17 をインストールする。
