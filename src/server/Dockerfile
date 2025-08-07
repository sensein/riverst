# Stage 1: Base Python image
FROM python:3.11

# Set working directory
WORKDIR /app

# System packages and Rust installation
RUN apt-get update && apt-get install -y --no-install-recommends \
    git build-essential g++ curl \
    libgl1 libglib2.0-0 ffmpeg \
    && curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y \
    && rm -rf /var/lib/apt/lists/*

# Copy application code
COPY . .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt


# Expose port
EXPOSE 7860

# Run the application
CMD ["python", "main.py"]
