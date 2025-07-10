# Server

A FastAPI server.

## Running the Server

1. Set up and activate your virtual environment:

```bash
conda create -n riverst python=3.11 -y
conda activate riverst
```

2. Copy `env.example` to `.env` and configure params.

3. [OPTIONAL] If you want to use `llama3.2` (or any `ollama` llm), you should first [install ollama on your machine](https://ollama.com/) and then run

```bash
ollama run llama3.2
```

4. Run the server:

```bash
python server.py
```

