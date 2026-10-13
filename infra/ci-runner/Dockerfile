# CI's self-hosted runner: a Linux (x86_64) container in Docker on zg's Mac, running the GitHub Actions runner. See README.md.
# CI のセルフホストランナー：zg の Mac 上の Docker 内にある Linux（x86_64）コンテナで、GitHub Actions runner を動かす。説明は README.md。
# Differences from GitHub's hosted ubuntu-24.04: jobs have no sudo. The system packages the workflows need are preinstalled here
# (env var ZOUJIN_CI_PREINSTALLED=1; workflows skip apt-get when they see it); to add a system package, change this file and
# rerun setup.sh on the Mac.
# GitHub 提供の ubuntu-24.04 との違い：ジョブに sudo がない。ワークフローが必要とするシステムパッケージはここにプリインストール済み
# （環境変数 ZOUJIN_CI_PREINSTALLED=1。ワークフローはこれを見ると apt-get を飛ばす）。システムパッケージを追加するときはこのファイルを変え、
# Mac で setup.sh を再実行する。
# The container starts as root; the entrypoint first blocks connections to the Mac itself and the LAN, then drops all
# privileges and switches to the runner user (entrypoint.sh).
# コンテナは root で起動し、エントリポイントがまず Mac 本体と LAN への接続を遮断してから、すべての権限を捨てて runner ユーザーに切り替える（entrypoint.sh）。
# x86_64 rather than arm64: bpy 5.2 has no Linux arm64 package; on Apple silicon Docker Desktop runs it with Rosetta.
# arm64 ではなく x86_64 を使う：bpy 5.2 には Linux arm64 のパッケージがない。Apple シリコンでは Docker Desktop が Rosetta で動かす。
FROM ubuntu:24.04

# The runner version and the linux-x64 package's sha256, read by setup.sh from the notes of the latest actions/runner release and passed in
# runner のバージョンと linux-x64 パッケージの sha256。setup.sh が actions/runner の最新 release の説明から読み取って渡す
ARG RUNNER_VERSION
ARG RUNNER_SHA256

ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    ZOUJIN_CI_PREINSTALLED=1

# Basic tools; iptables for the entrypoint to block connections; PostgreSQL 17 for the db job (start_postgres.sh)
# 基本ツール。iptables はエントリポイントが接続を遮断するため、PostgreSQL 17 は db ジョブ（start_postgres.sh）のため
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      ca-certificates curl git git-lfs unzip zip xz-utils zstd gnupg lsb-release locales tzdata iptables \
      python3 python3-venv build-essential postgresql-common \
 && sed -i 's/^#\?\s*create_main_cluster.*/create_main_cluster = false/' /etc/postgresql-common/createcluster.conf \
 && /usr/share/postgresql-common/pgdg/apt.postgresql.org.sh -y \
 && apt-get install -y --no-install-recommends postgresql-17 \
 && rm -rf /var/lib/apt/lists/*

# What the workflows used to install with sudo apt-get: the X11/GL libraries bpy links (assets.yml, web.yml),
# Playwright 1.63's Chromium dependencies and fonts (those `playwright install --with-deps chromium` installs on ubuntu24.04-x64)
# 以前ワークフローで sudo apt-get でインストールしていたもの：bpy がリンクする X11/GL ライブラリ（assets.yml、web.yml）、
# Playwright 1.63 の Chromium の依存とフォント（ubuntu24.04-x64 で `playwright install --with-deps chromium` が入れるもの）
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      libx11-6 libxext6 libxrender1 libxfixes3 libxi6 libxkbcommon0 libsm6 libgl1 \
      libasound2t64 libatk-bridge2.0-0t64 libatk1.0-0t64 libatspi2.0-0t64 libcairo2 libcups2t64 libdbus-1-3 \
      libdrm2 libgbm1 libglib2.0-0t64 libnspr4 libnss3 libpango-1.0-0 libxcb1 libxcomposite1 libxdamage1 \
      libxrandr2 \
      xvfb fonts-noto-color-emoji fonts-unifont libfontconfig1 libfreetype6 xfonts-cyrillic xfonts-scalable \
      fonts-liberation fonts-ipafont-gothic fonts-wqy-zenhei fonts-tlwg-loma-otf fonts-freefont-ttf \
 && rm -rf /var/lib/apt/lists/*

RUN useradd -m -s /bin/bash runner

WORKDIR /home/runner/actions-runner
RUN test -n "$RUNNER_VERSION" && test -n "$RUNNER_SHA256" \
 && curl -fsSL -o /tmp/runner.tgz \
      "https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz" \
 && echo "${RUNNER_SHA256}  /tmp/runner.tgz" | sha256sum -c - \
 && tar -xzf /tmp/runner.tgz \
 && rm /tmp/runner.tgz \
 && ./bin/installdependencies.sh \
 && rm -rf /var/lib/apt/lists/* \
 && chown -R runner:runner /home/runner

COPY --chmod=0755 entrypoint.sh job-done.sh /usr/local/bin/

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
