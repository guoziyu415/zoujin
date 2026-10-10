#!/usr/bin/env bash
# S-1b：把语音代理临时部署到走进物语的 GCP 项目（Cloud Run），测完当天删除。方案和规则：s1b-plan.md（D-017）。
#
# 只在 zg 明确同意之后执行；每一步单独执行，执行前先把这一步要跑的命令给 zg 看。
#   ./s1b_deploy.sh check      看现在有什么（只读）
#   ./s1b_deploy.sh prepare    开 4 个 API，建镜像仓库和服务账号（只能调 Gemini；zg 可以临时以它的身份做检查）
#   ./s1b_deploy.sh sacheck    在这台 Mac 上以服务账号的身份连一次 Live，确认权限已生效（不部署、不花钱）
#   ./s1b_deploy.sh build      在这台 Mac 上构建镜像并推到镜像仓库（ZJ_S1B_PAGE=前端测试页目录）
#   ./s1b_deploy.sh up         建成私有服务（只有 zg 的 Google 身份能访问），然后冒烟测试
#   ./s1b_deploy.sh open       打开公开访问（靠测试码保护），再查一次匿名访问被拒
#   ./s1b_deploy.sh logs       把计时日志拉回 out/s1b/（只留时间戳和计时字段）
#   ./s1b_deploy.sh down       删除服务、镜像仓库、服务账号，确认原地址打不开
#
# 服务名在 up 时随机生成（s- 加 8 位），所以网址里没有产品名；镜像仓库和服务账号也用中性的名字。
# 地址、服务名和测试码只写在 ~/.zoujin-spike/ 里（权限 600），本脚本不把地址和测试码打印到屏幕上。
# gcloud 和 docker 的输出写进 ~/.zoujin-spike/s1b-deploy.log（里面有地址，不要贴到聊天或文档里）。
set -euo pipefail
umask 077

REGION=asia-northeast1
REPO=spike-images
SA_NAME=s1b-proxy
SECRET_DIR="${ZJ_S1B_SECRET_DIR:-$HOME/.zoujin-spike}"
URL_FILE="$SECRET_DIR/s1b-url"
ENV_FILE="$SECRET_DIR/s1b.env"
CODE_FILE="$SECRET_DIR/s1b-code"
IMAGE_FILE="$SECRET_DIR/s1b-image"
SERVICE_FILE="$SECRET_DIR/s1b-service"
SA_OK_FILE="$SECRET_DIR/s1b-sa-ok"
LOG="$SECRET_DIR/s1b-deploy.log"
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE"

die() { echo "[停止] $*" >&2; exit 1; }

guard() {
  [[ "${CLOUDSDK_ACTIVE_CONFIG_NAME:-}" == "zoujin" ]] || die "先执行 export CLOUDSDK_ACTIVE_CONFIG_NAME=zoujin（日々の森 的配置不能用）"
  [[ -n "${ZJ_PROJECT:-}" ]] || die "先执行 export ZJ_PROJECT=走进物语的项目ID"
  [[ "$(gcloud config get-value project 2>/dev/null)" == "$ZJ_PROJECT" ]] || die "gcloud 当前项目和 ZJ_PROJECT 不一致"
  mkdir -p "$SECRET_DIR" && chmod 700 "$SECRET_DIR"
  SA="$SA_NAME@$ZJ_PROJECT.iam.gserviceaccount.com"
  P=(--project="$ZJ_PROJECT")
  SERVICE=""
  [[ -f "$SERVICE_FILE" ]] && SERVICE="$(cat "$SERVICE_FILE")"
  return 0
}

# Run a command with its output going to the private log only.
run() {
  echo "  → $1 $2 $3 …" >&2
  echo "### $(date '+%F %T') $*" >>"$LOG"
  "$@" >>"$LOG" 2>&1 || die "上一条命令失败，详细信息在 $LOG（里面可能有地址，不要贴到聊天里，只转述错误那一行）"
}

