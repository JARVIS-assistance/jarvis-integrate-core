FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/models/huggingface \
    TRANSFORMERS_CACHE=/models/huggingface \
    MECABRC=/etc/mecabrc

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        git \
        libsndfile1 \
        sox \
        libsox-fmt-all \
        libespeak-ng1 \
        espeak-ng-data \
        mecab \
        libmecab-dev \
        mecab-ipadic-utf8 \
    && mkdir -p /usr/local/etc \
    && ln -sf /etc/mecabrc /usr/local/etc/mecabrc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN python -m pip install --upgrade pip setuptools wheel \
    && python -m pip install --index-url https://download.pytorch.org/whl/cpu torch==2.8.0 torchaudio==2.8.0 \
    && python -m pip install --no-build-isolation -r /app/requirements.txt

ARG INSTALL_MELOTTS=0
ARG INSTALL_PIPER_TTS=0
RUN if [ "$INSTALL_MELOTTS" = "1" ]; then \
        python -m pip install --no-build-isolation \
            txtsplit \
            cached_path \
            num2words==0.5.12 \
            unidic_lite==1.0.8 \
            mecab-python3==1.0.9 \
            pykakasi==2.2.1 \
            "fugashi>=1.5.2" \
            g2p_en==2.1.0 \
            anyascii==0.3.2 \
            jamo==0.4.1 \
            "gruut[de,es,fr]==2.2.3" \
            "g2pkk>=0.1.1" \
            pydub==0.25.1 \
            eng_to_ipa==0.0.2 \
            inflect==7.0.0 \
            unidecode==1.3.7 \
            pypinyin==0.50.0 \
            cn2an==0.5.22 \
            jieba==0.42.1 \
            langid==1.1.6 \
            tqdm \
            tensorboard==2.16.2 \
            loguru==0.7.2 \
        && python -m pip install "setuptools<81" \
        && python -m pip install --no-deps --no-build-isolation "git+https://github.com/myshell-ai/MeloTTS.git"; \
    fi
RUN if [ "$INSTALL_PIPER_TTS" = "1" ]; then \
        python -m pip install --no-build-isolation "piper-tts>=1.3.0"; \
    fi

COPY app.py /app/app.py

EXPOSE 8031

CMD ["python", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8031"]
