#!/bin/bash

# Generate Development SSL Certificates for ChittyChattyChat
# This script creates a development CA and certificates for testing HTTPS

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Certificate directory - using standard certs folder
CERT_DIR="./certs"
CA_DIR="${CERT_DIR}/ca"
CHAT_DIR="${CERT_DIR}/chat"
ADMIN_DIR="${CERT_DIR}/admin"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  ChittyChattyChat Dev Certificate Generator${NC}"
echo -e "${BLUE}========================================${NC}\n"

# Check if certificates already exist
if [ -d "$CERT_DIR" ]; then
    echo -e "${YELLOW}⚠️  Certificate directory already exists.${NC}"
    read -p "Do you want to regenerate all certificates? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${YELLOW}Exiting without changes.${NC}"
        exit 0
    fi
    echo -e "${YELLOW}Removing existing certificates...${NC}"
    rm -rf "$CERT_DIR"
fi

# Create directories
echo -e "${GREEN}📁 Creating certificate directories...${NC}"
mkdir -p "$CA_DIR" "$CHAT_DIR" "$ADMIN_DIR"

# Generate CA private key
echo -e "${GREEN}🔑 Generating Development CA private key...${NC}"
openssl genrsa -out "${CA_DIR}/ca.key" 4096

# Generate CA certificate
echo -e "${GREEN}📜 Creating Development CA certificate...${NC}"
openssl req -new -x509 -days 3650 -key "${CA_DIR}/ca.key" -out "${CA_DIR}/ca.crt" \
    -subj "/C=US/ST=Development/L=Local/O=DEV_TESTING_CA/CN=ChittyChattyChat Development CA"

echo -e "${GREEN}✅ Development CA created successfully!${NC}\n"

# Function to generate certificate for a service
generate_cert() {
    local SERVICE=$1
    local DIR=$2
    local DOMAIN=$3
    local ALT_NAMES=$4

    echo -e "${BLUE}--- Generating certificate for ${SERVICE} ---${NC}"

    # Generate private key
    echo -e "${GREEN}🔑 Generating private key for ${SERVICE}...${NC}"
    openssl genrsa -out "${DIR}/${SERVICE}.key" 2048

    # Create config file for certificate request
    cat > "${DIR}/${SERVICE}.conf" <<EOF
[req]
distinguished_name = req_distinguished_name
req_extensions = v3_req
prompt = no

[req_distinguished_name]
C = US
ST = Development
L = Local
O = ChittyChattyChat
CN = ${DOMAIN}

[v3_req]
keyUsage = keyEncipherment, dataEncipherment
extendedKeyUsage = serverAuth
subjectAltName = @alt_names

[alt_names]
${ALT_NAMES}
EOF

    # Generate certificate request
    echo -e "${GREEN}📝 Creating certificate request for ${SERVICE}...${NC}"
    openssl req -new -key "${DIR}/${SERVICE}.key" -out "${DIR}/${SERVICE}.csr" \
        -config "${DIR}/${SERVICE}.conf"

    # Sign certificate with CA
    echo -e "${GREEN}✍️  Signing certificate with Development CA...${NC}"
    openssl x509 -req -in "${DIR}/${SERVICE}.csr" \
        -CA "${CA_DIR}/ca.crt" -CAkey "${CA_DIR}/ca.key" \
        -CAcreateserial -out "${DIR}/${SERVICE}.crt" \
        -days 365 -extensions v3_req -extfile "${DIR}/${SERVICE}.conf"

    # Create combined PEM file
    cat "${DIR}/${SERVICE}.crt" "${DIR}/${SERVICE}.key" > "${DIR}/${SERVICE}.pem"

    # Clean up CSR
    rm "${DIR}/${SERVICE}.csr"

    echo -e "${GREEN}✅ Certificate for ${SERVICE} created successfully!${NC}\n"
}

# Generate certificate for Chat service
ALT_NAMES="DNS.1 = chat.chittychattychat.local
DNS.2 = localhost
DNS.3 = chitty
DNS.4 = ccc-chitty
IP.1 = 127.0.0.1
IP.2 = ::1"

generate_cert "chat" "$CHAT_DIR" "chat.chittychattychat.local" "$ALT_NAMES"

# Generate certificate for Admin Panel
ALT_NAMES="DNS.1 = admin.chittychattychat.local
DNS.2 = localhost
DNS.3 = adminpanel
DNS.4 = ccc-adminpanel
IP.1 = 127.0.0.1
IP.2 = ::1"

