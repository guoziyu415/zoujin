#!/usr/bin/env bash
# 第一版的部署（B-23）：网关和叙事者两个 Cloud Run 服务、一个 Cloud SQL、邀请制。只在 zg 的 Mac 上跑，说明见 README.md。
#
#   infra/deploy/deploy.sh all          第 27 步：setup → build → migrate → up → promote，一条跑完（可以重跑，做过的跳过）
#   infra/deploy/deploy.sh check        只读：现在有什么
#   infra/deploy/deploy.sh setup        开 API，建镜像仓库、两个服务账号、数据库、密钥（已有的跳过）
#   infra/deploy/deploy.sh build        取 origin/main（ZJ_DEPLOY_REF 换），构建前端和镜像，推到镜像仓库
#   infra/deploy/deploy.sh migrate      经 Cloud SQL 代理跑迁移，再设两个应用账号的权限
#   infra/deploy/deploy.sh up           新版本上线但不接流量（第一次：私有服务），对候选地址跑冒烟
#   infra/deploy/deploy.sh promote      切流量（维持现有 IAM 私密设置），再冒烟一次、查匿名被拒
#   infra/deploy/deploy.sh verify       只查匿名被拒
#   infra/deploy/deploy.sh invite [N]   生成 N 个邀请码（默认 1），写进私有目录的文件，不打印
#   infra/deploy/deploy.sh rollback     两个服务的流量切回上一个版本
#   infra/deploy/deploy.sh pause|resume 停 / 开数据库（不玩的时候省钱；服务本来就缩到 0）
#
# 只用 gcloud 的 zoujin 配置里的项目；项目 ID、地址、密码、邀请码只在 ~/.zoujin/deploy/（权限 700）和 Secret Manager 里，
# 不打印到屏幕上。gcloud、docker 的输出写进 ~/.zoujin/deploy/deploy.log（里面可能有地址，不要贴到聊天里）。
set -euo pipefail
umask 077

export CLOUDSDK_ACTIVE_CONFIG_NAME=zoujin
REGION=asia-northeast1
AR_REPO=images
SA_GW=zj-gateway
SA_NR=zj-narrator
SEC_OWNER=zj-db-owner
SEC_GW=zj-db-gw
SEC_NR=zj-db-nr
SEC_CLAUDE=zj-claude
SEC_SITE=zj-site-password
KEYCHAIN_CLAUDE=zoujin-claude
DB=zoujin
TAG=next
PNPM="npx -y pnpm@10.28.0"
SQLPROXY_IMAGE="${ZJ_SQLPROXY_IMAGE:-gcr.io/cloud-sql-connectors/cloud-sql-proxy:2.14.1}"
PROXY_PORT="${ZJ_PROXY_PORT:-5433}"
STATE="${ZJ_DEPLOY_DIR:-$HOME/.zoujin/deploy}"
CONFIG="$STATE/config.env"
STATE_ENV="$STATE/state.env"
LOG="$STATE/deploy.log"
WT="$STATE/wt"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
APIS=(run.googleapis.com sqladmin.googleapis.com artifactregistry.googleapis.com secretmanager.googleapis.com
  iam.googleapis.com aiplatform.googleapis.com modelarmor.googleapis.com)
SA_ROLES=(roles/cloudsql.client roles/aiplatform.user roles/modelarmor.user)

die() { echo "[停止] $*" >&2; exit 1; }
say() { echo "== $*"; }

# 命令的输出只进日志；日志里只记命令的前 4 段（后面可能有密码）
run() {
  echo "  → $1 $2 $3 …" >&2
  echo "### $(date '+%F %T') ${*:1:4} …" >>"$LOG"
  "$@" >>"$LOG" 2>&1 || die "上一条命令失败，详细在 $LOG（里面可能有地址，不要贴到聊天里，只转述错误那一行）"
}

save() { # save KEY VALUE：写进 state.env（覆盖同名的行）
  touch "$STATE_ENV"
  grep -v "^$1=" "$STATE_ENV" >"$STATE_ENV.tmp" || true
  printf '%s=%q\n' "$1" "$2" >>"$STATE_ENV.tmp"
  mv "$STATE_ENV.tmp" "$STATE_ENV"
  printf -v "$1" '%s' "$2"
}

rand_hex() { openssl rand -hex "$1"; }

