# CI 的自建机器（zg 的 Mac）

从 2026-10-11 起，仓库的 GitHub Actions 不在 GitHub 自带的机器上跑：免费分钟用完，花费上限是 $0。所有 job 改在
zg 的 Mac 上跑，自建机器不花钱、不占分钟。工作流里写的是
`runs-on: ${{ fromJSON(vars.CI_RUNS_ON || '["self-hosted","zoujin-mac"]') }}`。

## 怎么隔离

runner 不直接装在 Mac 上，而是跑在 Docker 里的一个 Linux 容器里（`Dockerfile`，x86_64，Apple 芯片上走 Rosetta）。
每个 PR 分支的代码都会在这里跑，所以：

- 容器不挂 Mac 的任何文件夹，不给 Docker 的 socket，不加 `--privileged`（只加 `NET_ADMIN`，见下）：钥匙串、gcloud 配置、`~/.zoujin`
  账本、`~/Developer` 下的检出它都碰不到。
- 不给任何 Key 的环境变量；CI 照旧只用假模型和回放。
- 只注册在这个仓库，标签 `zoujin-mac`，只有这个仓库的工作流能用它。
- 每个 job 跑完清掉工作目录和临时目录（`job-done.sh`）。
- 只出公网：容器以 root 起，入口（`entrypoint.sh`）用 iptables 拒绝到 Mac 本机（`host.docker.internal`）、
  Docker 的虚拟机和局域网的一切连接，只留 Docker 的 DNS。所以 Mac 上开着的本地服务（5432 的开发库、8001/8787、
  Blender MCP 这类能执行代码的端口）job 都连不到。规则没装上就不起 runner。
- job 没有任何特权：入口装完规则后换成 runner 用户，丢掉全部能力（包括改规则要的 NET_ADMIN），并禁止再提权；
  镜像里没有 sudo。工作流要的系统包预装在 `Dockerfile` 里（环境变量 `ZOUJIN_CI_PREINSTALLED=1`，工作流见到它
  就跳过 `apt-get`）。新加系统包：改 `Dockerfile`，合并后在 Mac 上重跑 `setup.sh`。
- 容器里没有 Docker，所以工作流不能用 `services:`；db job 用 `.github/scripts/start_postgres.sh` 在 job 里起
  PostgreSQL 17，只监听容器自己的 127.0.0.1，和 Mac 上 5432 端口的开发库互不相干。

## 装和更新

在 Mac 上，Docker Desktop 开着、gh 已登录（仓库管理员）：

```bash
bash infra/ci-runner/setup.sh
```

它读 actions/runner 最新版本和校验和、构建镜像、第一次时用现取的注册令牌注册（令牌不打印、不落盘）、启动容器
`zoujin-ci-runner`（`--restart unless-stopped`，Docker Desktop 开机自启时它也起来）。重复跑会重建镜像、换掉容器，
不重复注册。runner 自己会自动更新，更新留在命名卷 `zoujin-ci-runner` 里。

Mac 合盖、睡眠或 Docker 没开时 job 排队，机器回来接着跑。

## 常用

- 看状态：`docker logs --tail 20 zoujin-ci-runner`；GitHub 上：仓库 Settings → Actions → Runners。
- 停：`docker stop zoujin-ci-runner`；再开：`docker start zoujin-ci-runner`。
- 彻底拆掉：GitHub 上删掉这台 runner，再 `docker rm -f zoujin-ci-runner && docker volume rm zoujin-ci-runner`。
- 换回 GitHub 自带的机器（比如分钟恢复以后）：仓库的 Actions 变量 `CI_RUNS_ON` 设成 `"ubuntu-24.04"`
  （带引号，是 JSON）。工作流不用改；db job 会在那边从 PostgreSQL 官方源装 17。
