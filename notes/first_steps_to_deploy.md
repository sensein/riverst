# First steps to deploy riverst

This guide explains step-by-step how to deploy the Riverst project on AWS using a Linux EC2 machine.

---

## 1. Create an AWS EC2 instance

- Choose `g4dn.xlarge` as the instance type or more powerful (we need a GPU for efficient lip sync).
- Use a Linux (Ubuntu) machine.
- Set the storage volume to **64 GB** (or larger).
- Open these ports in the security group:
  - **22** (SSH)
  - **80** (HTTP)
  - **443** (HTTPS - this is crucial for webrtc connection to work)
  - **3478 and 10000-65535** (UDP for webrtc connection)

---

## 2. Create and assign an Elastic IP

- Go to the AWS console.
- Create a new **Elastic IP**.
- Associate it with your EC2 instance.
- (Optional) If you have a domain or subdomain (like our `kivaproject.org` and `play.kivaproject.org`), connect it to the Elastic IP.

---

## 3. Connect to the EC2 instance

Use SSH:
```bash
ssh -i your-key.pem ubuntu@your-elastic-ip
```

---

## 4. Install NVIDIA drivers

```bash
sudo apt update
sudo apt install ubuntu-drivers-common
sudo ubuntu-drivers autoinstall
sudo reboot
```

---

## 5. Install ollama

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

---

## 6. Install conda

```bash
mkdir -p ~/miniconda3
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O ~/miniconda3/miniconda.sh
bash ~/miniconda3/miniconda.sh -b -u -p ~/miniconda3
rm ~/miniconda3/miniconda.sh
source ~/miniconda3/bin/activate
conda init --all
```

---

## 7. Install NVM (Node version manager)

```bash
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh | bash
. "$HOME/.nvm/nvm.sh"
nvm install 22
```

---

## 8. Install more system dependencies (required by riverst)

```bash
sudo apt install -y build-essential python3-dev ffmpeg git
sudo apt install -y libsndfile1-dev pkg-config
```

---

## 9. SSL certificates with certbot

```bash
sudo apt install certbot
sudo apt install python3-certbot-nginx
sudo certbot certonly --standalone -d play.kivaproject.org
```

Set up automatic renewal:

```bash
sudo crontab -e
# Add this line:
0 0 * * * certbot renew --quiet
```

---

## 10. Install and configure NGINX

```bash
sudo apt install nginx
sudo vim /etc/nginx/sites-available/play.kivaproject.org
```

Paste this config:

```nginx
server {
    listen 80;
    server_name play.kivaproject.org;

    location / {
        return 301 https://$host$request_uri;
    }
}

server {
    listen 443 ssl;
    server_name play.kivaproject.org;

    ssl_certificate /etc/letsencrypt/live/play.kivaproject.org/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/play.kivaproject.org/privkey.pem;

    location / {
        proxy_pass http://localhost:5173;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }

    location /api/ {
        proxy_pass https://localhost:7860/api/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
        proxy_ssl_verify off;
    }
}
```

Enable the config:

```bash
sudo ln -s /etc/nginx/sites-available/play.kivaproject.org /etc/nginx/sites-enabled/
sudo systemctl start nginx
sudo systemctl status nginx
```

---

## 11. Clone and setup riverst

```bash
git clone https://github.com/fabiocat93/riverst.git
```

### Frontend

```bash
cd riverst/src/client/react/
npm install
cp .env.example .env
# Edit `.env` to configure your settings following .env.example

# [In a tmux tab]
npm run dev -- --host 0.0.0.0
```

### Backend

```bash
conda create -n riverst python=3.11
conda activate riverst
cd riverst/src/server
pip install -r requirements.txt
git clone https://huggingface.co/pipecat-ai/smart-turn-v2
cp .env.example .env
# Edit `.env` to configure your settings following .env.example

# [In a tmux tab]
sudo /home/ubuntu/miniconda3/envs/riverst/bin/python main.py \
  --ssl-certfile /etc/letsencrypt/live/play.kivaproject.org/fullchain.pem \
  --ssl-keyfile /etc/letsencrypt/live/play.kivaproject.org/privkey.pem
```

---

## 12. Setup Piper (open-source text-to-speech)

```bash
pip install --no-deps piper-tts
pip install piper_phonemize
git clone https://github.com/rhasspy/piper.git
cd piper/src/python_run
mkdir voices
cd voices

# Download voices
wget -O en_GB-alba-medium.onnx "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_GB/alba/medium/en_GB-alba-medium.onnx?download=true"
wget -O en_GB-alba-medium.onnx.json "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_GB/alba/medium/en_GB-alba-medium.onnx.json?download=true"
wget -O en_GB-alan-medium.onnx "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_GB/alan/medium/en_GB-alan-medium.onnx?download=true"
wget -O en_GB-alan-medium.onnx.json "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_GB/alan/medium/en_GB-alan-medium.onnx.json?download=true"
```

Run Piper [in 2 tmux tabs]:

```bash
python3 -m piper.http_server --model voices/en_GB-alba-medium.onnx --port 5001
python3 -m piper.http_server --model voices/en_GB-alan-medium.onnx --port 5002
```

---

## 13. Run ollama models

Run (only one at a time because `ollama run` by default connects to a single Ollama server running at localhost:11434):

```bash
ollama run qwen3:4b-instruct-2507-q4_K_M
ollama run llama3.2
```

or with Docker (this may be helpful to run both at the same time [in 2 tmux tabs]):

```bash
docker run -d \
  --name ollama-llama3 \
  -p 11434:11434 \
  -v ollama-llama3:/root/.ollama \
  ollama/ollama

# Then inside the container:
docker exec -it ollama-llama3 ollama run llama3.2

# This way you specify a different port!!!
docker run -d \
  --name ollama-qwen \
  -p 11435:11434 \
  -v ollama-qwen:/root/.ollama \
  ollama/ollama

# Then inside the container:
docker exec -it ollama-qwen ollama run qwen3:4b-instruct-2507-q4_K_M
```

---

## (Optional) COTURN Server Setup
To ensure reliable WebRTC connections, especially when clients are behind firewalls or NATs, you may want to install and configure a TURN server using coturn.

- Install and Configure COTURN
```
sudo apt-get update
sudo apt-get install coturn -y
turnserver -v  # Verify installation
```

- Edit the TURN server config
```
sudo vim /etc/turnserver.conf
```

- Here is a minimal example configuration (edit with your domain and credentials):

```
listening-port=3478
fingerprint
lt-cred-mech
realm=mydomain.org
user=testuser:testpass
no-multicast-peers
no-loopback-peers
min-port=10000
max-port=65535
external-ip=public_id/private_ip
cert=/etc/letsencrypt/live/mydomain.org/fullchain.pem
pkey=/etc/letsencrypt/live/mydomain.org/privkey.pem
verbose
log-file=/var/log/turnserver.log
```


- Enable and start the coturn service
```
sudo systemctl enable coturn
sudo systemctl start coturn
sudo systemctl status coturn
```

- Test your TURN server
Use [Trickle ICE](https://webrtc.github.io/samples/src/content/peerconnection/trickle-ice/) to verify connectivity

---


**You are all set!**
