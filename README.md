# Riverst

![Avatar screenshot](public/fabio_says_hi.png)

## Do you need/want to...

- build interactive user-avatar experiences (speech-based, with video/multimodal support)?
- collect high-quality conversational data for research or industry projects?
- automatically analyze conversations for behavioral, linguistic, or engagement metrics?

| Session overview | Automated analysis summary |
|---|---|
| ![Session overview](public/session_summary_example.png) | ![Automated analysis](public/automated_audio_analysis.png) |


**If so, Riverst is for you.**

---

## Video demos

| Video Demo | Description |
|---|---|
| [Riverst Demo](https://drive.google.com/file/d/1r2LoBGbjBx1mdDIv-fPzGeZVEYf1kLw8/view?usp=sharing) | Demo of the Riverst platform in action. What can I do with Riverst? |
| [KIVA Activity Demo](https://drive.google.com/file/d/1jTHvTXG4WWIYqgqjC4lp1LWMEnyZJQzr/view?usp=sharing) | Demonstration of a vocabulary teaching activity workflow, exploiting pipecat-ai-flows under the hood. |
| [Riverst + KIVA Activity Summary](https://drive.google.com/file/d/1AvYnSq87neOYj_YSduYatN5D4rdO-7QG/view?usp=sharing) | Overview and summary of configuration pages in Riverst and automatically generated summary of the KIVA activity. |


---

## What is Riverst?

Riverst is a platform for building, running, and analyzing interactive user-avatar conversations. It enables you to:

- Create engaging, speech-driven (and optionally multimodal) avatar interactions.
- Use these interactions for real-time applications, data collection, or research studies.
- Automatically process and analyze collected conversations with built-in pipelines (leveraging [senselab](https://github.com/sensein/senselab)) for behavioral and speech analysis.

---

## How it works

1. **User interacts with an avatar** (primarily via speech, with optional video/multimodal input).
2. **Conversations are recorded and stored** for later review or analysis.
3. **Automated pipelines** process the data, extracting features and generating insights (e.g., speech metrics, behavioral markers).
4. **Results can be used** for research, product feedback, or to power adaptive experiences.

---

## Project Structure

```
src/
├── server/              # Bot server implementation (FastAPI)
│   ├── main.py          # Server entrypoint
│   └── requirements.txt
└── flow-builder/        # Complex conversational flow/tree builder
└── client/              # Client implementations
    └── react/           # React web client
        └── index.html   # Client main page

```

---

## Requirements

- **Supported OS:**
  - ✅ Apple Silicon (M-chip) macOS
  - ✅ Ubuntu Linux
  - ❌ Not supported on Windows

- Python 3.11+
- Node.js 16+ (for React client)
- API keys for 3rd party services (see .env.example files in both client and server)
- Modern web browser with WebRTC support (e.g., Chrome 134+)

---

## Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/sensein/riverst.git
cd riverst
```

### 2. Set up environment variables

- In `src/server/`, rename [`.env.example`](src/server/env.example) to `.env` and fill in the required API keys and configuration
- In `src/client/react/`, rename [`.env.example`](src/client/react/env.example) to `.env` and fill in the required API keys and configuration

More detailed instructions for setting up the [client](src/client/react/README.md) and [server](src/server/README.md) can be found in their respective README documents.

**Note**: Not all API KEYS are strictly required. Only if you want to use a remote service, you need to expose the corresponding API KEY

**Note**: If you want to run local models, you will need to have Ollama or another method for running models locally. Please see [#5 under Getting Started for the server setup](src/server/README.md#getting-started).

### 3. Run

#### 3a. Run with Docker

```bash
docker compose up --build
```

This default Docker setup builds the server for CPU / non-GPU deployment.

To build with GPU-oriented extras and request a GPU-enabled container runtime:

```bash
docker compose -f docker-compose.yaml -f docker-compose.gpu.yaml up --build
```

#### 3b. Run manually in two different tabs of your terminal (recommended)

- **Start the server:**
  ```bash
  cd src/server
  conda create -n riverst python=3.11
  conda activate riverst
  conda install -c conda-forge "ffmpeg=7.*"
  pip install -r requirements.txt
  python main.py
  ```

  For a GPU-oriented install on Linux, use:
  ```bash
  pip install -r requirements.gpu.txt
  ```

  To force local inference onto CPU even on a machine with an accelerator, set:
  ```bash
  export RIVERST_COMPUTE_DEVICE=cpu
  ```

- **Start the client:**
  ```bash
  cd src/client/react
  npm install
  npm run dev
  ```

⚠️ **Note:** The server must be running before starting the client.

ℹ️ **Note 2:** For AWS EC2 deployment instructions, see [here](notes/first_steps_to_deploy.md).

### 4. Run into issues?

It's possible some issues might have arisen along the way. Feel free to post an issue asking for help as well as check out our [Common Pitfalls Guide](notes/common_pitfalls.md) for some issues that we have seen pop up.

---

## 🙏 Acknowledgments

Riverst builds on the work of these fantastic open-source projects:

- **[TalkingHead](https://github.com/met4citizen/TalkingHead)** — WebGL/Three.js talking-head renderer for avatar animation.
- **[Contextless Phonemes (CUPE)](https://github.com/tabahi/contexless-phonemes-CUPE)** — Efficient phoneme modeling utilities.
- **[Pipecat](https://github.com/pipecat-ai/pipecat)** — Real-time, multimodal agent framework for low-latency streaming.
- **[senselab](https://github.com/sensein/senselab)** — Python package for speech processing, feature extraction, and behavioral analysis.

---

## Project board

The project is in continuous progress. Follow [the project plan here](https://github.com/orgs/sensein/projects/55).
