# First steps to deploy riverst

This guide explains step-by-step how to deploy the Riverst project on AWS using a Linux EC2 machine.

---

## 1. Create an AWS EC2 instance

- Choose `g4dn.xlarge` as the instance type or more powerful (you may need a more powerful gpu if you want to run models locally without experiencing any unpleasant delay).
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
cp .env.example .env
# Edit `.env` to configure your settings following .env.example
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
cp .env.example .env
# Edit `.env` to configure your settings following .env.example
# Edit the src/server/config/authorized_users.json

# [In a tmux tab]
sudo /home/ubuntu/miniconda3/envs/riverst/bin/python main.py \
  --ssl-certfile /etc/letsencrypt/live/play.kivaproject.org/fullchain.pem \
  --ssl-keyfile /etc/letsencrypt/live/play.kivaproject.org/privkey.pem
```


Instead of starting the backend manually, you can run it as a service.

- Run Riverst backend as a daemon
```
sudo vim /etc/systemd/system/riverst-server.service
```

- Paste:
```
[Unit]
Description=Riverst Python Server
After=network.target ollama-server.service ollama-qwen3.service
Requires=ollama-server.service ollama-qwen3.service

[Service]
Type=simple
User=root
WorkingDirectory=/home/ubuntu/riverst/src/server
ExecStart=/home/ubuntu/miniconda3/envs/riverst/bin/python main.py \
  --ssl-certfile /etc/letsencrypt/live/play.kivaproject.org/fullchain.pem \
  --ssl-keyfile /etc/letsencrypt/live/play.kivaproject.org/privkey.pem
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
Then enable and start:
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
        proxy_pass https://localhost:7860/api/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;

        # Because it's a self-signed or custom cert:
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


**You are all set!**
