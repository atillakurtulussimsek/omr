FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 JOB_DIR=/data/jobs FORMS_DIR=/data/forms
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY omr ./omr
COPY api ./api

RUN useradd --create-home appUser && mkdir -p /data/jobs /data/forms && chown -R appUser /data
USER appUser

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health')"

# iş durumu bellekte tutulduğu için tek worker
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
