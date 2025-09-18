# Server

A FastAPI server.

## Running the server

1. Set up and activate your virtual environment:

```bash
conda create -n riverst python=3.11 -y
conda activate riverst
```

If you intend to use `piper`, you do:

```bash
pip install --no-deps piper-tts && pip install -r requirements.txt
```

Otherwise, it's enough to do:

```bash
pip install -r requirements.txt
```

2. Copy `env.example` to `.env` and configure params:
   - Set your `OPENAI_API_KEY` for LLM and TTS services
   - Configure Google OAuth credentials (`GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`)
   - Add other API keys as needed (Google, ElevenLabs, etc.)

3. Set up authentication:
   - Copy `authorization/authorized_users.json.example` to `authorization/authorized_users.json`
   - Add authorized user email addresses to the JSON array
   - This file is gitignored for security

4. [OPTIONAL] If you want to use `llama3.2` (or any `ollama` llm), you should first [install ollama on your machine](https://ollama.com/) and then run

```bash
ollama run llama3.2
```

5. [OPTIONAL] If you want to use `piper`, you should first download the voice model(s) you want from [here](https://github.com/rhasspy/piper/blob/9b1c6397698b1da11ad6cca2b318026b628328ec/VOICES.md) and then run

```bash
git clone https://github.com/rhasspy/piper.git
cd piper/src/python_run
python3 -m piper.http_server --model <path_to_voices_folder>/en_GB-alba-medium.onnx --port 5001
python3 -m piper.http_server --model <path_to_voices_folder>/en_GB-alan-medium.onnx --port 5002
```

6. Run the server:

```bash
python main.py
```



## Alternative approache to run the server script with Docker

```bash
docker build --no-cache -t fastapi-server .
docker run -p 7860:7860 --env-file .env fastapi-server
```
