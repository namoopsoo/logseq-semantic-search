FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1
ENV UV_COMPILE_BYTECODE=1
ENV HF_HOME=/models/huggingface
ENV TRANSFORMERS_CACHE=/models/huggingface
ENV SENTENCE_TRANSFORMERS_HOME=/models/sentence-transformers

COPY pyproject.toml ./

RUN uv sync --no-dev

COPY src favicon-61f4ee969f89f9936688a6c49b63173679a18780_2_1000x1000.jpeg ./

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
