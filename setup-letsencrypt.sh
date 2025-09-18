#!/bin/bash

# Let's Encrypt Setup Script for ChittyChattyChat
# This script sets up production SSL certificates using Let's Encrypt

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  ChittyChattyChat Let's Encrypt Setup${NC}"
echo -e "${BLUE}========================================${NC}\n"

# Check if running as root (needed for certbot in some cases)
if [[ $EUID -eq 0 ]]; then
   echo -e "${YELLOW}⚠️  This script is running as root${NC}"
fi

# Get domain information
echo -e "${BLUE}Please provide your domain information:${NC}"
read -p "Enter your main domain (e.g., chittychattychat.com): " MAIN_DOMAIN
read -p "Enter your email for Let's Encrypt notifications: " EMAIL

# Validate input
if [[ -z "$MAIN_DOMAIN" ]]; then
    echo -e "${RED}❌ Domain cannot be empty${NC}"
    exit 1
fi

if [[ -z "$EMAIL" ]]; then
    echo -e "${RED}❌ Email cannot be empty${NC}"
    exit 1
fi

# Ask for subdomain configuration
echo -e "\n${BLUE}Subdomain Configuration:${NC}"
read -p "Chat subdomain (default: chat): " CHAT_SUBDOMAIN
read -p "Admin subdomain (default: admin): " ADMIN_SUBDOMAIN

CHAT_SUBDOMAIN=${CHAT_SUBDOMAIN:-chat}
ADMIN_SUBDOMAIN=${ADMIN_SUBDOMAIN:-admin}

CHAT_DOMAIN="${CHAT_SUBDOMAIN}.${MAIN_DOMAIN}"
ADMIN_DOMAIN="${ADMIN_SUBDOMAIN}.${MAIN_DOMAIN}"

echo -e "\n${GREEN}Configuration Summary:${NC}"
echo -e "  Main Domain: ${MAIN_DOMAIN}"
echo -e "  Chat Domain: ${CHAT_DOMAIN}"
echo -e "  Admin Domain: ${ADMIN_DOMAIN}"
echo -e "  Email: ${EMAIL}"

read -p $'\nDo you want to proceed? (y/N): ' -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}Setup cancelled${NC}"
    exit 0
fi

# Create directories
echo -e "\n${GREEN}📁 Creating certificate directories...${NC}"
mkdir -p certs/letsencrypt
mkdir -p certs/nginx

# Create docker-compose override for Let's Encrypt
echo -e "${GREEN}📝 Creating docker-compose.letsencrypt.yml...${NC}"
cat > docker-compose.letsencrypt.yml <<EOF
# Let's Encrypt Override Configuration
# Use with: docker-compose -f docker-compose.yml -f docker-compose.letsencrypt.yml up -d

services:
  ccc-nginx:
    volumes:
      - ./certs/letsencrypt:/etc/letsencrypt
      - ./certs/nginx/dhparam.pem:/etc/nginx/dhparam.pem
      - ./nginx/nginx.letsencrypt.conf:/etc/nginx/nginx.conf:ro
      - ./certbot/www:/var/www/certbot:ro
    depends_on:
      - certbot

  certbot:
    image: certbot/certbot
    container_name: ccc-certbot
    volumes:
      - ./certs/letsencrypt:/etc/letsencrypt
      - ./certbot/www:/var/www/certbot
    entrypoint: "/bin/sh -c 'trap exit TERM; while :; do certbot renew; sleep 12h & wait \$\${!}; done;'"
EOF

# Create Nginx configuration for Let's Encrypt
echo -e "${GREEN}📝 Creating nginx.letsencrypt.conf...${NC}"
cat > nginx/nginx.letsencrypt.conf <<'EOF'
user nginx;
worker_processes auto;
error_log /var/log/nginx/error.log warn;
pid /var/run/nginx.pid;

events {
    worker_connections 1024;
    use epoll;
    multi_accept on;
}

