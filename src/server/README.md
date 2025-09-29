# Riverst server

## Getting started

1. Set up and activate your virtual environment:

```bash
conda create -n riverst python=3.11 -y
conda activate riverst
```

2. Install python dependencies
```bash
pip install -r requirements.txt
```

3. Copy `env.example` to `.env` and configure params:
   - Set your `OPENAI_API_KEY` for LLM and TTS services
   - Set your env variables (you can follow the instructions in the `.env.example` file)

**Note**: Not all API KEYS are strictly required. Only if you want to use a remote service, you need to expose the corresponding API KEY
**Note**: `.env` is gitignored for security

4. [Optional] If you want to use Google authentication (ENABLE_GOOGLE_AUTH is `true`), you need to set it up:
   - Copy `authorization/authorized_users.json.example` to `authorization/authorized_users.json`
   - Add authorized user email addresses to the JSON array

**Note**: `authorization/authorized_users.json` is gitignored for security

5. [Optional] If you want to use local LLMs through `ollama` (e.g., `qwen3`), you need first to [install ollama on your machine](https://ollama.com/) and then run

```bash
ollama run <model_uri>
```

For instance,
```bash
ollama run ollama/qwen3:4b-instruct-2507-q4_K_M
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
