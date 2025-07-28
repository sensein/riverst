# Stage 1: Base Python image
FROM python:3.11

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PATH="/root/.cargo/bin:$PATH"

# Set working directory
WORKDIR /app

# System packages and Rust installation
RUN apt-get update && apt-get install -y --no-install-recommends \
    git build-essential g++ curl \
    libgl1 libglib2.0-0 ffmpeg \
    && curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install them
COPY requirements.txt .
# RUN pip install --prefer-binary --no-cache-dir --no-deps piper-tts
RUN pip install --prefer-binary --no-cache-dir -r requirements.txt

# Clone smart-turn-v2 if not already committed
# RUN git clone https://huggingface.co/pipecat-ai/smart-turn-v2

# Copy application code
COPY . .

# Expose port
EXPOSE 7860

# Run the application
CMD ["python", "main.py"]
