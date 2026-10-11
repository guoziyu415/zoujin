# 网关和叙事者共用的镜像（B-23）。只在 zg 的 Mac 上由 deploy.sh build 构建（linux/amd64），不用 Cloud Build。
# 构建目录由 deploy.sh 拼：仓库这次提交的后端相关目录（git archive）、web/（vite build 的 dist）、scenes/（场景包）。
FROM python:3.13-slim-bookworm
RUN pip install --no-cache-dir uv==0.11.32

RUN useradd --system --create-home --uid 10001 app
WORKDIR /app
ENV UV_LINK_MODE=copy UV_COMPILE_BYTECODE=1 UV_PROJECT_ENVIRONMENT=/app/.venv UV_PYTHON_DOWNLOADS=never PYTHONUNBUFFERED=1

# 先只拷依赖清单装依赖（缓存层），再拷代码。工作区的包要可编辑安装：config.REPO 按源文件的位置找仓库根
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

# 只写 /tmp（账本 ZJ_LEDGER 在这里，跟着实例走）；Cloud Run 给 PORT
ENV ZJ_WEB_DIST=/app/web ZJ_SCENE_PACKS=/app/scenes
USER app
# 默认是网关；叙事者由 deploy.sh 用 --command 换
CMD ["sh", "-c", "exec /app/.venv/bin/zoujin-gateway --host 0.0.0.0 --port ${PORT:-8080}"]