guard() {
  mkdir -p "$STATE" && chmod 700 "$STATE"
  touch "$LOG"
  gcloud config configurations describe zoujin >/dev/null 2>&1 || die "没有 gcloud 的 zoujin 配置"
  P="$(gcloud config get-value project 2>/dev/null)"
  [[ -n "$P" ]] || die "gcloud 的 zoujin 配置里没设项目"
  case "$P" in *perfectbody*) die "zoujin 配置指到了别的项目，停下" ;; esac
  PA=(--project="$P")
  if [[ ! -f "$CONFIG" ]]; then
    cat >"$CONFIG" <<'EOF'
# deploy.sh 的设置（只在这台 Mac 上）。模型 ID 和单价上限不进仓库。
# Claude 的两档模型 ID：没写就用终端里 export 的 ZJ_CLAUDE_HAIKU / ZJ_CLAUDE_SONNET
ZJ_CLAUDE_HAIKU=
ZJ_CLAUDE_SONNET=
# 每个实例的花费上限（美元，账本在实例的 /tmp，实例重启归零；最多 3 个实例）
ZJ_MAX_CLAUDE_USD=10
ZJ_MAX_GOOGLE_USD=10
ZJ_VERTEX_LOCATION=global
ZJ_ARMOR_TEMPLATE=zoujin-safety-v1
EOF
    echo "写了设置文件 $CONFIG（默认值）"
  fi
  local haiku="${ZJ_CLAUDE_HAIKU:-}" sonnet="${ZJ_CLAUDE_SONNET:-}"
  # shellcheck disable=SC1090
  source "$CONFIG"
  ZJ_CLAUDE_HAIKU="${ZJ_CLAUDE_HAIKU:-$haiku}"
  ZJ_CLAUDE_SONNET="${ZJ_CLAUDE_SONNET:-$sonnet}"
  # export 进来的模型 ID 记进设置文件，以后单独跑 up 不用再 export
  local k v
  for k in ZJ_CLAUDE_HAIKU ZJ_CLAUDE_SONNET; do
    v="${!k}"
    if [[ -n "$v" ]] && grep -qx "$k=" "$CONFIG"; then
      awk -v k="$k" -v v="$v" '$0 == k "=" { print k "=" v; next } { print }' "$CONFIG" >"$CONFIG.tmp" &&
        mv "$CONFIG.tmp" "$CONFIG"
      echo "把 $k 记进了 $CONFIG"
    fi
  done
  # shellcheck disable=SC1090
  [[ -f "$STATE_ENV" ]] && source "$STATE_ENV"
  GW="${GW:-}" NR="${NR:-}" SQL="${SQL:-}" IMAGE="${IMAGE:-}" OPENED="${OPENED:-}"
  SA_GW_EMAIL="$SA_GW@$P.iam.gserviceaccount.com"
  SA_NR_EMAIL="$SA_NR@$P.iam.gserviceaccount.com"
  # 服务名、实例名第一次随机生成，网址里没有产品名或人名
  [[ -n "$GW" ]] || save GW "s-$(rand_hex 4)"
  [[ -n "$NR" ]] || save NR "s-$(rand_hex 4)"
  [[ -n "$SQL" ]] || save SQL "db-$(rand_hex 3)"
}

has_api() { gcloud services list --enabled "${PA[@]}" --format='value(config.name)' 2>/dev/null | grep -qx "$1"; }
has_repo() { gcloud artifacts repositories describe "$AR_REPO" --location="$REGION" "${PA[@]}" >/dev/null 2>&1; }
has_sa() { gcloud iam service-accounts describe "$1" "${PA[@]}" >/dev/null 2>&1; }
has_sql() { gcloud sql instances describe "$SQL" "${PA[@]}" >/dev/null 2>&1; }
# 有能接流量的版本才能 --no-traffic；第一次上线失败留下的空服务按第一次处理（还是私有的）
has_ready() { [[ -n "$(gcloud run services describe "$1" --region="$REGION" "${PA[@]}" \
  --format='value(status.latestReadyRevisionName)' 2>/dev/null)" ]]; }
