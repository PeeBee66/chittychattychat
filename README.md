# ChittyChattyChat

Anonymous 1-on-1 web chat with 24-hour rooms, hybrid encryption, and audit archive.

## Features

- **Anonymous Chat**: 1-on-1 rooms with 4-character IDs
- **24-Hour Expiry**: Rooms automatically close after 24 hours
- **Device Locking**: Rooms lock to 2 specific devices/browsers
- **Hybrid Encryption**: Messages encrypted at rest, server can decrypt for audit
- **Admin Panel**: Read-only admin interface for monitoring and audits
- **File Sharing**: Image uploads with previews
- **Responsive UI**: Works on both mobile and desktop
- **Dark/Light Theme**: User-selectable themes

## Architecture

- **Chat Service** (Port 5055): Flask + Socket.IO for real-time chat
- **Admin Panel** (Port 5056): Flask web interface for administrators
- **PostgreSQL**: Message and room data storage
- **Redis**: Session management and Socket.IO scaling
- **MinIO**: File storage for images and archives

## Quick Start

1. **Clone and setup**:
   ```bash
   cd chittychattychat
   cp .env.example .env
   # Edit .env with your settings
   ```

2. **Generate master key**:
   ```bash
   python3 -c "import secrets; import base64; print(base64.b64encode(secrets.token_bytes(32)).decode())"
   # Copy output to MASTER_KEY in .env
   ```

3. **Start services**:
   ```bash
   docker-compose up -d
   ```

4. **Access the application**:
   - Chat Interface: http://localhost:5055
   - Admin Panel: http://localhost:5056

## Configuration

Key environment variables in `.env`:

```bash
# Encryption (REQUIRED)
MASTER_KEY=YourBase64EncodedMasterKeyHere32BytesExactly==

# Database
POSTGRES_USER=chitty_user
POSTGRES_PASSWORD=chitty_secure_2025
POSTGRES_DB=chittychat

# MinIO Storage
MINIO_ACCESS_KEY=chitty_minio_access
MINIO_SECRET_KEY=chitty_minio_secret_key_2025

# Security
ALLOWED_ADMIN_CIDRS=10.0.0.0/8,172.16.0.0/12,192.168.0.0/16,127.0.0.1/32

# Ports (External)
CHAT_PORT=5055
ADMIN_PORT=5056
POSTGRES_EXTERNAL_PORT=5433
REDIS_EXTERNAL_PORT=6380
MINIO_EXTERNAL_PORT=9001
```

## Usage

### Creating a Room

1. Visit http://localhost:5055
2. Click "Host Chat"
3. Click "Create Room" to generate a 4-character Room ID
4. Click "Accept & Activate" to start the 24-hour timer
5. Share the Room ID with someone to start chatting

### Joining a Room

1. Visit http://localhost:5055
2. Click "Join Chat"
3. Enter the 4-character Room ID
4. Choose a display name from the provided options
5. Start chatting!

### Admin Panel

1. Visit http://localhost:5056 (local network access only)
2. View dashboard with all rooms and their status
3. Click "Transcript" to view full conversation history
4. Click "Archive" for rooms that have expired and been archived

## Security Features

- **Hybrid Encryption**: AES-256-GCM encryption with envelope keys
- **Device Binding**: Rooms locked to specific browser/device combinations
- **IP Logging**: All messages and actions logged with IP addresses
- **Network Restrictions**: Admin panel only accessible from local networks
- **Audit Trail**: Complete conversation history available to administrators

## Development

### Manual Setup

```bash
# Install dependencies
cd chitty && pip install -r requirements.txt
cd ../adminpanel && pip install -r requirements.txt

# Setup database
createdb chittychat
psql chittychat < migrations/001_init_schema.sql

# Run services
# Terminal 1: Chat service
cd chitty && python app.py

# Terminal 2: Admin panel
cd adminpanel && python app.py

# Terminal 3: Start supporting services
docker-compose up postgres redis minio
```

### Database Schema

The application uses PostgreSQL with these main tables:

- `rooms`: Chat room metadata and status
- `room_keys`: Encrypted room keys for message decryption
- `participants`: Room participants with device binding
- `messages`: Encrypted messages with metadata
- `attachments`: File upload metadata and MinIO object keys

## Monitoring

### Health Checks

- Chat Service: `GET http://localhost:5055/health`
- Admin Panel: `GET http://localhost:5056/health`

### Logs

```bash
# View logs
docker-compose logs -f ccc-chitty
docker-compose logs -f ccc-adminpanel

# View specific service logs
docker-compose logs -f ccc-postgres
docker-compose logs -f ccc-redis
docker-compose logs -f ccc-minio
```

## Deployment

For production deployment:

1. **Security**:
   - Generate strong passwords and keys
   - Use HTTPS/TLS termination at load balancer
   - Restrict admin panel network access
   - Regular security updates

2. **Scaling**:
   - Multiple chat service instances behind load balancer
   - Redis for Socket.IO message distribution
   - PostgreSQL with connection pooling
   - MinIO with erasure coding or replication

3. **Backup**:
   - Regular PostgreSQL backups
   - MinIO data replication
   - Archive conversation transcripts

## Troubleshooting

### Common Issues

1. **Port conflicts**: Check `.env` ports don't conflict with existing services
2. **Database connection**: Ensure PostgreSQL is running and accessible
3. **MinIO access**: Verify MinIO credentials and bucket creation
4. **Room expiry**: Check system time and timezone settings
5. **Admin access**: Verify IP address is in allowed CIDR ranges

### Reset Everything

```bash
# Stop and remove all containers and volumes
docker-compose down -v

# Start fresh
docker-compose up -d
```

## License

This is a proof-of-concept implementation. Please review and modify security settings before production use.

## Support

For issues and questions:
1. Check the logs using the commands above
2. Verify configuration in `.env`
3. Ensure all services are running: `docker-compose ps`