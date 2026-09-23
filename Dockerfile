FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# System deps for some ML libs (xgboost needs libgomp)
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code and models
COPY Frontend ./Frontend
COPY models ./models

ENV PORT=8080
EXPOSE 8080

CMD ["sh", "-c", "gunicorn --chdir Frontend app:app --bind 0.0.0.0:${PORT} --workers 1 --timeout 120"]


