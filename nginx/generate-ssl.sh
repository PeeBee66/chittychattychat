#!/bin/bash
set -e

echo "🔒 Generating SSL certificates for ChittyChattyChat..."

# Create SSL directory
mkdir -p /etc/nginx/ssl

# Generate chat certificate
echo "📝 Generating certificate for chat.chittychattychat.local..."
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout /etc/nginx/ssl/chat.key \
    -out /etc/nginx/ssl/chat.crt \
    -subj "/C=US/ST=State/L=City/O=ChittyChattyChat/CN=chat.chittychattychat.local" \
    -config <(
    echo '[req]'
    echo 'distinguished_name = req'
    echo '[v3_req]'
    echo 'keyUsage = keyEncipherment, dataEncipherment'
    echo 'extendedKeyUsage = serverAuth'
    echo 'subjectAltName = @alt_names'
    echo '[alt_names]'
    echo 'DNS.1 = chat.chittychattychat.local'
    echo 'DNS.2 = localhost'
    echo 'IP.1 = 127.0.0.1'
    ) \
    -extensions v3_req

# Generate admin certificate
echo "📝 Generating certificate for admin.chittychattychat.local..."
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout /etc/nginx/ssl/admin.key \
    -out /etc/nginx/ssl/admin.crt \
    -subj "/C=US/ST=State/L=City/O=ChittyChattyChat/CN=admin.chittychattychat.local" \
    -config <(
    echo '[req]'
    echo 'distinguished_name = req'
    echo '[v3_req]'
    echo 'keyUsage = keyEncipherment, dataEncipherment'
    echo 'extendedKeyUsage = serverAuth'
    echo 'subjectAltName = @alt_names'
    echo '[alt_names]'
    echo 'DNS.1 = admin.chittychattychat.local'
    echo 'DNS.2 = localhost'
    echo 'IP.1 = 127.0.0.1'
    ) \
    -extensions v3_req

# Set proper permissions
chmod 600 /etc/nginx/ssl/*.key
chmod 644 /etc/nginx/ssl/*.crt

echo "✅ SSL certificates generated successfully!"
echo "📍 Certificates location: /etc/nginx/ssl/"
echo "🔗 Chat URL: https://chat.chittychattychat.local"
echo "🔗 Admin URL: https://admin.chittychattychat.local"
echo ""
echo "⚠️  Don't forget to add these entries to your /etc/hosts file:"
echo "127.0.0.1 chat.chittychattychat.local"
echo "127.0.0.1 admin.chittychattychat.local"