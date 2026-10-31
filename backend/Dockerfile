# LegalLens backend image for Render. Build context is the repo root (render.yaml),
# so docs/ (ML metrics page) is available next to backend/.
FROM python:3.12-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends libglib2.0-0 libgl1 \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /srv

# CPU-only PyTorch: the default wheel bundles CUDA and is several GB larger.
RUN pip install --no-cache-dir torch==2.14.0 torchvision==0.29.0 --index-url https://download.pytorch.org/whl/cpu

COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# Bake the EasyOCR models into the image so a cold start doesn't download them.
RUN python -c "import easyocr; easyocr.Reader(['en', 'hi'], gpu=False)"

COPY backend/ backend/
COPY docs/ docs/

WORKDIR /srv/backend
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
