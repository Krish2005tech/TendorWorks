FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir uv
COPY pyproject.toml uv.lock ./
COPY src ./src
RUN uv sync --frozen --no-dev
COPY database/README.md ./database/README.md
RUN useradd --create-home tender && mkdir -p /app/var && chown -R tender:tender /app
USER tender
EXPOSE 8000
CMD [".venv/bin/tender", "serve", "--host", "0.0.0.0", "--port", "8000"]
