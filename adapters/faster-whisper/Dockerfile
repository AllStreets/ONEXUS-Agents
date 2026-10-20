# Image for the confined faster-whisper adapter (see mcp.json "confinement").
# The Whisper base model is fetched here, at build time, so the running container
# needs no network. Built and published by .github/workflows/adapter-images.yml.
FROM python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app \
    HF_HUB_DISABLE_TELEMETRY=1 WHISPER_MODEL_DIR=/models/base
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --root-user-action=ignore --disable-pip-version-check -r /app/requirements.txt
RUN python -c "from faster_whisper import download_model; download_model('base', output_dir='/models/base')" \
 && chmod -R a+rX /models
COPY server.py /app/adapters/faster_whisper/server.py
RUN touch /app/adapters/__init__.py /app/adapters/faster_whisper/__init__.py \
 && python -c "import adapters.faster_whisper.server"
USER 65534:65534
CMD ["python", "-m", "adapters.faster_whisper.server"]