http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;

    # Logging
    access_log /var/log/nginx/access.log;

    # Performance
    sendfile on;
    tcp_nopush on;
    tcp_nodelay on;
    keepalive_timeout 65;
    types_hash_max_size 2048;
    client_max_body_size 10M;

    # Gzip
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_types text/plain text/css text/xml text/javascript application/javascript application/json application/xml+rss;

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=general:10m rate=10r/s;
    limit_req_zone $binary_remote_addr zone=auth:10m rate=5r/m;

    # Backend upstreams
    upstream chitty_backend {
        server ccc-chitty:5055;
        keepalive 32;
    }

    upstream admin_backend {
        server ccc-adminpanel:5056;
        keepalive 32;
    }

    # HTTP redirect to HTTPS
    server {
        listen 80;
        listen [::]:80;
        server_name CHAT_DOMAIN ADMIN_DOMAIN;

        # ACME challenge for Let's Encrypt
        location /.well-known/acme-challenge/ {
            root /var/www/certbot;
        }

        # Redirect everything else to HTTPS
        location / {
            return 301 https://$server_name$request_uri;
        }
    }

    # HTTPS Chat Server
    server {
        listen 443 ssl http2;
        listen [::]:443 ssl http2;
        server_name CHAT_DOMAIN;

        # SSL Configuration
        ssl_certificate /etc/letsencrypt/live/CHAT_DOMAIN/fullchain.pem;
        ssl_certificate_key /etc/letsencrypt/live/CHAT_DOMAIN/privkey.pem;

        # Strong SSL Settings
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers HIGH:!aNULL:!MD5;
        ssl_prefer_server_ciphers off;
        ssl_session_timeout 1d;
        ssl_session_cache shared:SSL:50m;
        ssl_stapling on;
        ssl_stapling_verify on;

        # DH parameters
        ssl_dhparam /etc/nginx/dhparam.pem;

        # Security headers
        add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
        add_header X-Frame-Options "SAMEORIGIN" always;
        add_header X-Content-Type-Options "nosniff" always;
        add_header X-XSS-Protection "1; mode=block" always;
        add_header Referrer-Policy "strict-origin-when-cross-origin" always;

        # WebSocket configuration
        location /socket.io/ {
            proxy_pass http://chitty_backend;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;

            # WebSocket timeouts
            proxy_connect_timeout 7d;
            proxy_send_timeout 7d;
            proxy_read_timeout 7d;
        }

        # Main application
        location / {
            limit_req zone=general burst=20 nodelay;

            proxy_pass http://chitty_backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;

            # Connection settings
            proxy_http_version 1.1;
            proxy_set_header Connection "";
        }
    }

    # HTTPS Admin Panel Server
    server {
        listen 443 ssl http2;
        listen [::]:443 ssl http2;
        server_name ADMIN_DOMAIN;

        # SSL Configuration
        ssl_certificate /etc/letsencrypt/live/ADMIN_DOMAIN/fullchain.pem;
        ssl_certificate_key /etc/letsencrypt/live/ADMIN_DOMAIN/privkey.pem;

        # Strong SSL Settings (same as chat)
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers HIGH:!aNULL:!MD5;
        ssl_prefer_server_ciphers off;
        ssl_session_timeout 1d;
        ssl_session_cache shared:SSL:50m;
        ssl_stapling on;
        ssl_stapling_verify on;

        # DH parameters
        ssl_dhparam /etc/nginx/dhparam.pem;

        # Security headers
        add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
        add_header X-Frame-Options "SAMEORIGIN" always;
        add_header X-Content-Type-Options "nosniff" always;
        add_header X-XSS-Protection "1; mode=block" always;
        add_header Referrer-Policy "strict-origin-when-cross-origin" always;

        # Admin routes with authentication rate limiting
        location /api/auth {
            limit_req zone=auth burst=5 nodelay;

            proxy_pass http://admin_backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        # Main admin application
        location / {
            limit_req zone=general burst=20 nodelay;

            proxy_pass http://admin_backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;

            proxy_http_version 1.1;
            proxy_set_header Connection "";
        }
    }
}
EOF

# Replace domain placeholders
sed -i "s/CHAT_DOMAIN/${CHAT_DOMAIN}/g" nginx/nginx.letsencrypt.conf
sed -i "s/ADMIN_DOMAIN/${ADMIN_DOMAIN}/g" nginx/nginx.letsencrypt.conf

# Generate DH parameters if not exists
if [ ! -f "certs/nginx/dhparam.pem" ]; then
    echo -e "${GREEN}🔐 Generating DH parameters (this may take a minute)...${NC}"
    openssl dhparam -out certs/nginx/dhparam.pem 2048
fi

# Create initial certificate request script
echo -e "${GREEN}📝 Creating initial certificate request script...${NC}"
cat > request-certificates.sh <<EOF
#!/bin/bash

# Request initial certificates from Let's Encrypt

