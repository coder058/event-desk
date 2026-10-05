FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
# SOURCE: one BLAS thread avoids per-job native oversubscription on the existing small VPS.
WORKDIR /app
COPY pyproject.toml .
COPY constraints.txt .
COPY src src
RUN pip install --no-cache-dir -c constraints.txt .
COPY alembic.ini .
COPY migrations migrations
COPY research research
COPY fixtures fixtures
RUN useradd --uid 10001 --create-home eventdesk
# GUESS: isolated unprivileged application UID; no relation to model calibration.
USER eventdesk
CMD ["uvicorn", "eventdesk.api:app_factory", "--factory", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
