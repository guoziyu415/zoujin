#!/usr/bin/env bash
# S-1b: deploy the voice proxy temporarily to the 物語 (Monogatari) GCP project (Cloud Run) and delete it the same day
# the test ends. Plan and rules: s1b-plan.md (D-017).
#
# Run only after zg has clearly agreed; run each step on its own, and show zg the commands of a step before running it.
#   ./s1b_deploy.sh check      show what exists now (read-only)
#   ./s1b_deploy.sh prepare    enable 4 APIs, create the image repository and the service account (it can only call
#                              Gemini; zg can temporarily act as it for checks)
#   ./s1b_deploy.sh sacheck    on this Mac, open Live once as the service account to confirm the permission has
#                              applied (no deployment, no cost)
#   ./s1b_deploy.sh build      build the image on this Mac and push it to the repository (ZJ_S1B_PAGE=frontend test
#                              page directory)
#   ./s1b_deploy.sh up         create a private service (only zg's Google identity can reach it), then smoke-test it
#   ./s1b_deploy.sh open       open public access (protected by the test code), then check anonymous access is refused
#   ./s1b_deploy.sh logs       pull the timing logs back into out/s1b/ (timestamps and timing fields only)
#   ./s1b_deploy.sh down       delete the service, image repository and service account; confirm the old address is gone
#
# The service name is random at up (s- plus 8 characters), so the URL holds no product name; the image repository and
# service account also have neutral names. The address, service name and test code are written only under
# ~/.zoujin-spike/ (mode 600); this script never prints the address or the test code. gcloud and docker output goes to
# ~/.zoujin-spike/s1b-deploy.log (it contains the address; do not paste it into chat or docs).
#
# S-1b：音声プロキシを 物語 (Monogatari) の GCP プロジェクト（Cloud Run）に一時的にデプロイし、テストの当日に削除する。
# 計画とルール：s1b-plan.md（D-017）。
#
# zg がはっきり同意した後にだけ実行する。各ステップは個別に実行し、実行前にそのステップのコマンドを zg に見せる。
#   ./s1b_deploy.sh check      現在あるものを表示（読み取りのみ）
#   ./s1b_deploy.sh prepare    API を 4 つ有効化し、イメージリポジトリとサービスアカウントを作成（Gemini しか呼べない。
#                              zg は確認のため一時的にそのアカウントとして動ける）
#   ./s1b_deploy.sh sacheck    この Mac でサービスアカウントとして Live に一度接続し、権限の反映を確認（デプロイなし・費用なし）
#   ./s1b_deploy.sh build      この Mac でイメージをビルドしてリポジトリにプッシュ（ZJ_S1B_PAGE=フロントエンドのテストページのディレクトリ）
#   ./s1b_deploy.sh up         非公開サービスを作成（zg の Google ID だけがアクセス可）し、スモークテストする
#   ./s1b_deploy.sh open       公開アクセスを開き（テストコードで保護）、匿名アクセスが拒否されることを再確認
#   ./s1b_deploy.sh logs       計時ログを out/s1b/ に取得（タイムスタンプと計時フィールドのみ）
#   ./s1b_deploy.sh down       サービス・イメージリポジトリ・サービスアカウントを削除し、元のアドレスが開けないことを確認
#
# サービス名は up のときにランダム生成する（s- と 8 文字）ので URL に製品名は出ない。イメージリポジトリとサービスアカウントも
# 中立的な名前にする。アドレス・サービス名・テストコードは ~/.zoujin-spike/（パーミッション 600）にだけ書き、このスクリプトは
# アドレスとテストコードを画面に出さない。gcloud と docker の出力は ~/.zoujin-spike/s1b-deploy.log に書く
# （アドレスを含むのでチャットや文書に貼らないこと）。
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

die() { echo "[stop / 停止] $*" >&2; exit 1; }

guard() {
  [[ "${CLOUDSDK_ACTIVE_CONFIG_NAME:-}" == "zoujin" ]] || die "First run export CLOUDSDK_ACTIVE_CONFIG_NAME=zoujin (the 日々の森 configuration must not be used) / 先に export CLOUDSDK_ACTIVE_CONFIG_NAME=zoujin を実行（日々の森 の設定は使えない）"
  [[ -n "${ZJ_PROJECT:-}" ]] || die "First run export ZJ_PROJECT=<物語 project ID> / 先に export ZJ_PROJECT=<物語のプロジェクトID> を実行"
  [[ "$(gcloud config get-value project 2>/dev/null)" == "$ZJ_PROJECT" ]] || die "The current gcloud project does not match ZJ_PROJECT / gcloud の現在のプロジェクトが ZJ_PROJECT と一致しない"
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
  "$@" >>"$LOG" 2>&1 || die "The last command failed; details in $LOG (it may contain the address: do not paste it into chat, only relay the error line) / 直前のコマンドが失敗。詳細は $LOG（アドレスを含む可能性があるのでチャットに貼らず、エラーの行だけ伝える）"
}

