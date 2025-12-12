# Docker Deployment Guide

## Overview

This project includes comprehensive Docker configuration for development and production deployment of the Windsurf Sustainable City Dashboard.

## Services

### Backend API
- **Port**: 8000
- **Technology**: FastAPI + Python 3.11
- **Database**: SQLite (development) / PostgreSQL (production)
- **Features**: Auto-migrations, health checks, file uploads

### Frontend
- **Port**: 3000
- **Technology**: React + Vite + Node.js 18
- **Features**: Hot reload, development server

### Optional Services
- **PostgreSQL**: Production database (port 5432)
- **Redis**: Caching and sessions (port 6379)
- **Nginx**: Reverse proxy for production (ports 80/443)
- **Adminer**: Database admin interface (port 8080)

## Quick Start

### Development (SQLite)
```bash
# Start backend and frontend
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

### Development with PostgreSQL
```bash
# Start with PostgreSQL database
docker-compose --profile postgres up -d

# Access database admin
# http://localhost:8080
# Server: db
# Username: windsurf
# Password: windsurf_pass
```

### Production Deployment
```bash
# Start with all production services
docker-compose --profile production --profile postgres up -d

# This includes:
# - Backend (port 8000)
# - Frontend (port 3000)
# - PostgreSQL (port 5432)
# - Nginx reverse proxy (ports 80/443)
# - Redis (port 6379)
```

## Environment Variables

### Backend Environment
```bash
ENV=docker
DATABASE_URL=sqlite:///./dev.db
SECRET_KEY=change-me-in-production
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=30
UPLOAD_ROOT=/app/uploads
CORS_ORIGINS=["http://localhost:3000"]
```

### Frontend Environment
```bash
VITE_API_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000/ws
```

## Volumes

### Persistent Data
- `backend_uploads`: File uploads and certificates
- `backend_db`: SQLite database files
- `postgres_data`: PostgreSQL data (when using PostgreSQL)
- `redis_data`: Redis cache data

### Development Volumes
- `./backend:/app`: Live code mounting for backend
- `./frontend:/app`: Live code mounting for frontend

## Health Checks

All services include health checks:
- **Backend**: `curl -f http://localhost:8000/health`
- **Frontend**: `curl -f http://localhost:3000`
- **Database**: Connection validation

## Production Configuration

### Nginx Configuration
The Nginx reverse proxy provides:
- Load balancing
- SSL termination (configure certificates in `nginx/ssl/`)
- Static file serving
- WebSocket support
- Gzip compression
- Security headers

### SSL Setup
1. Place certificates in `nginx/ssl/`:
   - `cert.pem`: SSL certificate
   - `key.pem`: Private key

2. Uncomment HTTPS server block in `nginx/nginx.conf`

### Database Migration
The backend automatically runs Alembic migrations on startup:
```dockerfile
CMD alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Development Workflow

### Making Changes
- Backend changes are reflected immediately (live reload)
- Frontend changes trigger hot reload via Vite
- Database migrations run automatically on container restart

### Testing
```bash
# Run backend tests
docker-compose exec backend pytest

# Run frontend tests
docker-compose exec frontend npm test

# Check service health
docker-compose ps
```

### Debugging
```bash
# View backend logs
docker-compose logs -f backend

# View frontend logs
docker-compose logs -f frontend

# Access container shell
docker-compose exec backend bash
docker-compose exec frontend sh
```

## Production Considerations

### Security
1. Change default passwords and secrets
2. Configure SSL certificates
3. Use environment variables for sensitive data
4. Enable firewall rules
5. Regular security updates

### Performance
1. Use PostgreSQL instead of SQLite for production
2. Enable Redis caching
3. Configure Nginx for optimal performance
4. Monitor resource usage
5. Set up log rotation

### Backup Strategy
1. Backup PostgreSQL database regularly
2. Backup upload volumes
3. Backup configuration files
4. Test restore procedures

## Troubleshooting

### Common Issues

#### Backend Won't Start
```bash
# Check database connection
docker-compose exec backend python -c "from app.db.session import engine; print(engine.url)"

# Run migrations manually
docker-compose exec backend alembic upgrade head
```

#### Frontend Build Issues
```bash
# Clear node modules and reinstall
docker-compose exec frontend rm -rf node_modules package-lock.json
docker-compose exec frontend npm install
```

#### Database Connection Issues
```bash
# Check PostgreSQL status
docker-compose exec postgres pg_isready

# Reset database (development only)
docker-compose down -v
docker-compose up -d postgres
```

#### Permission Issues
```bash
# Fix upload permissions
sudo chown -R 1000:1000 ./backend/uploads
```

### Performance Issues
1. Check resource usage: `docker stats`
2. Monitor logs for errors
3. Verify database connections
4. Check Nginx configuration

## Scaling

### Horizontal Scaling
```yaml
# Example docker-compose.override.yml
version: '3.9'
services:
  backend:
    deploy:
      replicas: 3
  frontend:
    deploy:
      replicas: 2
```

### Load Balancing
Nginx automatically load balances between backend replicas when using Docker Swarm or Kubernetes.

## Monitoring

### Basic Monitoring
```bash
# Service status
docker-compose ps

# Resource usage
docker stats

# Logs
docker-compose logs -f
```

### Advanced Monitoring
Consider integrating with:
- Prometheus + Grafana
- ELK Stack (Elasticsearch, Logstash, Kibana)
- Docker health checks
- External monitoring services

## Support

For deployment issues:
1. Check this guide first
2. Review Docker logs
3. Verify environment configuration
4. Check network connectivity
5. Validate service dependencies