has_service() { [[ -n "$SERVICE" ]] && gcloud run services describe "$SERVICE" --region="$REGION" "${P[@]}" --format='value(metadata.name)' >/dev/null 2>&1; }
has_repo() { gcloud artifacts repositories describe "$REPO" --location="$REGION" "${P[@]}" --format='value(name)' >/dev/null 2>&1; }
has_sa() { gcloud iam service-accounts describe "$SA" "${P[@]}" --format='value(email)' >/dev/null 2>&1; }
yn() { if "$@"; then echo 有; else echo 没有; fi; }

# curl already prints 000 when it cannot connect; only add it when curl printed nothing.
http_code() { local c; c="$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 "$@")" || true; echo "${c:-000}"; }

# Cloud Run needs a moment to route a new service, apply an access change or drop a deleted one, so one request
# proves nothing: ask every 10 seconds, up to $3 times, until the code is one of $2. Prints the last code.
# Probe "/" only: Cloud Run answers paths ending in "z" (e.g. /healthz) with 404 at its front end.
wait_code() {
  local url="$1" want="$2" tries="$3" code="" i
  for ((i = 1; i <= tries; i++)); do
    code="$(http_code "$url")"
    if [[ " $want " == *" $code "* ]]; then echo "$code"; return 0; fi
    (( i < tries )) && sleep 10
  done
  echo "$code"
  return 1
}

cmd_check() {
  guard
  local apis
  apis="$(gcloud services list --enabled "${P[@]}" --format='value(config.name)' 2>/dev/null || true)"
  for api in run artifactregistry iam iamcredentials; do
    if grep -qx "$api.googleapis.com" <<<"$apis"; then echo "API $api：已开"; else echo "API $api：未开"; fi
  done
  echo "镜像仓库 $REPO：$(yn has_repo)"
  echo "服务账号 $SA_NAME：$(yn has_sa)"
  echo "服务（名字随机，记在 $SERVICE_FILE）：$(yn has_service)"
  echo "测试码：$([[ -f "$CODE_FILE" ]] && echo 有 || echo 没有)；镜像记录：$([[ -f "$IMAGE_FILE" ]] && echo 有 || echo 没有)；sacheck：$([[ -f "$SA_OK_FILE" ]] && echo 通过 || echo 没有)"
}

cmd_prepare() {
  guard
  # iamcredentials: sacheck borrows the service account's identity through it, billed to this project, not to the
  # project named in zg's ADC file.
  run gcloud services enable run.googleapis.com artifactregistry.googleapis.com iam.googleapis.com \
    iamcredentials.googleapis.com "${P[@]}"
  local me
  me="$(gcloud config get-value account 2>/dev/null)"
  [[ -n "$me" ]] || die "gcloud 没有登录的账号"
  has_repo || run gcloud artifacts repositories create "$REPO" --repository-format=docker --location="$REGION" \
    --labels=app=zoujin-spike --description="temporary" "${P[@]}"
  has_sa || run gcloud iam service-accounts create "$SA_NAME" --display-name="S-1b voice proxy (temporary)" "${P[@]}"
  # A new service account can take a few seconds to become visible to IAM. The second binding lets zg's own login
  # act as the account for sacheck; it sits on the account itself and disappears with it at down.
  for i in 1 2 3; do
    if gcloud projects add-iam-policy-binding "$ZJ_PROJECT" --member="serviceAccount:$SA" --role=roles/aiplatform.user \
         --condition=None --quiet >>"$LOG" 2>&1 \
       && gcloud iam service-accounts add-iam-policy-binding "$SA" "${P[@]}" --member="user:$me" \
         --role=roles/iam.serviceAccountTokenCreator --quiet >>"$LOG" 2>&1; then
      rm -f "$SA_OK_FILE"
      echo "准备好了：4 个 API、镜像仓库、服务账号（只有调用 Gemini 的权限）。下一步：./s1b_deploy.sh sacheck"
      return
    fi
    sleep $((i * 10))
  done
  die "给服务账号授权失败，详细信息在 $LOG"
}

