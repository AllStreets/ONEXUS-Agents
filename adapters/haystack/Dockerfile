# Image for the confined haystack adapter (see mcp.json "confinement").
# Built and published by .github/workflows/adapter-images.yml.
FROM python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app \
    HAYSTACK_TELEMETRY_ENABLED=False
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --root-user-action=ignore --disable-pip-version-check -r /app/requirements.txt
COPY server.py /app/adapters/haystack/server.py
RUN touch /app/adapters/__init__.py /app/adapters/haystack/__init__.py \
 && python -c "import adapters.haystack.server"
USER 65534:65534
CMD ["python", "-m", "adapters.haystack.server"]
