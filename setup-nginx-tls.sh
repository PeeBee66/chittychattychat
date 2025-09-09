#!/bin/bash
set -e

echo "🚀 Setting up Nginx with TLS for ChittyChattyChat..."

# Check if Docker Compose is available
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is required but not installed"
    exit 1
fi

# Add hosts entries
echo "📝 Adding hosts entries..."
HOSTS_FILE="/etc/hosts"
CHAT_HOST="127.0.0.1 chat.chittychattychat.local"
ADMIN_HOST="127.0.0.1 admin.chittychattychat.local"

# Check if entries already exist
if ! grep -q "chat.chittychattychat.local" "$HOSTS_FILE"; then
    echo "Adding chat.chittychattychat.local to hosts file..."
    echo "$CHAT_HOST" | sudo tee -a "$HOSTS_FILE"
fi

if ! grep -q "admin.chittychattychat.local" "$HOSTS_FILE"; then
    echo "Adding admin.chittychattychat.local to hosts file..."
    echo "$ADMIN_HOST" | sudo tee -a "$HOSTS_FILE"
fi

# Build and start Nginx service
echo "🔨 Building and starting Nginx service..."
docker-compose build ccc-nginx
docker-compose up -d ccc-nginx

# Wait for services to be healthy
echo "⏳ Waiting for services to become healthy..."
max_attempts=30
attempt=0

while [ $attempt -lt $max_attempts ]; do
    if docker-compose ps ccc-nginx | grep -q "healthy"; then
        echo "✅ Nginx service is healthy!"
        break
    fi
    
    echo "Waiting for Nginx to be healthy... (attempt $((attempt + 1))/$max_attempts)"
    sleep 5
    attempt=$((attempt + 1))
done

if [ $attempt -eq $max_attempts ]; then
    echo "❌ Nginx service failed to become healthy"
    echo "📋 Check logs with: docker-compose logs ccc-nginx"
    exit 1
fi

# Test the endpoints
echo "🧪 Testing HTTPS endpoints..."

echo "Testing chat endpoint..."
if curl -k -s --connect-timeout 10 https://chat.chittychattychat.local/health > /dev/null; then
    echo "✅ Chat HTTPS endpoint is working!"
else
    echo "⚠️  Chat HTTPS endpoint may not be fully ready yet"
fi

echo "Testing admin endpoint..."
if curl -k -s --connect-timeout 10 https://admin.chittychattychat.local/ > /dev/null; then
    echo "✅ Admin HTTPS endpoint is working!"
else
    echo "⚠️  Admin HTTPS endpoint may not be fully ready yet"
fi

echo ""
echo "🎉 Nginx with TLS setup complete!"
echo ""
echo "📱 Access URLs:"
echo "   Chat:  https://chat.chittychattychat.local"
echo "   Admin: https://admin.chittychattychat.local"
echo ""
echo "🔒 Features enabled:"
echo "   ✅ HTTPS/TLS encryption"
echo "   ✅ HTTP to HTTPS redirect"
echo "   ✅ WebSocket support for real-time chat"
echo "   ✅ File upload support (50MB limit)"
echo "   ✅ Rate limiting protection"
echo "   ✅ Security headers"
echo "   ✅ Admin panel IP restrictions"
echo ""
echo "⚠️  Certificate Warnings:"
echo "   Your browser will show security warnings for self-signed certificates."
echo "   Click 'Advanced' and 'Proceed to chat.chittychattychat.local' to continue."
echo ""
echo "🔍 Useful commands:"
echo "   Check status: docker-compose ps"
echo "   View logs:    docker-compose logs ccc-nginx"
echo "   Restart:      docker-compose restart ccc-nginx"