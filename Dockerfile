FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Install Deno (required by yt-dlp for YouTube JS extraction)
RUN curl -fsSL https://deno.land/install.sh | DENO_INSTALL=/usr/local sh

WORKDIR /app

# ---- Key optimization: Install PyTorch CPU-only FIRST ----
# Default torch pulls CUDA libs (~5-8GB). CPU-only is ~200MB.
# The backend only serves API — no GPU needed in container.
RUN pip install --no-cache-dir \
    torch==2.7.0 --index-url https://download.pytorch.org/whl/cpu

# Install deps (cached if pyproject.toml unchanged)
COPY pyproject.toml ./
RUN mkdir -p src scripts && \
    touch src/__init__.py scripts/__init__.py && \
    pip install --no-cache-dir . && \
    rm -rf src scripts build *.egg-info

# Copy source and install package (no deps, fast)
COPY src/ src/
COPY scripts/ scripts/
RUN pip install --no-cache-dir --no-deps .

# Non-root user with home dir (needed for HuggingFace model cache)
RUN useradd -r -m -s /bin/false appuser && \
    mkdir -p output data/chroma && \
    chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