# The third attempt (2026-10-07) failed only on Cloud Run: the service account could not open a Live session, most
# likely because its new permission had not applied yet. Prove it from this Mac first, as that same account.
cmd_sacheck() {
  guard
  has_sa || die "先执行 prepare"
  rm -f "$SA_OK_FILE"
  echo "在这台 Mac 上以服务账号的身份连一次 Live（不建密钥、不说话、不花钱；新账号的权限可能要几分钟才生效，最多等 7 分钟）："
  ZJ_IMPERSONATE_SA="$SA" uv run python -m zj_spike.s1b_proxy sacheck \
    || die "服务账号还连不上 Live，不要继续。把上面几行转给后端（已去掉项目 ID、地址和账号）。"
  date '+%F %T' >"$SA_OK_FILE"
  echo "可以继续：build。"
}

# After a failed smoke test: the service's own record of why Live refused (project, addresses and accounts removed).
show_session_errors() {
  echo "服务日志里最近的会话错误（已去掉项目 ID、地址和账号；没有就是空的）："
  sleep 10
  gcloud logging read \
    "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"$SERVICE\" AND jsonPayload.event=\"session_error\"" \
    "${P[@]}" --freshness=30m --limit=5 \
    --format='value(timestamp,jsonPayload.errorType,jsonPayload.upstreamCode,jsonPayload.upstreamStatus,jsonPayload.upstreamMessage)' \
    2>>"$LOG" || true
}

# Copy what the image needs into an empty build directory.
stage_ctx() {
  local ctx="$1"
  cp pyproject.toml uv.lock s1b/Dockerfile "$ctx/"
  cp -R zj_spike "$ctx/"
  find "$ctx/zj_spike" -name __pycache__ -prune -exec rm -rf {} +
  mkdir "$ctx/page"
  if [[ -n "${ZJ_S1B_PAGE:-}" ]]; then
    [[ -f "$ZJ_S1B_PAGE/index.html" ]] || die "ZJ_S1B_PAGE 里没有 index.html"
    cp -R "$ZJ_S1B_PAGE"/. "$ctx/page/"
  else
    echo "  （没有设 ZJ_S1B_PAGE：镜像里只有占位页面，前端测试页之后再放）" >&2
  fi
  # The umask 077 above makes every copy 600/700, and COPY keeps those modes; the image runs as a non-root user,
  # which then cannot read its own code (S-1b part 2 failed on exactly this, 2026-10-07).
  chmod -R a+rX "$ctx"
}

cmd_build() {
  guard
  command -v docker >/dev/null || die "没有 docker"
  local ctx tag image registry
  ctx="$(mktemp -d)"
  stage_ctx "$ctx"
  tag="$(date +%Y%m%d-%H%M%S)"
  registry="$REGION-docker.pkg.dev"
  image="$registry/$ZJ_PROJECT/$REPO/s1b:$tag"
  run docker buildx build --platform linux/amd64 -t "$image" -t "s1b-check:$tag" --load "$ctx"
  rm -rf "$ctx"
  # Before pushing: start the image offline as the user Cloud Run will use, and check it can read its code and page.
  # The local tag keeps the project ID off the screen.
  echo "检查镜像（断网，以服务实际用的非 root 用户运行）："
  docker run --rm --network none --platform linux/amd64 "s1b-check:$tag" \
    /app/.venv/bin/python -m zj_spike.s1b_proxy selfcheck || die "镜像检查没通过，没有推送。把上面几行转给后端。"
  docker image rm "s1b-check:$tag" >/dev/null 2>&1 || true
  # A one-hour token instead of a permanent docker credential helper; logged out right after the push.
  gcloud auth print-access-token | docker login -u oauth2accesstoken --password-stdin "https://$registry" >>"$LOG" 2>&1 \
    || die "登录镜像仓库失败，详细信息在 $LOG"
  run docker push "$image"
  docker logout "https://$registry" >>"$LOG" 2>&1 || true
  printf '%s\n' "$image" >"$IMAGE_FILE"
  echo "镜像已推送（标签 $tag）。"
}

