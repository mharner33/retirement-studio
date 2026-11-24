FROM node:26 AS dashboard
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --ignore-scripts
COPY dashboard ./dashboard
RUN npx vite build dashboard

FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev --no-install-project
COPY backend ./backend
COPY agent ./agent
COPY --from=dashboard /app/dashboard/dist ./dashboard/dist
ENV DATA_DIR=/data PATH="/app/.venv/bin:$PATH"
EXPOSE 8000
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
