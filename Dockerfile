FROM nvidia/cuda:12.1.0-base-ubuntu22.04

RUN apt-get update -y \
    && apt-get install -y python3-pip

RUN ldconfig /usr/local/cuda-12.1/compat/

# ---- environment ----
ENV PIP_NO_CACHE_DIR=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PATH=$PATH:/usr/local/bin

# ---- install system dependencies ----
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        cmake \
        git \
        wget \
        python3-dev \
        libglib2.0-0 \
        libsm6 \
        libxext6 \
        libxrender1 \
    && rm -rf /var/lib/apt/lists/*

# ---- python tooling ----
RUN pip install --upgrade pip setuptools wheel

# Install Python dependencies
COPY builder/requirements.txt /requirements.txt
RUN --mount=type=cache,target=/root/.cache/pip \
    python3 -m pip install --upgrade pip && \
    python3 -m pip install --upgrade -r /requirements.txt

RUN python3 -m pip install paddlepaddle-gpu==3.2.1 -i https://www.paddlepaddle.org.cn/packages/stable/cu126/

# ---- install PaddleOCR and PaddleX ----
RUN python3 -m pip install --no-cache-dir "paddleocr[doc-parser]" "paddlex==3.3.11"


# ---- install safetensors for CUDA 12.6 ----
RUN python3 -m pip install --no-cache-dir https://paddle-whl.bj.bcebos.com/nightly/cu126/safetensors/safetensors-0.6.2.dev0-cp38-abi3-linux_x86_64.whl

ENV DISABLE_MODEL_SOURCE_CHECK=True

# ---- install PaddleX serving ----
RUN paddlex --install serving || (pip list && python -c "import paddlex; print(paddlex.__version__)" && exit 1)


# ---- environment variables for offline cache ----
ENV HOME=/home/paddleocr
ENV PADDLEX_HOME=/home/paddleocr/.paddlex
ENV PADDLEX_MODEL_HOME=/home/paddleocr/.paddlex/official_models
ENV HF_HOME=/home/paddleocr/.cache/huggingface
ENV TRANSFORMERS_CACHE=/home/paddleocr/.cache/huggingface
ENV DISABLE_MODEL_SOURCE_CHECK=True

WORKDIR /home/paddleocr

# Create directories for offline cache
RUN mkdir -p $HOME
RUN mkdir -p $PADDLEX_HOME
RUN mkdir -p $PADDLEX_MODEL_HOME
RUN mkdir -p $HF_HOME
RUN mkdir -p $TRANSFORMERS_CACHE

# Copy handler
COPY /src/handler.py /src/handler.py
CMD ["python3", "/src/handler.py"]
