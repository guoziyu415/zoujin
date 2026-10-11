# CI 的自建机器：zg 的 Mac 上 Docker 里的一个 Linux（x86_64）容器，里面跑 GitHub Actions runner。说明见 README.md。
# 和 GitHub 自带的 ubuntu-24.04 不同的地方：job 里没有 sudo。工作流要的系统包都在这里预装好（环境变量
# ZOUJIN_CI_PREINSTALLED=1，工作流见到它就跳过 apt-get）；新加系统包改这个文件，再在 Mac 上重跑 setup.sh。
# 容器以 root 起，入口先封掉到 Mac 本机和局域网的连接，再丢掉全部权限换成 runner 用户（entrypoint.sh）。
# 用 x86_64 而不是 arm64：bpy 5.2 没有 Linux arm64 的包；Apple 芯片上 Docker Desktop 用 Rosetta 跑。
FROM ubuntu:24.04

# runner 的版本和 linux-x64 包的 sha256，由 setup.sh 从 actions/runner 最新 release 的说明里读出来传进来
ARG RUNNER_VERSION
ARG RUNNER_SHA256

ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    ZOUJIN_CI_PREINSTALLED=1

# 基本工具；iptables 给入口封连接用；PostgreSQL 17 给 db job（start_postgres.sh）
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      ca-certificates curl git git-lfs unzip zip xz-utils zstd gnupg lsb-release locales tzdata iptables \
      python3 python3-venv build-essential postgresql-common \
 && sed -i 's/^#\?\s*create_main_cluster.*/create_main_cluster = false/' /etc/postgresql-common/createcluster.conf \
 && /usr/share/postgresql-common/pgdg/apt.postgresql.org.sh -y \
 && apt-get install -y --no-install-recommends postgresql-17 \
 && rm -rf /var/lib/apt/lists/*

# 原来工作流里 sudo apt-get 装的：bpy 链接的 X11/GL 库（assets.yml、web.yml），
# Playwright 1.63 的 Chromium 依赖和字体（`playwright install --with-deps chromium` 在 ubuntu24.04-x64 上装的那些）
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
