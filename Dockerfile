FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1
WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends mc curl && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

RUN groupadd --system --gid 10001 nicedice && \
    useradd --system --uid 10001 --gid nicedice --home-dir /app --shell /usr/sbin/nologin nicedice && \
    mkdir -p /app/staticfiles && \
    chown -R nicedice:nicedice /app

COPY --chown=nicedice:nicedice . .
COPY --chown=root:root scripts/entrypoint.sh /entrypoint.sh
RUN chmod 0555 /entrypoint.sh

USER nicedice

ENTRYPOINT ["/entrypoint.sh"]
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
