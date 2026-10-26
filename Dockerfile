# syntax=docker/dockerfile:1

FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8501

WORKDIR /app

# System deps occasionally needed by crewai/chroma transitive packages.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .

EXPOSE 8501

# Streamlit Cloud sets $PORT; honour it, default to 8501 locally.
CMD ["sh", "-c", "streamlit run streamlit_app/app.py --server.port=${PORT:-8501} --server.address=0.0.0.0 --server.headless=true"]
