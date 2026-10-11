# CI 的自建机器：zg 的 Mac 上 Docker 里的一个 Linux（x86_64）容器，里面跑 GitHub Actions runner。说明见 README.md。
# 尽量和 GitHub 自带的 ubuntu-24.04 一样：工作流里的 sudo apt-get、python3、sha256sum 照常能用。
# 多装的只有 PostgreSQL 17（db job 的 start_postgres.sh 用；容器里没有 Docker，services: 起不了）。
# 用 x86_64 而不是 arm64：bpy 5.2 没有 Linux arm64 的包；Apple 芯片上 Docker Desktop 用 Rosetta 跑。
FROM ubuntu:24.04

# runner 的版本和 linux-x64 包的 sha256，由 setup.sh 从 actions/runner 最新 release 的说明里读出来传进来
ARG RUNNER_VERSION
ARG RUNNER_SHA256

ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      ca-certificates curl git git-lfs sudo unzip zip xz-utils zstd gnupg lsb-release locales tzdata \
      python3 python3-venv build-essential postgresql-common \
 && sed -i 's/^#\?\s*create_main_cluster.*/create_main_cluster = false/' /etc/postgresql-common/createcluster.conf \
 && /usr/share/postgresql-common/pgdg/apt.postgresql.org.sh -y \
 && apt-get install -y --no-install-recommends postgresql-17 \
 && rm -rf /var/lib/apt/lists/*

# 容器里的 runner 用户可以 sudo（和 GitHub 自带机器一样）；容器不带 --privileged，这只是容器里的 root
RUN useradd -m -s /bin/bash runner \
 && echo 'runner ALL=(ALL) NOPASSWD:ALL' >/etc/sudoers.d/runner \
 && chmod 0440 /etc/sudoers.d/runner

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

USER runner
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