echo "Requesting certificates for ${CHAT_DOMAIN} and ${ADMIN_DOMAIN}..."

# Create certbot webroot directory
mkdir -p certbot/www

# Start nginx for ACME challenge
docker-compose -f docker-compose.yml -f docker-compose.letsencrypt.yml up -d ccc-nginx

# Wait for nginx to start
sleep 5

# Request certificate for chat domain
docker run -it --rm \\
    -v "\$(pwd)/certs/letsencrypt:/etc/letsencrypt" \\
    -v "\$(pwd)/certbot/www:/var/www/certbot" \\
    certbot/certbot certonly \\
    --webroot \\
    --webroot-path=/var/www/certbot \\
    --email ${EMAIL} \\
    --agree-tos \\
    --no-eff-email \\
    -d ${CHAT_DOMAIN}

# Request certificate for admin domain
docker run -it --rm \\
    -v "\$(pwd)/certs/letsencrypt:/etc/letsencrypt" \\
    -v "\$(pwd)/certbot/www:/var/www/certbot" \\
    certbot/certbot certonly \\
    --webroot \\
    --webroot-path=/var/www/certbot \\
    --email ${EMAIL} \\
    --agree-tos \\
    --no-eff-email \\
    -d ${ADMIN_DOMAIN}

echo "Certificates requested! Restarting services with SSL..."

# Restart with full configuration
docker-compose -f docker-compose.yml -f docker-compose.letsencrypt.yml down
docker-compose -f docker-compose.yml -f docker-compose.letsencrypt.yml up -d

echo "Setup complete!"
echo "Access your services at:"
echo "  Chat: https://${CHAT_DOMAIN}"
echo "  Admin: https://${ADMIN_DOMAIN}"
EOF

chmod +x request-certificates.sh

# Create renewal script
echo -e "${GREEN}📝 Creating certificate renewal script...${NC}"
cat > renew-certificates.sh <<'EOF'
#!/bin/bash

# Renew Let's Encrypt certificates

echo "Checking for certificate renewal..."

# Run certbot renewal
docker-compose -f docker-compose.yml -f docker-compose.letsencrypt.yml exec certbot certbot renew

# Reload nginx to pick up new certificates
docker-compose -f docker-compose.yml -f docker-compose.letsencrypt.yml exec ccc-nginx nginx -s reload

echo "Renewal check complete!"
EOF

chmod +x renew-certificates.sh

# Create systemd timer for automatic renewal (optional)
echo -e "${GREEN}📝 Creating systemd timer configuration (optional)...${NC}"
cat > letsencrypt-renewal.service <<EOF
[Unit]
Description=Let's Encrypt renewal for ChittyChattyChat

[Service]
Type=oneshot
WorkingDirectory=$(pwd)
ExecStart=$(pwd)/renew-certificates.sh
EOF

cat > letsencrypt-renewal.timer <<EOF
[Unit]
Description=Run Let's Encrypt renewal twice daily

[Timer]
OnCalendar=*-*-* 00,12:00:00
RandomizedDelaySec=1h
Persistent=true

[Install]
WantedBy=timers.target
EOF

echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}✨ Let's Encrypt setup complete!${NC}"
echo -e "${GREEN}========================================${NC}\n"

echo -e "${YELLOW}📋 Next Steps:${NC}"
echo -e "  1. Ensure your DNS records point to this server:"
echo -e "     ${CHAT_DOMAIN} → Your server IP"
echo -e "     ${ADMIN_DOMAIN} → Your server IP\n"

echo -e "  2. Request initial certificates:"
echo -e "     ${BLUE}./request-certificates.sh${NC}\n"

echo -e "  3. (Optional) Setup automatic renewal with systemd:"
echo -e "     ${BLUE}sudo cp letsencrypt-renewal.* /etc/systemd/system/${NC}"
echo -e "     ${BLUE}sudo systemctl daemon-reload${NC}"
echo -e "     ${BLUE}sudo systemctl enable --now letsencrypt-renewal.timer${NC}\n"

echo -e "${YELLOW}📝 To switch between dev and production certificates:${NC}"
echo -e "  Dev mode:  ${BLUE}docker-compose up -d${NC}"
echo -e "  Prod mode: ${BLUE}docker-compose -f docker-compose.yml -f docker-compose.letsencrypt.yml up -d${NC}\n"

echo -e "${GREEN}✅ Setup script completed successfully!${NC}"