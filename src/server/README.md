# Server

A FastAPI server that manages bot instances and provides endpoints for both Daily Prebuilt and Pipecat client connections.

## Running the Server

1. Set up and activate your virtual environment:

```bash
conda create -n riverst python=3.11 -y
conda activate riverst
pip install -r requirements.txt
```

2. Copy `env.example` to `.env` and configure params.

3. Run the server:

```bash
python server.py
```
