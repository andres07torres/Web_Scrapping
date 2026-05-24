FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    wget gnupg ca-certificates \
    libglib2.0-0 libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libdrm2 libdbus-1-3 libxkbcommon0 libxcomposite1 \
    libxdamage1 libxfixes3 libxrandr2 libgbm1 libpango-1.0-0 \
    libcairo2 libasound2 libgtk-3-0 \
    && rm -rf /var/lib/apt/lists/*

COPY proyecto/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN playwright install chromium

COPY proyecto/ .

EXPOSE 5000

ENV FLASK_ENV=production
ENV PYTHONUNBUFFERED=1

CMD ["sh", "-c", "gunicorn web_app:app --bind 0.0.0.0:${PORT:-5000} --workers 2 --timeout 120 --access-logfile - --error-logfile -"]