has_secret() { gcloud secrets describe "$1" "${PA[@]}" >/dev/null 2>&1; }
has_service() { gcloud run services describe "$1" --region="$REGION" "${PA[@]}" >/dev/null 2>&1; }
gateway_access() {
  # 只有成功的 list 空结果才代表尚未创建；权限/网络/JSON 错误绝不能被解释成“私有”。
  local services mode policy members
  services="$(gcloud run services list --region="$REGION" "${PA[@]}" --filter="metadata.name=$GW" --format=json 2>/dev/null)" ||
    die "无法读取网关服务访问配置，禁止继续"
  mode="$(python3 -c 'import json,sys
p=json.load(sys.stdin)
if not isinstance(p,list) or len(p)>1: raise ValueError("invalid service list")
if not p: print("missing")
else:
 s=p[0]; metadata=s.get("metadata",{})
 if not isinstance(metadata,dict) or not metadata.get("name"): raise ValueError("missing service identity")
 value=metadata.get("annotations",{}).get("run.googleapis.com/invoker-iam-disabled",s.get("invokerIamDisabled",False))
 if str(value).lower() not in ("true","false"): raise ValueError("invalid invoker state")
 print("public" if str(value).lower()=="true" else "check")' <<<"$services")" ||
    die "网关服务访问配置无法解析，禁止继续"
  if [[ "$mode" == missing ]]; then printf '%s\n' missing; return; fi
  policy="$(gcloud run services get-iam-policy "$GW" --region="$REGION" "${PA[@]}" --format=json 2>/dev/null)" ||
    die "无法读取网关 IAM 权限，禁止继续"
  members="$(python3 -c 'import json,sys
p=json.load(sys.stdin)
if not isinstance(p,dict) or not isinstance(p.get("bindings",[]),list): raise ValueError("invalid IAM policy")
for b in p.get("bindings",[]):
 if not isinstance(b,dict) or not isinstance(b.get("members",[]),list): raise ValueError("invalid IAM binding")
print("public" if any(b.get("role")=="roles/run.invoker" and {"allUsers","allAuthenticatedUsers"}.intersection(b.get("members",[])) for b in p.get("bindings",[])) else "private")' <<<"$policy")" ||
    die "网关 IAM 权限无法解析，禁止继续"
  if [[ "$mode" == public || "$members" == public ]]; then printf '%s\n' public; else printf '%s\n' private; fi
}
privacy_check() {
  GW_ACCESS="$(gateway_access)" || die "网关访问状态未知，禁止继续"
  if [[ "$GW_ACCESS" == missing && "${1:-}" != allow-missing ]]; then
    die "网关服务尚不存在，禁止冒烟或切流量"
  fi
  if [[ -f "$STATE/privacy-lock.json" && "$GW_ACCESS" == public ]]; then
    # User-authorized reviewer access is restricted to one tested release, not an OPENED flag.
    [[ -f "$STATE/reviewer-access.json" ]] &&
      gcloud run services describe "$GW" --region="$REGION" "${PA[@]}" --format=json 2>/dev/null |
      python3 -I "$HERE/reviewer_access.py" "$STATE/reviewer-access.json" "$GW" ||
      die "隐私锁存在，且未匹配已验密码的评审版本：先收紧访问，禁止自动继续"
  fi
}
gateway_bearer() {
  privacy_check
  if [[ "$GW_ACCESS" == private ]]; then
    local token
    token="$(gcloud auth print-identity-token 2>/dev/null)" || die "无法取得私有网关身份令牌"
    [[ -n "$token" ]] || die "私有网关身份令牌为空"
    printf '%s' "$token"
  fi
}

secret() { gcloud secrets versions access latest --secret="$1" "${PA[@]}"; }
conn() { gcloud sql instances describe "$SQL" "${PA[@]}" --format='value(connectionName)'; }
url_of() { gcloud run services describe "$1" --region="$REGION" "${PA[@]}" --format='value(status.url)'; }
tag_url() { gcloud run services describe "$1" --region="$REGION" "${PA[@]}" --format=json |
  python3 -c "import json,sys; print(next((t['url'] for t in json.load(sys.stdin)['status'].get('traffic',[]) if t.get('tag')=='$TAG'),''))"; }
yn() { if "$@"; then echo 有; else echo 没有; fi; }

new_secret() { # new_secret NAME（值从标准输入读）
  run gcloud secrets create "$1" --replication-policy=automatic --data-file=- "${PA[@]}"
}

