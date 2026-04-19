# Riverst server

## Getting started

1. Set up and activate your virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
```

2. Install python dependencies
```bash
pip install -r requirements.txt
```

For a GPU-oriented Linux deployment, install:
```bash
pip install -r requirements.gpu.txt
```

3. Copy `env.example` to `.env` and configure params:
   - Set your `OPENAI_API_KEY` for LLM and TTS services
   - Set your env variables (you can follow the instructions in the `.env.example` file)
   - Set `RIVERST_COMPUTE_DEVICE=cpu` if you want to disable GPU/MPS usage at runtime

**Note**: Not all API KEYS are strictly required. Only if you want to use a remote service, you need to expose the corresponding API KEY

**Note**: `.env` is gitignored for security

**Note**: Using OpenAI for all of the services with a free user plan will likely cause a Pipecat 500 issue shortly after generating a session as OpenAI rate limits free users to 3 requests per minute, which the initial setup of the models alone might exceed.

**Note**: The HuggingFace API key is not necessary for all models, but adding the key will allow access to models that might be gated behind permission requests or even your own private models. A `Read` token should allow this, but if you would like to use a more fine-grained access token for security reasons, then you should enable:
- `Make calls to Inference Providers` under `Inference`
- `Read access to contents of all public gated repos you can access` under `Repositories`

4. [Optional] If you want to use Google authentication (ENABLE_GOOGLE_AUTH is `true`), you need to set it up:
   - Copy `authorization/authorized_users.json.example` to `authorization/authorized_users.json`
   - Add authorized user email addresses to the JSON array

**Note**: `authorization/authorized_users.json` is gitignored for security

5. [Optional] If you want to use local LLMs through `ollama` (e.g., `qwen3`), you need first to [install ollama on your machine](https://ollama.com/) and then run

```bash
ollama pull <model_uri>
```

For instance,
```bash
ollama pull qwen3:4b-instruct-2507-q4_K_M
```

6. Run the server:
```bash
python main.py
```


### Alternative approache to run the server script with Docker
```bash
docker build --no-cache -t fastapi-server .
docker run -p 7860:7860 --env-file .env fastapi-server
```

To build a GPU-oriented image instead:

```bash
docker build --no-cache --build-arg RIVERST_DEPLOYMENT_TARGET=gpu -t fastapi-server .
docker run --gpus all -p 7860:7860 --env-file .env fastapi-server
```
