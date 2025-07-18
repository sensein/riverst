# Server

A FastAPI server.

## Running the Server

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

2. Inside of this folder (the server folder), clone the repo with the smart_turn_classifier.mlpackage
```bash
git clone https://huggingface.co/pipecat-ai/smart-turn-v2
```

3. Copy `env.example` to `.env` and configure params.

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
python server.py
```