cmd_up() {
  guard
  [[ -f "$ENV_FILE" ]] || die "没有测试码。先执行：uv run python -m zj_spike.s1b_proxy newcode"
  [[ -f "$IMAGE_FILE" ]] || die "先执行 build"
  [[ -f "$SA_OK_FILE" ]] || die "先执行 sacheck（部署前在本机确认服务账号能连上 Live）"
  has_service && die "服务已经存在。要重新部署，先 down，再重新问 zg。"
  # A random service name, so the address says nothing about the product (D-017).
  SERVICE="$(python3 -c 'import secrets, string; print("s-" + "".join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(8)))')"
  printf '%s\n' "$SERVICE" >"$SERVICE_FILE"
  local hash url
  hash="$(sed -n 's/^ZJ_S1B_CODE_HASH=//p' "$ENV_FILE")"
  # Cloud Run cannot create a service at 0% traffic, so the first revision is private instead:
  # only callers with zg's Google identity get through (same effect as 0% public traffic).
  run gcloud run deploy "$SERVICE" --image="$(cat "$IMAGE_FILE")" --region="$REGION" "${P[@]}" \
    --service-account="$SA" --no-allow-unauthenticated --ingress=all \
    --max-instances=1 --min-instances=0 --concurrency=4 --timeout=3600 --cpu=1 --memory=512Mi \
    --labels=app=zoujin-spike \
    --set-env-vars="ZJ_PROJECT=$ZJ_PROJECT,ZJ_S1B_CODE_HASH=$hash,ZJ_S1B_VOICE=${ZJ_S1B_VOICE:-Puck},ZJ_S1B_MAX_USD=${ZJ_S1B_MAX_USD:-3}" \
    --quiet
  url="$(gcloud run services describe "$SERVICE" --region="$REGION" "${P[@]}" --format='value(status.url)')"
  printf '%s\n' "$url" >"$URL_FILE"
  echo "服务已建成，目前是私有的。地址存在 $URL_FILE（不显示）。"
  local code
  if code="$(wait_code "$url/" "401 403 200" 9)"; then
    [[ "$code" == "200" ]] && die "没有 Google 身份也打开了页面（HTTP 200），服务不是私有的。马上执行 down，告诉后端。"
    echo "  [OK] 没有 Google 身份的访问被拒：HTTP $code"
  else
    die "等了 80 秒，没有 Google 身份的访问还没有出现「被拒」（最后一次 HTTP $code）。先 down，告诉后端。"
  fi
  echo "冒烟测试（带 zg 的身份穿过私有这一层，测我们自己的测试码和 Cookie 保护，再说两句话）："
  ZJ_S1B_ID_TOKEN="$(gcloud auth print-identity-token)" uv run python -m zj_spike.s1b_proxy smoke --url-file --voice-retry 120 \
    || { show_session_errors; die "冒烟测试没通过，不要执行 open。先 down，把上面几行转给后端。"; }
}