has_service() { [[ -n "$SERVICE" ]] && gcloud run services describe "$SERVICE" --region="$REGION" "${P[@]}" --format='value(metadata.name)' >/dev/null 2>&1; }
has_repo() { gcloud artifacts repositories describe "$REPO" --location="$REGION" "${P[@]}" --format='value(name)' >/dev/null 2>&1; }
has_sa() { gcloud iam service-accounts describe "$SA" "${P[@]}" --format='value(email)' >/dev/null 2>&1; }
yn() { if "$@"; then echo "yes/あり"; else echo "no/なし"; fi; }

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
    if grep -qx "$api.googleapis.com" <<<"$apis"; then echo "API $api: enabled/有効"; else echo "API $api: disabled/無効"; fi
  done
  echo "Image repository / イメージリポジトリ $REPO: $(yn has_repo)"
  echo "Service account / サービスアカウント $SA_NAME: $(yn has_sa)"
  echo "Service / サービス (random name, kept in / ランダム名、記録先 $SERVICE_FILE): $(yn has_service)"
  echo "Test code / テストコード: $([[ -f "$CODE_FILE" ]] && echo "yes/あり" || echo "no/なし"); image record / イメージ記録: $([[ -f "$IMAGE_FILE" ]] && echo "yes/あり" || echo "no/なし"); sacheck: $([[ -f "$SA_OK_FILE" ]] && echo "passed/合格" || echo "no/なし")"
}

cmd_prepare() {
  guard
  # iamcredentials: sacheck borrows the service account's identity through it, billed to this project, not to the
  # project named in zg's ADC file.
  run gcloud services enable run.googleapis.com artifactregistry.googleapis.com iam.googleapis.com \
    iamcredentials.googleapis.com "${P[@]}"
  local me
  me="$(gcloud config get-value account 2>/dev/null)"
  [[ -n "$me" ]] || die "gcloud has no logged-in account / gcloud にログイン中のアカウントがない"
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
      echo "Ready: 4 APIs, image repository, service account (permission to call Gemini only). Next: ./s1b_deploy.sh sacheck / 準備完了：API 4 つ、イメージリポジトリ、サービスアカウント（Gemini を呼ぶ権限のみ）。次：./s1b_deploy.sh sacheck"
      return
    fi
    sleep $((i * 10))
  done
  die "Granting the service account its roles failed; details in $LOG / サービスアカウントへの権限付与に失敗。詳細は $LOG"
}

# The third attempt (2026-10-07) failed only on Cloud Run: the service account could not open a Live session, most
# likely because its new permission had not applied yet. Prove it from this Mac first, as that same account.
cmd_sacheck() {
  guard
  has_sa || die "Run prepare first / 先に prepare を実行"
  rm -f "$SA_OK_FILE"
  echo "Opening Live once on this Mac as the service account (no key, nothing said, no cost; a new account's permission may take a few minutes to apply, waiting up to 7 minutes) / この Mac でサービスアカウントとして Live に一度接続（鍵は作らず、話さず、費用なし。新しいアカウントの権限反映には数分かかることがあり、最大 7 分待つ）:"
  ZJ_IMPERSONATE_SA="$SA" uv run python -m zj_spike.s1b_proxy sacheck \
    || die "The service account still cannot reach Live; do not continue. Forward the lines above to the backend (project ID, address and account removed). / サービスアカウントがまだ Live に接続できない。先に進まず、上の数行をバックエンドに伝える（プロジェクト ID・アドレス・アカウントは除去済み）。"
  date '+%F %T' >"$SA_OK_FILE"
  echo "OK to continue: build. / 続行可：build"
}