generate_cert "admin" "$ADMIN_DIR" "admin.chittychattychat.local" "$ALT_NAMES"

# Create Nginx certificates directory and copy certificates
echo -e "${BLUE}📦 Preparing certificates for Nginx...${NC}"
NGINX_CERT_DIR="${CERT_DIR}/nginx"
mkdir -p "$NGINX_CERT_DIR"

# Copy certificates for Nginx
cp "${CHAT_DIR}/chat.crt" "${NGINX_CERT_DIR}/chat.crt"
cp "${CHAT_DIR}/chat.key" "${NGINX_CERT_DIR}/chat.key"
cp "${ADMIN_DIR}/admin.crt" "${NGINX_CERT_DIR}/admin.crt"
cp "${ADMIN_DIR}/admin.key" "${NGINX_CERT_DIR}/admin.key"
cp "${CA_DIR}/ca.crt" "${NGINX_CERT_DIR}/ca.crt"

# Create combined certificate chains
cat "${CHAT_DIR}/chat.crt" "${CA_DIR}/ca.crt" > "${NGINX_CERT_DIR}/chat-chain.crt"
cat "${ADMIN_DIR}/admin.crt" "${CA_DIR}/ca.crt" > "${NGINX_CERT_DIR}/admin-chain.crt"

# Create DH parameters for Nginx (this takes a moment)
echo -e "${BLUE}🔐 Generating DH parameters (this may take a minute)...${NC}"
openssl dhparam -out "${NGINX_CERT_DIR}/dhparam.pem" 2048

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}✨ All certificates generated successfully!${NC}"
echo -e "${GREEN}========================================${NC}\n"

echo -e "${YELLOW}📋 Certificate Information:${NC}"
echo -e "  CA Certificate: ${CERT_DIR}/ca/ca.crt"
echo -e "  Chat Certificate: ${CERT_DIR}/chat/chat.crt"
echo -e "  Admin Certificate: ${CERT_DIR}/admin/admin.crt\n"

echo -e "${YELLOW}🔧 To use these certificates:${NC}"
echo -e "  1. Update nginx/nginx.conf to use certificates from ./certs/nginx/"
echo -e "  2. Mount the certs volume in docker-compose.yml"
echo -e "  3. Import ca.crt to your browser's trusted CAs (optional)\n"

echo -e "${YELLOW}📝 To trust the CA on your system:${NC}"
echo -e "  ${BLUE}Ubuntu/Debian:${NC}"
echo -e "    sudo cp ${CERT_DIR}/ca/ca.crt /usr/local/share/ca-certificates/chitty-dev-ca.crt"
echo -e "    sudo update-ca-certificates\n"
echo -e "  ${BLUE}MacOS:${NC}"
echo -e "    sudo security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain ${CERT_DIR}/ca/ca.crt\n"
echo -e "  ${BLUE}Windows:${NC}"
echo -e "    Import ${CERT_DIR}/ca/ca.crt using certmgr.msc\n"

echo -e "${GREEN}✅ Script completed successfully!${NC}"

# Create a README for the certificates
cat > "${CERT_DIR}/README.md" <<EOF
# Development Certificates for ChittyChattyChat

This directory contains development SSL certificates for testing HTTPS locally.

## ⚠️ IMPORTANT SECURITY WARNING
These certificates are for **DEVELOPMENT ONLY** and should **NEVER** be used in production!

## Directory Structure
- \`ca/\` - Development Certificate Authority
- \`chat/\` - Certificates for the chat application
- \`admin/\` - Certificates for the admin panel
- \`nginx/\` - Certificates prepared for Nginx configuration

## Certificate Details
- **CA Validity**: 10 years
- **Service Certificates Validity**: 1 year
- **Domains Covered**:
  - chat.chittychattychat.local
  - admin.chittychattychat.local
  - localhost
  - Container names (ccc-chitty, ccc-adminpanel)

## Usage
1. Mount the \`nginx/\` directory in your Docker container
2. Reference the certificates in your Nginx configuration
3. Optionally import \`ca/ca.crt\` to your browser for green padlock

## Regenerating Certificates
Simply run \`./generate-dev-certs.sh\` again and choose to regenerate.

## Production Certificates
For production, use proper certificates from:
- Let's Encrypt (free)
- Commercial CA (DigiCert, GlobalSign, etc.)
- Your organization's internal CA
EOF

echo -e "${BLUE}📖 README.md created in ${CERT_DIR}/${NC}"