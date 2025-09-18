# Development Certificates for ChittyChattyChat

This directory contains development SSL certificates for testing HTTPS locally.

## ⚠️ IMPORTANT SECURITY WARNING
These certificates are for **DEVELOPMENT ONLY** and should **NEVER** be used in production!

## Directory Structure
- `ca/` - Development Certificate Authority
- `chat/` - Certificates for the chat application
- `admin/` - Certificates for the admin panel
- `nginx/` - Certificates prepared for Nginx configuration

## Certificate Details
- **CA Validity**: 10 years
- **Service Certificates Validity**: 1 year
- **Domains Covered**:
  - chat.chittychattychat.local
  - admin.chittychattychat.local
  - localhost
  - Container names (ccc-chitty, ccc-adminpanel)

## Usage
1. Mount the `nginx/` directory in your Docker container
2. Reference the certificates in your Nginx configuration
3. Optionally import `ca/ca.crt` to your browser for green padlock

## Regenerating Certificates
Simply run `./generate-dev-certs.sh` again and choose to regenerate.

## Production Certificates
For production, use proper certificates from:
- Let's Encrypt (free)
- Commercial CA (DigiCert, GlobalSign, etc.)
- Your organization's internal CA