cmd_open() {
  guard
  [[ -f "$URL_FILE" && -n "$SERVICE" ]] || die "先执行 up"
  echo "### $(date '+%F %T') open" >>"$LOG"
  if ! gcloud run services update "$SERVICE" --region="$REGION" "${P[@]}" --no-invoker-iam-check --quiet >>"$LOG" 2>&1; then
    # Older gcloud: same effect through the invoker role.
    run gcloud run services add-iam-policy-binding "$SERVICE" --region="$REGION" "${P[@]}" \
      --member=allUsers --role=roles/run.invoker --quiet
  fi
  local code
  code="$(wait_code "$(cat "$URL_FILE")/" "200" 18)" \
    || die "3 分钟内公开还没生效（匿名打开页面 HTTP $code）。服务仍是私有的，不会对外。过几分钟再执行一次 open；还不行就 down，告诉后端。"
  echo "  [OK] 公开已生效：匿名能打开页面（HTTP 200）"
  echo "复查：现在任何人都能打开地址，但没有测试码什么都做不了。"
  uv run python -m zj_spike.s1b_proxy smoke --url-file --anon-only || die "匿名访问没有被拒！马上执行 down。"
  echo
  echo "可以测了。下面两件事请 zg 自己做（不要贴到聊天里）："
  echo "  1. 把地址发到 iPhone：pbcopy < $URL_FILE ，然后在 iPhone 的 Safari 地址栏粘贴（通用剪贴板），或用 AirDrop。"
  echo "  2. 看测试码：cat $CODE_FILE"
  echo "测完当天执行：./s1b_deploy.sh logs，然后 ./s1b_deploy.sh down"
}

cmd_logs() {
  guard
  mkdir -p out/s1b
  local out="out/s1b/logs-$(date +%Y%m%d-%H%M%S).jsonl"
  gcloud logging read \
    "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"${SERVICE:?先执行 up}\" AND jsonPayload.kind=\"s1b\"" \
    "${P[@]}" --freshness=2d --order=asc --format=json 2>>"$LOG" \
    | python3 -c 'import json,sys
for e in json.load(sys.stdin):
    print(json.dumps({"at": e.get("timestamp"), **e.get("jsonPayload", {})}, ensure_ascii=False))' >"$out"
  echo "写到 $out（$(wc -l <"$out" | tr -d ' ') 行；只有时间戳和计时字段，没有项目 ID 和地址，可以交回团队）。"
}

cmd_down() {
  guard
  local url=""
  [[ -f "$URL_FILE" ]] && url="$(cat "$URL_FILE")"
  has_service && run gcloud run services delete "$SERVICE" --region="$REGION" "${P[@]}" --quiet
  has_repo && run gcloud artifacts repositories delete "$REPO" --location="$REGION" "${P[@]}" --quiet
  gcloud projects remove-iam-policy-binding "$ZJ_PROJECT" --member="serviceAccount:$SA" --role=roles/aiplatform.user \
    --condition=None --quiet >>"$LOG" 2>&1 || true
  has_sa && run gcloud iam service-accounts delete "$SA" "${P[@]}" --quiet
  echo "服务、镜像仓库、服务账号都已删除。"
  if [[ -n "$url" ]]; then
    local code
    if code="$(wait_code "$url/" "404" 12)"; then
      echo "  [OK] 原地址已经打不开（HTTP 404）"
    else
      echo "  [注意] 两分钟后原地址还是 HTTP $code。服务已经由 gcloud 删除（上面没有报错）；执行 ./s1b_deploy.sh check，应显示「服务：没有」。"
    fi
  fi
  has_service || rm -f "$SERVICE_FILE"
  rm -f "$URL_FILE" "$ENV_FILE" "$CODE_FILE" "$IMAGE_FILE" "$SA_OK_FILE"
  echo "测试码、服务名和地址文件已删除。开着的 4 个 API 不花钱，留着（开发阶段还要用）。"
}

case "${1:-}" in
  check) cmd_check ;;
  prepare) cmd_prepare ;;
  sacheck) cmd_sacheck ;;
  build) cmd_build ;;
  up) cmd_up ;;
  open) cmd_open ;;
  logs) cmd_logs ;;
  down) cmd_down ;;
  _stage) [[ -d "${2:-}" ]] || die "用法：_stage 空目录（只给离线测试用）"; stage_ctx "$2" ;;
  *) sed -n '2,16p' "$0"; exit 2 ;;
esac
