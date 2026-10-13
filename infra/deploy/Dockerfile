# The image shared by the gateway and the narrator (B-23). Built only on zg's Mac by deploy.sh build (linux/amd64), not with Cloud Build.
# ゲートウェイとナレーターが共用するイメージ（B-23）。zg の Mac 上で deploy.sh build によってのみビルドし（linux/amd64）、Cloud Build は使わない。
# deploy.sh assembles the build directory: the backend-related directories of this commit (git archive), web/ (vite build's dist), scenes/ (scene packs).
# ビルドディレクトリは deploy.sh が組み立てる：このコミットのバックエンド関連ディレクトリ（git archive）、web/（vite build の dist）、scenes/（シーンパック）。
FROM python:3.13-slim-bookworm
RUN pip install --no-cache-dir uv==0.11.32

RUN useradd --system --create-home --uid 10001 app
WORKDIR /app
ENV UV_LINK_MODE=copy UV_COMPILE_BYTECODE=1 UV_PROJECT_ENVIRONMENT=/app/.venv UV_PYTHON_DOWNLOADS=never PYTHONUNBUFFERED=1

# Copy only the dependency manifests and install dependencies first (cache layer), then copy the code. Workspace packages need
# an editable install: config.REPO finds the repo root from the source files' location
# まず依存関係の一覧だけをコピーして依存をインストールし（キャッシュレイヤー）、そのあとコードをコピーする。workspace のパッケージは
# 編集可能インストールが必要：config.REPO はソースファイルの場所からリポジトリのルートを探す
COPY pyproject.toml uv.lock ./
COPY services/backend/pyproject.toml services/backend/
COPY packages/worldsim/pyproject.toml packages/worldsim/
COPY packages/contracts/pyproject.toml packages/contracts/
COPY packages/llm/pyproject.toml packages/llm/
COPY evals/pyproject.toml evals/
RUN uv sync --frozen --no-dev --extra real --package zoujin-backend --no-install-workspace \
 && rm -rf /root/.cache/uv
COPY . .
RUN uv sync --frozen --no-dev --extra real --package zoujin-backend \
 && rm -rf /root/.cache/uv

# Writes only to /tmp (the ledger ZJ_LEDGER lives here and goes with the instance); Cloud Run provides PORT
# 書き込むのは /tmp だけ（台帳 ZJ_LEDGER はここにあり、インスタンスと運命を共にする）。PORT は Cloud Run が与える
ENV ZJ_WEB_DIST=/app/web ZJ_SCENE_PACKS=/app/scenes
USER app
# Defaults to the gateway; deploy.sh switches to the narrator with --command
# デフォルトはゲートウェイ。ナレーターは deploy.sh が --command で切り替える
CMD ["sh", "-c", "exec /app/.venv/bin/zoujin-gateway --host 0.0.0.0 --port ${PORT:-8080}"]
