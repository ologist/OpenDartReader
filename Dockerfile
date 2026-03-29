FROM python:3.11-slim

WORKDIR /workspace

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy opendart-mcp package source
COPY . /workspace/opendart-mcp

# Cache directory for corp codes
RUN mkdir -p /workspace/opendart-mcp/docs_cache

# Python은 하이픈 디렉토리를 import할 수 없으므로 underscore symlink 생성
RUN ln -s /workspace/opendart-mcp/opendart_mcp /workspace/opendart_mcp

# PYTHONPATH=/workspace so `import opendart_mcp` resolves to /workspace/opendart_mcp/
ENV PYTHONPATH=/workspace
ENV DART_API_KEY=""

EXPOSE 8000

# app.main resolves to /workspace/opendart-mcp/app/main.py via uvicorn's sys.path (cwd=/workspace/opendart-mcp)
WORKDIR /workspace/opendart-mcp
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
