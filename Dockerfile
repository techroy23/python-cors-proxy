FROM python:3.12-alpine

RUN apk add --no-cache \
      build-base \
      libffi-dev \
      curl \
      bash

WORKDIR /app

COPY app.py /app/app.py

RUN pip install --no-cache-dir \
      flask \
      requests \
      fake_useragent \
      gunicorn

ENV PORT=3000 \
    HOST=0.0.0.0 \
    USE_GUNICORN=true

EXPOSE 3000

CMD if [ "$USE_GUNICORN" = "true" ]; then \
      gunicorn -w ${WORKERS:-$(nproc)} -b 0.0.0.0:$PORT --log-level ${LOG_LEVEL:-info} app:app; \
    else \
      python app.py; \
    fi
