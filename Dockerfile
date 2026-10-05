FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
# SOURCE: one BLAS thread avoids per-job native oversubscription on the existing small VPS.
WORKDIR /app
COPY pyproject.toml .
COPY constraints.txt .
# SOURCE: runtime dependencies and build-backend requirement come from pyproject.toml.
# Cache the large scientific dependency layer independently of source edits on the existing small VPS.
RUN python -c "import subprocess,sys,tomllib;from pathlib import Path;c=tomllib.loads(Path('pyproject.toml').read_text());subprocess.check_call([sys.executable,'-m','pip','install','--no-cache-dir','-c','constraints.txt',*c['project']['dependencies'],*c['build-system']['requires'],'wheel'])"
COPY src src
RUN pip install --no-cache-dir --no-deps --no-build-isolation .
COPY alembic.ini .
COPY migrations migrations
COPY research research
COPY fixtures fixtures
RUN useradd --uid 10001 --create-home eventdesk
# GUESS: isolated unprivileged application UID; no relation to model calibration.
USER eventdesk
CMD ["uvicorn", "eventdesk.api:app_factory", "--factory", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
