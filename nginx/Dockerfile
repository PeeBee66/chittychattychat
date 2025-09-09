FROM nginx:alpine

# Install OpenSSL and curl for certificate generation and health checks
RUN apk add --no-cache openssl curl

# Copy Nginx configuration
COPY nginx.conf /etc/nginx/nginx.conf

# Copy SSL generation script
COPY generate-ssl.sh /usr/local/bin/generate-ssl.sh
RUN chmod +x /usr/local/bin/generate-ssl.sh

# Create nginx user and group if they don't exist
RUN addgroup -g 101 -S nginx || true
RUN adduser -S -D -H -u 101 -h /var/cache/nginx -s /sbin/nologin -G nginx -g nginx nginx || true

# Create necessary directories
RUN mkdir -p /var/log/nginx /etc/nginx/ssl /var/cache/nginx
RUN chown -R nginx:nginx /var/log/nginx /var/cache/nginx

# Generate SSL certificates directly in Dockerfile
RUN openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout /etc/nginx/ssl/chat.key \
    -out /etc/nginx/ssl/chat.crt \
    -subj "/C=US/ST=State/L=City/O=ChittyChattyChat/CN=chat.chittychattychat.local" && \
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout /etc/nginx/ssl/admin.key \
    -out /etc/nginx/ssl/admin.crt \
    -subj "/C=US/ST=State/L=City/O=ChittyChattyChat/CN=admin.chittychattychat.local" && \
    chmod 600 /etc/nginx/ssl/*.key && \
    chmod 644 /etc/nginx/ssl/*.crt

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f -k https://localhost/nginx-health || exit 1

# Expose ports
EXPOSE 80 443

# Start Nginx
CMD ["nginx", "-g", "daemon off;"]