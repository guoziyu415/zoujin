# S-1b voice proxy image. Built on zg's Mac by s1b_deploy.sh build (linux/amd64), never by Cloud Build.
FROM python:3.12-slim

RUN pip install --no-cache-dir uv==0.11.32 \
 && useradd --system --create-home --uid 10001 app

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY zj_spike ./zj_spike
COPY page ./page

# Nothing is written outside /tmp; there is no ledger to keep (the proxy has its own spend cap).
ENV PYTHONUNBUFFERED=1 ZJ_OUT=/tmp/out ZJ_LEDGER=/tmp/ledger.json ZJ_S1B_STATIC=/app/page

USER app
CMD ["/app/.venv/bin/python", "-m", "zj_spike.s1b_proxy", "serve", "--host", "0.0.0.0"]
