# First steps to deploy riverst

This guide explains step-by-step how to deploy the Riverst project on AWS using a Linux EC2 machine.

> **CPU-only deployment**: All activities are now configured to use OpenAI APIs by default (STT, LLM, TTS). No GPU, NVIDIA drivers, or Ollama is required. Skip steps 4 and 5, use the CPU-only service config in step 9, and skip step 10.

---

## 1. Create an AWS EC2 instance

**CPU-only (recommended):** Use `c6i.2xlarge` (8 vCPU, 16 GB RAM, ~$0.34/hr) or `m6i.xlarge` (4 vCPU, 16 GB RAM, ~$0.19/hr). Set storage to **30 GB**.

**GPU deployment:** Choose `g4dn.xlarge` or more powerful. Set storage to **64 GB** (or larger).

- Use a Linux (Ubuntu 22.04 LTS) machine.
- Open these ports in the security group:
  - **22** (SSH)
  - **80** (HTTP)
  - **443** (HTTPS - this is crucial for webrtc connection to work)
  - **3478 and 10000-65535** (UDP for webrtc connection)

---

## 2. Create and assign an Elastic IP

**If replacing an existing instance (zero-downtime domain cutover):**
1. Go to EC2 → Elastic IPs in the AWS console.
2. Disassociate the existing Elastic IP from the old instance.
3. Associate it with your new instance.
4. DNS propagates instantly — no TTL wait needed since the IP address does not change.

**If creating a fresh deployment:**
- Create a new **Elastic IP** and associate it with your EC2 instance.
- Point your domain or subdomain (e.g., `play.kivaproject.org`) DNS A record to the new Elastic IP.

---

## 3. Connect to the EC2 instance

Use SSH:
```bash
ssh -i your-key.pem ubuntu@your-elastic-ip
```

---

## 4. Install NVIDIA drivers

**GPU deployment only — skip for CPU-only instances.**

```bash
sudo apt update
sudo apt install ubuntu-drivers-common
sudo ubuntu-drivers autoinstall
sudo reboot
```

---

## 5. Install ollama

**GPU deployment only — skip for CPU-only instances.**

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

You can run ollama backend with:
```bash
ollama run
```

Alternatively, you can run it as a daemon:

- Create the service file:
```bash
sudo vim /etc/systemd/system/ollama-server.service
```

- Paste:

```bash
[Unit]
Description=Ollama Backend Server
After=network.target

[Service]
Type=simple
User=ubuntu
ExecStart=/usr/local/bin/ollama serve
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
Enable and start the service:
```

- Run:

```bash
sudo systemctl daemon-reload
sudo systemctl enable ollama-server.service
sudo systemctl start ollama-server.service
```

- Check logs:

```bash
journalctl -u ollama-server.service -n 20 -f
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

## 8. Install more system dependencies (required by riverst and for serving web apps - a.k.a. nginx)

```bash
sudo add-apt-repository universe
sudo apt update
sudo apt install -y build-essential python3-dev ffmpeg git
sudo apt install -y libsndfile1-dev pkg-config
sudo apt install -y nginx
```

---

## 9. Clone and setup riverst

```bash
git clone https://github.com/sensein/riverst.git
```

### Frontend

```bash
cd riverst/src/client/react/
npm install
cp env.example .env
# Edit `.env` to configure your settings following env.example
npm run build
sudo mkdir -p /var/www
sudo ln -s /home/ubuntu/riverst/src/client/react/dist /var/www/play.kivaproject.org
```

### Backend

```bash
conda create -n riverst python=3.11
conda activate riverst
cd riverst/src/server
pip install -r requirements.txt
cp env.example .env
# Edit `.env` to configure your settings following env.example
# Required: OPENAI_API_KEY, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, SECRET_KEY
# For CPU-only deployment add: RIVERST_COMPUTE_DEVICE=cpu
# Edit the src/server/config/authorized_users.json

# [In a tmux tab — nginx handles SSL, so no cert args needed]
/home/ubuntu/miniconda3/envs/riverst/bin/python main.py
```


Instead of starting the backend manually, you can run it as a service.

- **CPU-only** — Run Riverst backend as a daemon (no Ollama dependency):
```
sudo vim /etc/systemd/system/riverst-server.service
```

- Paste:
```
[Unit]
Description=Riverst Python Server
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/riverst/src/server
Environment=RIVERST_COMPUTE_DEVICE=cpu
ExecStart=/home/ubuntu/miniconda3/envs/riverst/bin/python main.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

- **GPU deployment** — include Ollama as a dependency instead:
```
[Unit]
Description=Riverst Python Server
After=network.target ollama-server.service ollama-qwen3.service
Requires=ollama-server.service ollama-qwen3.service

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/riverst/src/server
ExecStart=/home/ubuntu/miniconda3/envs/riverst/bin/python main.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

- Run:
```
sudo systemctl daemon-reload
sudo systemctl enable riverst-server.service
sudo systemctl start riverst-server.service
journalctl -u riverst-server.service -n 20 -f
```


---

## 10. Run ollama models

**GPU deployment only — skip for CPU-only instances.**

Run interactively (only one at a time because `ollama run` by default connects to a single Ollama server running at localhost:11434):

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


Alternatively, you can run Ollama model (e.g., Qwen3) as a daemon:

- Create a service to automatically run Qwen3 on boot:

```
sudo vim /etc/systemd/system/ollama-qwen3.service
```

- Paste:
```
[Unit]
Description=Ollama Model Qwen3 Loader (Interactive)
After=ollama-server.service
Requires=ollama-server.service

[Service]
ExecStart=/usr/bin/script -q -c "/usr/local/bin/ollama run qwen3:4b-instruct-2507-q4_K_M" /dev/null
Restart=always
RestartSec=5
User=ubuntu

[Install]
WantedBy=multi-user.target
```

- Then run:

```
sudo systemctl daemon-reload
sudo systemctl enable ollama-qwen3.service
sudo systemctl start ollama-qwen3.service
```

- Check logs:
```
journalctl -u ollama-qwen3.service -n 20 -f
```

---

## 11. (Optional) COTURN Server Setup
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

**Note**: [Extensive coturn setup guide](https://www.metered.ca/blog/coturn/)

---

## 12. SSL certificates with certbot

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

## 13. Configure NGINX

```bash
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

    root /var/www/play.kivaproject.org;
    index index.html;
    client_max_body_size 50M;

    #location / {
    #    proxy_pass http://localhost:5173;
    #    proxy_http_version 1.1;
    #    proxy_set_header Upgrade $http_upgrade;
    #    proxy_set_header Connection "upgrade";
    #    proxy_set_header Host $host;
    #    proxy_cache_bypass $http_upgrade;
    #}

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://localhost:7860/api/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }

    location /uploads/ {
        proxy_pass http://localhost:7860/uploads/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
    }
}
```

Enable the config:

```bash
sudo ln -s /etc/nginx/sites-available/play.kivaproject.org /etc/nginx/sites-enabled/
sudo systemctl start nginx
sudo systemctl status nginx
```

> **Note on user-uploaded avatars**: Avatars uploaded by users are stored locally at `src/server/uploads/` on the EC2 instance and are gitignored. They will be lost if the instance is terminated or replaced. Consider snapshotting the EBS volume before replacing an instance, or migrating uploads to S3 in the future.

---


**You are all set!**
