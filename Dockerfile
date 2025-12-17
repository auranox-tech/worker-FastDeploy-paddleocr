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
RUN pip install --upgrade pip

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

# ---- offline model env ----
ENV BUILD_FOR_OFFLINE=true

RUN mkdir -p "$PADDLEX_HOME/fonts" && \
    (if [[ "${BUILD_FOR_OFFLINE,,}" == "true" ]]; then \
      set -e; \
      declare -A MODELS=( \
        ["UVDoc"]="https://paddle-model-ecology.bj.bcebos.com/paddlex/official_inference_model/paddle3.0.0/UVDoc_infer.tar" \
        ["PP-LCNet_x1_0_doc_ori"]="https://paddle-model-ecology.bj.bcebos.com/paddlex/official_inference_model/paddle3.0.0/PP-LCNet_x1_0_doc_ori_infer.tar" \
        ["PP-DocLayoutV2"]="https://paddle-model-ecology.bj.bcebos.com/paddlex/official_inference_model/paddle3.0.0/PP-DocLayoutV2_infer.tar" \
        ["PaddleOCR-VL-0.9B"]="https://paddle-model-ecology.bj.bcebos.com/paddlex/official_inference_model/paddle3.0.0/PaddleOCR-VL_infer.tar" \
      ); \
      \
      for MODEL_NAME in "${!MODELS[@]}"; do \
        URL="${MODELS[$MODEL_NAME]}"; \
        TAR_PATH="$PADDLEX_MODEL_HOME/${MODEL_NAME}.tar"; \
        MODEL_DIR="$PADDLEX_MODEL_HOME/${MODEL_NAME}"; \
        \
        if [[ -d "$MODEL_DIR" ]]; then \
          echo "✓ $MODEL_NAME already exists, skipping."; \
          continue; \
        fi; \
        \
        echo "▶ Downloading $MODEL_NAME"; \
        wget -q "$URL" -O "$TAR_PATH"; \
        \
        echo "▶ Extracting $MODEL_NAME"; \
        tar -xf "$TAR_PATH" -C "$PADDLEX_MODEL_HOME"; \
        \
        FILENAME="$(basename "$URL")"; \
        EXTRACTED_DIR="${FILENAME%.tar}"; \
        \
        if [[ -d "$PADDLEX_MODEL_HOME/$EXTRACTED_DIR" ]]; then \
          mv "$PADDLEX_MODEL_HOME/$EXTRACTED_DIR" "$MODEL_DIR"; \
        else \
          ROOT_DIR="$(tar -tf "$TAR_PATH" | head -n1 | cut -d/ -f1)"; \
          mv "$PADDLEX_MODEL_HOME/$ROOT_DIR" "$MODEL_DIR"; \
        fi; \
        \
        rm -f "$TAR_PATH"; \
      done; \
      \
      FONT_URL="https://paddle-model-ecology.bj.bcebos.com/paddlex/PaddleX3.0/fonts/PingFang-SC-Regular.ttf"; \
      FONT_PATH="$PADDLEX_HOME/fonts/PingFang-SC-Regular.ttf"; \
      \
      if [[ ! -f "$FONT_PATH" ]]; then \
        echo "▶ Downloading font"; \
        wget -q "$FONT_URL" -O "$FONT_PATH"; \
      fi; \
      \
      echo "✅ Offline PaddleOCR-VL models ready."; \
    else \
      echo "Offline build disabled, skipping."; \
    fi)

# Copy handler
COPY /src/handler.py /src/handler.py
CMD ["python3", "/src/handler.py"]