# —— Cloud SQL 代理（docker 里跑，用 zg 的应用默认凭证），本机 127.0.0.1:$PROXY_PORT ——
proxy_up() {
  local adc="$HOME/.config/gcloud/application_default_credentials.json"
  [[ -f "$adc" ]] || die "没有应用默认凭证（$adc）"
  docker rm -f zj-sqlproxy >/dev/null 2>&1 || true
  # --quota-project：zg 的应用默认凭证里的配额项目是别的项目，不改全局设置，代理调 API 时记到这个项目上。
  # --run-connection-test：起来时先真连一次实例，连不上就退出；不加 --rm，退出了还能看日志。
  run docker run -d --name zj-sqlproxy -p "127.0.0.1:$PROXY_PORT:5432" -v "$adc:/adc.json:ro" "$SQLPROXY_IMAGE" \
    --address 0.0.0.0 --port 5432 --credentials-file /adc.json --quota-project "$P" --run-connection-test "$(conn)"
  local i
  for ((i = 0; i < 60; i++)); do
    # Docker Desktop 的端口映射先通，nc -z 拦不住代理连不上；看代理自己说准备好了
    docker logs zj-sqlproxy 2>&1 | grep -q "ready for new connections" && return 0
    [[ "$(docker inspect -f '{{.State.Running}}' zj-sqlproxy 2>/dev/null)" == true ]] || break
    sleep 1
  done
  docker logs --tail 20 zj-sqlproxy 2>&1 | sed "s/$P/<项目>/g" >&2 || true
  die "Cloud SQL 代理没起来（上面是它最后 20 行日志）"
}
proxy_down() { docker rm -f zj-sqlproxy >/dev/null 2>&1 || true; }

owner_url() { echo "postgresql://zj_owner:$(secret "$SEC_OWNER")@127.0.0.1:$PROXY_PORT/${1:-postgres}"; }

# 在部署用的工作树里跑后端的命令（和镜像同一个提交）
in_wt() { [[ -d "$WT" ]] || die "先跑 build"; (cd "$WT" && uv run --frozen --no-dev --package zoujin-backend "$@"); }

cmd_check() {
  guard
  say "项目：zoujin 配置里的那个；区域 $REGION"
  for a in "${APIS[@]}"; do echo "API $a：$(yn has_api "$a")"; done
  echo "镜像仓库：$(yn has_repo)"
  echo "服务账号：网关 $(yn has_sa "$SA_GW_EMAIL")，叙事者 $(yn has_sa "$SA_NR_EMAIL")"
  echo "数据库实例：$(yn has_sql)"
  for s in "$SEC_OWNER" "$SEC_GW" "$SEC_NR" "$SEC_CLAUDE" "$SEC_SITE"; do echo "密钥 $s：$(yn has_secret "$s")"; done
  local access
  access="$(gateway_access)" || die "网关访问状态未知"
  echo "服务：网关 $(yn has_service "$GW")，叙事者 $(yn has_service "$NR")；网关访问状态：$access"
  echo "镜像：${IMAGE:+已构建（${IMAGE##*:}）}${IMAGE:-还没构建}"
}

