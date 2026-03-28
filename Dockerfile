FROM python:3.11-slim

WORKDIR /workspace

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy OpenDartReader package source
COPY . /workspace/OpenDartReader

# Cache directory for corp codes
RUN mkdir -p /workspace/OpenDartReader/docs_cache

# PYTHONPATH=/workspace so `import OpenDartReader` resolves to /workspace/OpenDartReader/
ENV PYTHONPATH=/workspace
ENV DART_API_KEY=""

EXPOSE 8000

# app.main resolves to /workspace/OpenDartReader/app/main.py via uvicorn's sys.path (cwd=/workspace/OpenDartReader)
WORKDIR /workspace/OpenDartReader
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
