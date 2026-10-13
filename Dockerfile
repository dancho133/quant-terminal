FROM ghcr.io/astral-sh/uv:0.12.3 AS uv
FROM python:3.12-slim
COPY --from=uv /uv /uvx /bin/
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY quant_terminal ./quant_terminal
RUN uv sync --locked --no-dev
EXPOSE 8501
CMD ["uv", "run", "--locked", "streamlit", "run", "quant_terminal/dashboard/app.py", "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true", "--browser.gatherUsageStats=false"]