cmd_setup() {
  guard
  say "开 API"
  local missing=()
  for a in "${APIS[@]}"; do has_api "$a" || missing+=("$a"); done
  [[ ${#missing[@]} -eq 0 ]] || run gcloud services enable "${missing[@]}" "${PA[@]}"
  say "镜像仓库"
  has_repo || run gcloud artifacts repositories create "$AR_REPO" --repository-format=docker --location="$REGION" "${PA[@]}"
  say "服务账号"
  local sa r
  for sa in "$SA_GW" "$SA_NR"; do
    has_sa "$sa@$P.iam.gserviceaccount.com" || run gcloud iam service-accounts create "$sa" --display-name="$sa" "${PA[@]}"
    for r in "${SA_ROLES[@]}"; do
      run gcloud projects add-iam-policy-binding "$P" --member="serviceAccount:$sa@$P.iam.gserviceaccount.com" \
        --role="$r" --condition=None
    done
  done
  say "数据库实例（第一次建要 10 分钟左右）"
  if ! has_sql; then
    run gcloud sql instances create "$SQL" --database-version=POSTGRES_17 --edition=ENTERPRISE --tier=db-f1-micro \
      --region="$REGION" --storage-type=SSD --storage-size=10 --availability-type=zonal \
      --backup-start-time=18:00 --deletion-protection --root-password="$(rand_hex 24)" "${PA[@]}"
  fi
  local i state=""
  for ((i = 0; i < 60; i++)); do # 上次 gcloud 等不及先退出了，实例可能还在建
    state="$(gcloud sql instances describe "$SQL" "${PA[@]}" --format='value(state)')"
    [[ "$state" == RUNNABLE ]] && break
    sleep 20
  done
  [[ "$state" == RUNNABLE ]] || die "数据库实例还没好（$state），过一会儿再跑"
  say "密钥"
  has_secret "$SEC_OWNER" || rand_hex 24 | tr -d '\n' | new_secret "$SEC_OWNER"
  # 账号单独查：上次可能存了密钥、没建成账号
  if ! gcloud sql users list --instance="$SQL" "${PA[@]}" --format='value(name)' | grep -qx zj_owner; then
    run gcloud sql users create zj_owner --instance="$SQL" --password="$(secret "$SEC_OWNER")" "${PA[@]}"
  fi
  local c
  c="$(conn)"
  has_secret "$SEC_GW" || printf 'postgresql://zj_gw:%s@/%s?host=/cloudsql/%s' "$(rand_hex 24)" "$DB" "$c" | new_secret "$SEC_GW"
  has_secret "$SEC_NR" || printf 'postgresql://zj_nr:%s@/%s?host=/cloudsql/%s' "$(rand_hex 24)" "$DB" "$c" | new_secret "$SEC_NR"
  if ! has_secret "$SEC_CLAUDE"; then
    security find-generic-password -s "$KEYCHAIN_CLAUDE" -w | tr -d '\n' | new_secret "$SEC_CLAUDE" ||
      die "钥匙串里读不到 $KEYCHAIN_CLAUDE"
  fi
  has_secret "$SEC_SITE" || rand_hex 32 | tr -d '\n' | new_secret "$SEC_SITE"
  local s
  for s in "$SEC_SITE:$SA_GW_EMAIL" "$SEC_GW:$SA_GW_EMAIL" "$SEC_NR:$SA_NR_EMAIL" "$SEC_CLAUDE:$SA_GW_EMAIL" "$SEC_CLAUDE:$SA_NR_EMAIL"; do
    run gcloud secrets add-iam-policy-binding "${s%%:*}" --member="serviceAccount:${s#*:}" \
      --role=roles/secretmanager.secretAccessor "${PA[@]}"
  done
  say "数据库和两个应用账号"
  proxy_up
  trap proxy_down EXIT
  ZJ_OWNER_URL="$(owner_url)" ZJ_GW_URL="$(secret "$SEC_GW")" ZJ_NR_URL="$(secret "$SEC_NR")" \
    uv run --directory "$REPO" --frozen --no-dev --package zoujin-backend python -I "$HERE/dbsetup.py" roles
  proxy_down
  trap - EXIT
  say "setup 完成"
}

cmd_build() {
  guard
  local ref="${ZJ_DEPLOY_REF:-origin/main}" sha packs="$STATE/assets/scenes" rc=0
  say "取 $ref"
  run git -C "$REPO" fetch origin main
  sha="$(git -C "$REPO" rev-parse "$ref^{commit}")"
  if [[ -n "$IMAGE" && "${BUILT_SHA:-}" == "$sha" && "${ZJ_REBUILD:-}" != 1 ]]; then
    say "提交 ${sha:0:7} 的镜像已经构建过，跳过（场景包换过要重建：ZJ_REBUILD=1）"
    return 0
  fi
  if [[ -d "$WT" ]]; then
    run git -C "$WT" checkout --detach --force "$sha"
    run git -C "$WT" clean -fdx -e node_modules -e .venv
  else
    run git -C "$REPO" worktree add --detach --force "$WT" "$sha"
  fi
  say "场景包和人物文件（Mac 上的仓库里生成过的 build/，和这个提交的清单比）"
  python3 -I "$HERE/packs.py" "$WT" "$REPO" "$STATE/assets" || rc=$?
  if [[ $rc -eq 1 ]] || { [[ $rc -eq 2 ]] && [[ "${ZJ_ALLOW_STALE:-}" != 1 ]]; }; then
    die "先把上面列的流水线跑完（只有「旧」、确定要照旧部署：ZJ_ALLOW_STALE=1）"
  fi
  say "前端构建（pnpm install + vite build）"
  (cd "$WT" && run $PNPM install --frozen-lockfile &&
    ZOUJIN_SCENE_ROOT="$packs" ZOUJIN_CAST_ROOT="$STATE/assets/cast" run $PNPM --filter @zoujin/web build)
  [[ -f "$WT/apps/web/dist/index.html" ]] || die "前端构建没有 dist/index.html"
  say "检查场景包能生成 manifest"
  ZJ_SCENE_PACKS="$packs" in_wt python -I - <<'EOF' || die "场景包出不了 manifest（上面一行是原因）"
import os
from pathlib import Path
from zoujin_backend.config import DEFAULT_WORLD, Settings
from zoujin_backend.manifest import generate
from zoujin_backend.schemas import SchemaBook
from zoujin_backend.world import Library
s = Settings(database_url="postgresql+psycopg://x", scene_packs=Path(os.environ["ZJ_SCENE_PACKS"]))
m = generate(Library(s.worlds, s.scenes, s.world).current, SchemaBook(s.schemas), packs=s.packs, voices=s.voice_dir)
print(f"manifest {m.doc['manifestVersion']}：带场景包的场景 {len(m.doc['scenes'])} 个")
assert m.doc["scenes"], "一个场景包都没有"
EOF
  say "拼构建目录"
  local ctx="$STATE/ctx"
  rm -rf "$ctx" && mkdir -p "$ctx"
  git -C "$WT" archive "$sha" pyproject.toml uv.lock packages services worlds assets evals fixtures | tar -x -C "$ctx"
  cp -R "$WT/apps/web/dist" "$ctx/web"
  rm -rf "$ctx/web/scenes" # 场景包由网关按带版本的地址从 /app/scenes 发（B-7），dist 里那份不要
  cp -RL "$packs" "$ctx/scenes"
  find "$ctx/scenes" -name '*.md' -delete
  # 脚本的 umask 077 让拼出来的都是 700/600，COPY 会照搬，镜像里的 app 用户（uid 10001）就读不到代码和场景包；
  # 构建目录里只有提交的代码、前端构建和场景包，没有密钥
  chmod -R u=rwX,go=rX "$ctx"
  say "构建镜像（linux/amd64）并推送"
  local img
  img="$REGION-docker.pkg.dev/$P/$AR_REPO/app:${sha:0:7}-$(date +%Y%m%d%H%M%S)"
  run gcloud auth configure-docker "$REGION-docker.pkg.dev" --quiet
  run docker buildx build --platform linux/amd64 -f "$WT/infra/deploy/Dockerfile" -t "$img" --push "$ctx"
  save IMAGE "$img"
  save BUILT_SHA "$sha"
  say "build 完成：提交 ${sha:0:7}"
}

cmd_migrate() {
  guard
  proxy_up
  trap proxy_down EXIT
  say "迁移（alembic upgrade head，提交 ${BUILT_SHA:0:7}）"
  DATABASE_URL="$(owner_url "$DB")" in_wt alembic -c services/backend/alembic.ini upgrade head >>"$LOG" 2>&1 ||
    die "迁移失败，详细在 $LOG"
  say "两个应用账号的权限"
  ZJ_OWNER_URL="$(owner_url)" ZJ_GW_URL="$(secret "$SEC_GW")" ZJ_NR_URL="$(secret "$SEC_NR")" \
    in_wt python -I "$HERE/dbsetup.py" grants
  # 冒烟专用的账号：up、promote 各开一局再删掉，删了也算一天 5 局的次数（S-019），所以每次 migrate 换一个新的，
  # 重跑几次也不会撞上 429
  DATABASE_URL="$(owner_url "$DB")" in_wt zoujin-admin invite create --count 1 >"$STATE/smoke-code.new" &&
    [[ -s "$STATE/smoke-code.new" ]] || die "冒烟用的邀请码没建成"
  mv "$STATE/smoke-code.new" "$STATE/smoke-code"
  proxy_down
  trap - EXIT
  say "migrate 完成"
}

common_env() { # 两个服务共用的环境变量（YAML，写进私有目录，不进命令行）
  [[ -n "$ZJ_CLAUDE_HAIKU" && -n "$ZJ_CLAUDE_SONNET" ]] || die "没有 Claude 的模型 ID（$CONFIG 或 export）"
  printf '%s: "%s"\n' \
    ZJ_MODEL real ZJ_NARRATOR_AUTH iam ZJ_VERTEX_PROJECT "$P" ZJ_VERTEX_LOCATION "$ZJ_VERTEX_LOCATION" \
    ZJ_ARMOR_PROJECT "$P" ZJ_ARMOR_TEMPLATE "$ZJ_ARMOR_TEMPLATE" \
    ZJ_CLAUDE_HAIKU "$ZJ_CLAUDE_HAIKU" ZJ_CLAUDE_SONNET "$ZJ_CLAUDE_SONNET" \
    ZJ_LEDGER /tmp/zj-ledger.jsonl ZJ_LEDGER_ITEM prod \
    ZJ_MAX_CLAUDE_USD "$ZJ_MAX_CLAUDE_USD" ZJ_MAX_GOOGLE_USD "$ZJ_MAX_GOOGLE_USD"
}

smoke() { # smoke MODE URL [BEARER]
  ZJ_SMOKE_PASSWORD="$(secret "$SEC_SITE")" ZJ_SMOKE_URL="$2" ZJ_SMOKE_BEARER="${3:-}" ZJ_SMOKE_CODE="$(head -1 "$STATE/smoke-code" 2>/dev/null)" \
    in_wt python -I "$HERE/smoke.py" "$1"
}

cmd_up() {
  guard
  [[ -n "$IMAGE" ]] || die "先跑 build"
  privacy_check allow-missing
  [[ "$GW_ACCESS" == private || "$GW_ACCESS" == missing ]] ||
    die "评审入口开放期间禁止创建候选地址；先恢复 IAM 私有再部署"
  [[ -s "$STATE/smoke-code" ]] || die "先跑 migrate"
  has_secret "$SEC_SITE" || die "缺少站点访问密码 Secret：先完成 setup 密钥准备，禁止无密码部署"
  local c flags=() bearer="" url
  c="$(conn)"
  common_env >"$STATE/env-narrator.yaml"
  say "叙事者（只许网关的服务账号调）"
  if has_ready "$NR"; then flags=(--no-traffic --tag="$TAG"); else flags=(--no-allow-unauthenticated); fi
  run gcloud run deploy "$NR" --image="$IMAGE" --region="$REGION" "${PA[@]}" "${flags[@]}" \
    --service-account="$SA_NR_EMAIL" --ingress=all --add-cloudsql-instances="$c" \
    --command=/app/.venv/bin/zoujin-narrator --args=--host,0.0.0.0,--port,8080 --port=8080 \
    --env-vars-file="$STATE/env-narrator.yaml" \
    --set-secrets="DATABASE_URL=$SEC_NR:latest,ANTHROPIC_API_KEY=$SEC_CLAUDE:latest" \
    --cpu=1 --memory=1Gi --concurrency=40 --min-instances=0 --max-instances=3 --timeout=300 --cpu-boost
  local fresh=0 # 网关调叙事者的权限是这次新加的：IAM 要一两分钟才生效，生效前叙事者回 403、开局 500
  gcloud run services get-iam-policy "$NR" --region="$REGION" "${PA[@]}" --format=json 2>/dev/null |
    grep -q "serviceAccount:$SA_GW_EMAIL" || fresh=1
  run gcloud run services add-iam-policy-binding "$NR" --region="$REGION" "${PA[@]}" \
    --member="serviceAccount:$SA_GW_EMAIL" --role=roles/run.invoker
  # 候选网关调叙事者的正式地址（还是上一个版本）；promote 两个一起切，再冒烟一次
  {
    common_env
    printf '%s: "%s"\n' ZJ_LIVE real ZJ_NARRATOR_URL "$(url_of "$NR")" FORWARDED_ALLOW_IPS "*"
  } >"$STATE/env-gateway.yaml"
  say "网关（新版本不接流量；第一次是私有服务）"
  if has_ready "$GW"; then flags=(--no-traffic --tag="$TAG"); else flags=(--no-allow-unauthenticated); fi # bash 3.2 + set -u：空数组展开会报错
  run gcloud run deploy "$GW" --image="$IMAGE" --region="$REGION" "${PA[@]}" "${flags[@]}" \
    --service-account="$SA_GW_EMAIL" --ingress=all --add-cloudsql-instances="$c" --port=8080 \
    --env-vars-file="$STATE/env-gateway.yaml" \
    --set-secrets="DATABASE_URL=$SEC_GW:latest,ANTHROPIC_API_KEY=$SEC_CLAUDE:latest,ZJ_SITE_PASSWORD=$SEC_SITE:latest" \
    --cpu=1 --memory=1Gi --concurrency=80 --min-instances=0 --max-instances=3 --timeout=3600 \
    --session-affinity --execution-environment=gen2 --cpu-boost
  say "冒烟（候选版本）"
  url="$(tag_url "$GW")"
  url="${url:-$(url_of "$GW")}"
  bearer="$(gateway_bearer)" || die "无法确定候选网关访问权限" # 每次查真实状态，不信 OPENED 旧标记
  if [[ $fresh -eq 1 ]]; then say "等调用权限生效（90 秒）"; sleep 90; fi
  # 再不过等一分钟重试一次（两次各开一局，promote 再一局，一天 5 局够用）
  smoke smoke "$url" "$bearer" || { say "冒烟没过，一分钟后重试一次"; sleep 60; smoke smoke "$url" "$bearer"; } ||
    die "冒烟没过：新版本没接流量（或服务还是私有的），线上不受影响；修好再跑 all（是 429 次数用完就先跑 migrate 换冒烟账号）"
  save CANDIDATE "$IMAGE"
  say "up 完成：下一步 promote"
}

cmd_promote() {
  guard
  privacy_check
  [[ "$GW_ACCESS" == private ]] || die "评审入口开放期间禁止切换版本；先恢复 IAM 私有再上线"
  [[ -n "${CANDIDATE:-}" && "$CANDIDATE" == "$IMAGE" ]] || die "这个镜像还没过 up 的冒烟"
  say "切流量：叙事者、网关都到新版本"
  run gcloud run services update-traffic "$NR" --to-latest --region="$REGION" "${PA[@]}"
  run gcloud run services update-traffic "$GW" --to-latest --region="$REGION" "${PA[@]}"
  # promote 不改变 IAM。恢复匿名入口必须在用户明确批准、密码门禁已通过验证以后单独执行。
  # privacy-lock 不会被本脚本删除；旧 OPENED 标记不再是授权依据。
  local url i bearer="" anon_ok=0
  bearer="$(gateway_bearer)" || die "无法确定正式网关访问权限"
  url="$(url_of "$GW")"
  printf '%s\n' "$url" >"$STATE/url"
  say "冒烟（正式地址）和匿名被拒"
  for ((i = 0; i < 6; i++)); do
    if smoke anon "$url" "$bearer" >/dev/null 2>&1; then anon_ok=1; break; fi
    if [[ $i -lt 5 ]]; then sleep 10; fi # 等流量切换生效
  done
  [[ $anon_ok -eq 1 ]] || die "匿名门禁检查连续失败：禁止继续冒烟或标记 DEPLOYED，请保持 IAM 私有并检查新版本"
  smoke smoke "$url" "$bearer" || die "正式地址冒烟没过：跑 rollback 切回上一个版本"
  save DEPLOYED "$IMAGE"
  say "promote 完成：地址在 $STATE/url（open \"\$(cat $STATE/url)\" 打开），邀请码用 invite 生成"
}

cmd_verify() {
  guard
  [[ -s "$STATE/url" ]] || die "还没部署"
  privacy_check
  local bearer=""
  bearer="$(gateway_bearer)" || die "无法确定网关访问权限"
  smoke anon "$(cat "$STATE/url")" "$bearer"
}

cmd_invite() {
  guard
  local n="${1:-1}" out
  [[ "$n" =~ ^[0-9]+$ && "$n" -ge 1 ]] || die "邀请码个数要是正整数"
  out="$STATE/invites-$(date +%Y%m%d-%H%M%S).txt"
  proxy_up
  trap proxy_down EXIT
  DATABASE_URL="$(owner_url "$DB")" in_wt zoujin-admin invite create --count "$n" >"$out" || die "邀请码没建成"
  proxy_down
  trap - EXIT
  say "$(wc -l <"$out" | tr -d ' ') 个邀请码写在 ${out}（一人一个，只给 18 岁以上的人）"
}

cmd_rollback() {
  guard
  privacy_check
  [[ "$GW_ACCESS" == private ]] || die "评审入口开放期间禁止直接回滚；先恢复 IAM 私有，避免旧版本无密码"
  local s prev
  for s in "$GW" "$NR"; do
    prev="$(gcloud run revisions list --service="$s" --region="$REGION" "${PA[@]}" \
      --sort-by=~metadata.creationTimestamp --format='value(metadata.name)' --limit=2 | sed -n 2p)"
    [[ -n "$prev" ]] || die "没有上一个版本"
    run gcloud run services update-traffic "$s" --to-revisions="$prev=100" --region="$REGION" "${PA[@]}"
  done
  say "已切回上一个版本"
}

cmd_pause() { guard; run gcloud sql instances patch "$SQL" --activation-policy=NEVER "${PA[@]}"; say "数据库已停"; }
cmd_resume() { guard; run gcloud sql instances patch "$SQL" --activation-policy=ALWAYS "${PA[@]}"; say "数据库已开"; }

cmd_all() {
  cmd_setup
  cmd_build
  cmd_migrate
  cmd_up
  cmd_promote
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  case "${1:-}" in
    all | check | setup | build | migrate | up | promote | verify | rollback | pause | resume) "cmd_$1" ;;
    invite) cmd_invite "${2:-1}" ;;
    *) sed -n '2,16p' "$0"; exit 2 ;;
  esac
fi
