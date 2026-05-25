# ============================================================
# Codex2DeepSeek — 跨平台多阶段构建
# ============================================================
# 构建:
#   docker build -t codex2deepseek:latest .
#   docker buildx build --platform linux/amd64,linux/arm64 -t codex2deepseek:latest .
#
# 运行:
#   docker compose -f docker/docker-compose.yml up -d
# ============================================================

# ---- 构建阶段 ----
# 使用与运行时相同的 slim 基镜像，避免 musl/glibc 不兼容问题
FROM docker.m.daocloud.io/python:3.12-slim AS builder

WORKDIR /build

# 安装 uv
# 国内镜像加速: ghcr.nju.edu.cn
COPY --from=ghcr.nju.edu.cn/astral-sh/uv:latest /uv /usr/local/bin/uv

# 利用 Docker 层缓存：先复制依赖声明
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# 复制源码
COPY app/ ./app/
COPY routers/ ./routers/
COPY services/ ./services/
COPY main.py ./

# 重新 sync 以链接本地包
RUN uv sync --frozen --no-dev


# ---- 运行时阶段 ----
FROM docker.m.daocloud.io/python:3.12-slim

WORKDIR /app

# 安装 ca-certificates 确保 HTTPS 请求正常
# 使用国内 apt 镜像源加速
RUN sed -i 's/deb.debian.org/mirrors.ustc.edu.cn/g' /etc/apt/sources.list.d/debian.sources 2>/dev/null ||     sed -i 's/deb.debian.org/mirrors.ustc.edu.cn/g' /etc/apt/sources.list 2>/dev/null;     apt-get update -qq && apt-get install -y -qq --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# 从 builder 复制已安装的 venv 和源码
COPY --from=builder /build/.venv /app/.venv
COPY --from=builder /build/main.py /app/main.py
COPY --from=builder /build/app/ /app/app/
COPY --from=builder /build/routers/ /app/routers/
COPY --from=builder /build/services/ /app/services/

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 12345

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import socket; socket.create_connection(('localhost', 12345), timeout=5).close()" || exit 1

ENTRYPOINT ["python", "main.py"]
