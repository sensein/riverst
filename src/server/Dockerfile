# Stage 1: Base Python image
FROM python:3.12

# Set working directory
WORKDIR /app

ARG RIVERST_DEPLOYMENT_TARGET=cpu
ENV RIVERST_DEPLOYMENT_TARGET=${RIVERST_DEPLOYMENT_TARGET}

# System packages and Rust installation
RUN apt-get update && apt-get install -y --no-install-recommends \
    git build-essential g++ curl \
    libgl1 libglib2.0-0 ffmpeg \
    && curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y \
    && rm -rf /var/lib/apt/lists/*

# Copy application code
COPY . .

# Install dependencies for the selected deployment target
RUN case "$RIVERST_DEPLOYMENT_TARGET" in \
      cpu) requirements_file="requirements.txt" ;; \
      gpu) requirements_file="requirements.gpu.txt" ;; \
      *) echo "Unsupported RIVERST_DEPLOYMENT_TARGET: $RIVERST_DEPLOYMENT_TARGET" >&2; exit 1 ;; \
    esac \
    && pip install --no-cache-dir -r "$requirements_file"


# Expose port
EXPOSE 7860

# Run the application
CMD ["python", "main.py"]