# After a failed smoke test: the service's own record of why Live refused (project, addresses and accounts removed).
show_session_errors() {
  echo "Recent session errors in the service log (project ID, address and account removed; empty if none) / サービスログ中の最近のセッションエラー（プロジェクト ID・アドレス・アカウントは除去済み。なければ空）:"
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
    [[ -f "$ZJ_S1B_PAGE/index.html" ]] || die "No index.html in ZJ_S1B_PAGE / ZJ_S1B_PAGE に index.html がない"
    cp -R "$ZJ_S1B_PAGE"/. "$ctx/page/"
  else
    echo "  (ZJ_S1B_PAGE not set: the image has only the placeholder page; the frontend test page comes later / ZJ_S1B_PAGE 未設定：イメージにはプレースホルダーページだけが入る。フロントエンドのテストページは後で入れる)" >&2
  fi
  # The umask 077 above makes every copy 600/700, and COPY keeps those modes; the image runs as a non-root user,
  # which then cannot read its own code (S-1b part 2 failed on exactly this, 2026-10-07).
  chmod -R a+rX "$ctx"
}

cmd_build() {
  guard
  command -v docker >/dev/null || die "docker not found / docker がない"
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
  echo "Checking the image (offline, as the non-root user the service really uses) / イメージを確認（ネットワークなし、サービスが実際に使う非 root ユーザーで実行）:"
  docker run --rm --network none --platform linux/amd64 "s1b-check:$tag" \
    /app/.venv/bin/python -m zj_spike.s1b_proxy selfcheck || die "Image check failed; nothing pushed. Forward the lines above to the backend. / イメージチェック不合格のためプッシュしていない。上の数行をバックエンドに伝える。"
  docker image rm "s1b-check:$tag" >/dev/null 2>&1 || true
  # A one-hour token instead of a permanent docker credential helper; logged out right after the push.
  gcloud auth print-access-token | docker login -u oauth2accesstoken --password-stdin "https://$registry" >>"$LOG" 2>&1 \
    || die "Logging in to the image repository failed; details in $LOG / イメージリポジトリへのログインに失敗。詳細は $LOG"
  run docker push "$image"
  docker logout "https://$registry" >>"$LOG" 2>&1 || true
  printf '%s\n' "$image" >"$IMAGE_FILE"
  echo "Image pushed (tag $tag). / イメージをプッシュした（タグ $tag）。"
}

cmd_up() {
  guard
  [[ -f "$ENV_FILE" ]] || die "No test code. First run: uv run python -m zj_spike.s1b_proxy newcode / テストコードがない。先に uv run python -m zj_spike.s1b_proxy newcode を実行"
  [[ -f "$IMAGE_FILE" ]] || die "Run build first / 先に build を実行"
  [[ -f "$SA_OK_FILE" ]] || die "Run sacheck first (confirm on this machine that the service account can reach Live before deploying) / 先に sacheck を実行（デプロイ前に本機でサービスアカウントが Live に接続できることを確認）"
  has_service && die "The service already exists. To redeploy, run down first, then ask zg again. / サービスはすでにある。再デプロイするには先に down し、改めて zg に確認する。"
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
  echo "Service created; it is private for now. Address stored in $URL_FILE (not shown). / サービスを作成した。現在は非公開。アドレスは $URL_FILE に保存（表示しない）。"
  local code
  if code="$(wait_code "$url/" "401 403 200" 9)"; then
    [[ "$code" == "200" ]] && die "The page opened without a Google identity (HTTP 200); the service is not private. Run down now and tell the backend. / Google ID なしでページが開いた（HTTP 200）。サービスが非公開になっていない。すぐに down を実行し、バックエンドに伝える。"
    echo "  [OK] Access without a Google identity refused / Google ID なしのアクセスは拒否: HTTP $code"
  else
    die "After 80 s, access without a Google identity is still not refused (last HTTP $code). Run down first and tell the backend. / 80 秒待っても Google ID なしのアクセスが拒否されない（最後は HTTP $code）。先に down し、バックエンドに伝える。"
  fi
  echo "Smoke test (passes the private layer with zg's identity, tests our own test-code and cookie protection, then says two lines) / スモークテスト（zg の ID で非公開の層を通り、独自のテストコードと Cookie の保護を確認してから 2 文話す）:"
  ZJ_S1B_ID_TOKEN="$(gcloud auth print-identity-token)" uv run python -m zj_spike.s1b_proxy smoke --url-file --voice-retry 120 \
    || { show_session_errors; die "Smoke test failed; do not run open. Run down first and forward the lines above to the backend. / スモークテスト不合格。open は実行しない。先に down し、上の数行をバックエンドに伝える。"; }
}

