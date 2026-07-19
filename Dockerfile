# Obraz dev dla wariantu GPU (serwer popos, RTX 5070 Ti / Blackwell).
# Dystrybucja koncowa pozostaje pyinstaller — ten obraz sluzy wylacznie wygodzie developmentu.
FROM nvidia/cuda:12.8.1-cudnn-runtime-ubuntu24.04

ENV DEBIAN_FRONTEND=noninteractive \
    ECHO_HOST=0.0.0.0 \
    XDG_DATA_HOME=/data \
    PATH="/opt/venv/bin:${PATH}"

RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 \
        python3-pip \
        python3-venv \
        libpython3.12t64 \
        ffmpeg \
    && rm -rf /var/lib/apt/lists/* \
    && python3 -m venv /opt/venv

WORKDIR /app

COPY pyproject.toml README.md constraints-gpu.txt ./
COPY src ./src
COPY scripts ./scripts

RUN pip install --extra-index-url https://download.pytorch.org/whl/cu128 -c constraints-gpu.txt -e ".[local]"

EXPOSE 8765

CMD ["uvicorn", "echo_app.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8765"]