cmd_open() {
  guard
  [[ -f "$URL_FILE" && -n "$SERVICE" ]] || die "Run up first / 先に up を実行"
  echo "### $(date '+%F %T') open" >>"$LOG"
  if ! gcloud run services update "$SERVICE" --region="$REGION" "${P[@]}" --no-invoker-iam-check --quiet >>"$LOG" 2>&1; then
    # Older gcloud: same effect through the invoker role.
    run gcloud run services add-iam-policy-binding "$SERVICE" --region="$REGION" "${P[@]}" \
      --member=allUsers --role=roles/run.invoker --quiet
  fi
  local code
  code="$(wait_code "$(cat "$URL_FILE")/" "200" 18)" \
    || die "Public access did not take effect within 3 minutes (anonymous page load HTTP $code). The service is still private and not exposed. Run open again in a few minutes; if it still fails, run down and tell the backend. / 3 分以内に公開が反映されない（匿名でのページ表示 HTTP $code）。サービスはまだ非公開で外部には出ていない。数分後にもう一度 open を実行し、それでも駄目なら down してバックエンドに伝える。"
  echo "  [OK] Public access is live: the page opens anonymously (HTTP 200) / 公開が反映された：匿名でページが開く（HTTP 200）"
  echo "Recheck: anyone can now open the address, but nothing works without the test code. / 再確認：誰でもアドレスを開けるが、テストコードなしでは何もできない。"
  uv run python -m zj_spike.s1b_proxy smoke --url-file --anon-only || die "Anonymous access was not refused! Run down now. / 匿名アクセスが拒否されていない！すぐに down を実行。"
  echo
  echo "Ready to test. zg, please do these two things yourself (do not paste them into chat) / テスト可能。次の 2 つは zg 自身が行う（チャットに貼らない）:"
  echo "  1. Send the address to the iPhone: pbcopy < $URL_FILE , then paste it into Safari's address bar on the iPhone (Universal Clipboard), or use AirDrop. / アドレスを iPhone に送る：pbcopy < $URL_FILE のあと iPhone の Safari のアドレスバーに貼り付ける（ユニバーサルクリップボード）か、AirDrop を使う。"
  echo "  2. View the test code / テストコードを見る: cat $CODE_FILE"
  echo "On the test day, when done: ./s1b_deploy.sh logs, then ./s1b_deploy.sh down / テスト当日、終わったら ./s1b_deploy.sh logs のあと ./s1b_deploy.sh down"
}

cmd_logs() {
  guard
  mkdir -p out/s1b
  local out="out/s1b/logs-$(date +%Y%m%d-%H%M%S).jsonl"
  gcloud logging read \
    "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"${SERVICE:?Run up first / 先に up を実行}\" AND jsonPayload.kind=\"s1b\"" \
    "${P[@]}" --freshness=2d --order=asc --format=json 2>>"$LOG" \
    | python3 -c 'import json,sys
for e in json.load(sys.stdin):
    print(json.dumps({"at": e.get("timestamp"), **e.get("jsonPayload", {})}, ensure_ascii=False))' >"$out"
  echo "Wrote $out ($(wc -l <"$out" | tr -d ' ') lines; timestamps and timing fields only, no project ID or address, fine to hand to the team) / $out に書き出した（タイムスタンプと計時フィールドのみ。プロジェクト ID とアドレスは含まないのでチームに渡してよい）。"
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
  echo "Service, image repository and service account deleted. / サービス・イメージリポジトリ・サービスアカウントを削除した。"
  if [[ -n "$url" ]]; then
    local code
    if code="$(wait_code "$url/" "404" 12)"; then
      echo "  [OK] The old address no longer opens (HTTP 404) / 元のアドレスはもう開けない（HTTP 404）"
    else
      echo "  [WARNING / 注意] After two minutes the old address still returns HTTP $code. gcloud has deleted the service (no error above); run ./s1b_deploy.sh check, which should show \"Service ...: no/なし\". / 2 分後も元のアドレスは HTTP $code。サービスは gcloud が削除済み（上にエラーなし）。./s1b_deploy.sh check を実行すると「Service ...: no/なし」と表示されるはず。"
    fi
  fi
  has_service || rm -f "$SERVICE_FILE"
  rm -f "$URL_FILE" "$ENV_FILE" "$CODE_FILE" "$IMAGE_FILE" "$SA_OK_FILE"
  echo "Test code, service name and address files deleted. The 4 enabled APIs cost nothing and stay on (development still needs them). / テストコード・サービス名・アドレスのファイルを削除した。有効化した 4 つの API は費用がかからないので残す（開発段階でも使う）。"
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
  _stage) [[ -d "${2:-}" ]] || die "Usage: _stage EMPTY_DIR (offline tests only) / 使い方：_stage 空のディレクトリ（オフラインテスト専用）"; stage_ctx "$2" ;;
  *) sed -n '2,40p' "$0"; exit 2 ;;
esac
