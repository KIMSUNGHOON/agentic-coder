# Agentic 2.0 Deployment Guide

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Installation](#installation)
3. [Docker Deployment](#docker-deployment)
4. [Kubernetes Deployment](#kubernetes-deployment)
5. [Production Configuration](#production-configuration)
6. [Health Checks](#health-checks)
7. [Monitoring](#monitoring)
8. [Backup and Recovery](#backup-and-recovery)
9. [Scaling](#scaling)
10. [Security](#security)

## Prerequisites

### System Requirements

**Minimum:**
- CPU: 2 cores
- RAM: 4 GB
- Disk: 20 GB
- OS: Linux, macOS, Windows (with WSL2)

**Recommended:**
- CPU: 4+ cores
- RAM: 8+ GB
- Disk: 50+ GB SSD
- OS: Linux (Ubuntu 20.04+, Debian 11+, RHEL 8+)

### Software Requirements

- Python 3.10 or higher
- pip 21.0 or higher
- Docker 20.10+ (for containerized deployment)
- Docker Compose 2.0+ (optional)
- PostgreSQL 13+ (optional, for production persistence)
- Git (for version control)

### Network Requirements

- Outbound HTTPS (443) for LLM API access
- Inbound HTTP (8080) for health checks
- Inbound TCP (5432) for PostgreSQL (if external)
- Inbound HTTP (9090) for Prometheus (optional)
- Inbound HTTP (3000) for Grafana (optional)

## Installation

### Quick Install

```bash
# Clone repository
git clone <repository-url>
cd agentic-ai

# Run installation script
./install.sh
```

The installation script will:
1. Check prerequisites
2. Create virtual environment
3. Install dependencies
4. Create directories
5. Create `.env` and `config.yaml`
6. Run tests (optional)

### Manual Installation

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Create directories
mkdir -p data/sessions logs workspace config

# Create configuration
cp config/config.example.yaml config/config.yaml
nano config/config.yaml  # Edit configuration

# Create environment file
cp .env.example .env
nano .env  # Add API keys

# Run tests
python examples/test_integration_full.py
```

## Docker Deployment

### Build and Run with Docker

```bash
# Build image
docker build -t agentic:latest .

# Run container
docker run -d \
  --name agentic \
  -p 8080:8080 \
  -e LLM_API_KEY_1="your-key-1" \
  -e LLM_API_KEY_2="your-key-2" \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/logs:/app/logs \
  agentic:latest
```

### Docker Compose Deployment

```bash
# Create .env file with required variables
cat > .env <<EOF
LLM_API_KEY_1=your-key-1
LLM_API_KEY_2=your-key-2
POSTGRES_USER=agentic
POSTGRES_PASSWORD=secure-password
EOF

# Start services
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f agentic

# Stop services
docker-compose down
```

### Multi-Container Setup

The default `docker-compose.yml` includes:

- **agentic**: Main application
- **postgres**: Database for checkpoints
- **prometheus**: Metrics collection
- **grafana**: Metrics visualization

Access services:
- Application: http://localhost:8080
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000

## Kubernetes Deployment

### Kubernetes Manifests

Create `k8s/deployment.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: agentic
  labels:
    app: agentic
spec:
  replicas: 3
  selector:
    matchLabels:
      app: agentic
  template:
    metadata:
      labels:
        app: agentic
    spec:
      containers:
      - name: agentic
        image: agentic:latest
        ports:
        - containerPort: 8080
          name: http
        env:
        - name: LLM_API_KEY_1
          valueFrom:
            secretKeyRef:
              name: agentic-secrets
              key: llm-api-key-1
        - name: LLM_API_KEY_2
          valueFrom:
            secretKeyRef:
              name: agentic-secrets
              key: llm-api-key-2
        - name: POSTGRES_HOST
          value: postgres-service
        - name: POSTGRES_PASSWORD
          valueFrom:
            secretKeyRef:
              name: postgres-secrets
              key: password
        resources:
          requests:
            memory: "2Gi"
            cpu: "1000m"
          limits:
            memory: "4Gi"
            cpu: "2000m"
        livenessProbe:
          httpGet:
            path: /health/live
            port: 8080
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health/ready
            port: 8080
          initialDelaySeconds: 10
          periodSeconds: 5
        volumeMounts:
        - name: data
          mountPath: /app/data
        - name: logs
          mountPath: /app/logs
      volumes:
      - name: data
        persistentVolumeClaim:
          claimName: agentic-data-pvc
      - name: logs
        emptyDir: {}
---
apiVersion: v1
kind: Service
metadata:
  name: agentic-service
spec:
  selector:
    app: agentic
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8080
  type: LoadBalancer
```

Create secrets:

```bash
# Create secrets
kubectl create secret generic agentic-secrets \
  --from-literal=llm-api-key-1='your-key-1' \
  --from-literal=llm-api-key-2='your-key-2'

kubectl create secret generic postgres-secrets \
  --from-literal=password='secure-password'

# Deploy
kubectl apply -f k8s/
```

### Horizontal Pod Autoscaling

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: agentic-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: agentic
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

## Production Configuration

### Environment Variables

Create `.env` file:

```bash
# LLM Configuration
LLM_API_KEY_1=sk-...
LLM_API_KEY_2=sk-...

# Database
POSTGRES_HOST=postgres.example.com
POSTGRES_PORT=5432
POSTGRES_DB=agentic_prod
POSTGRES_USER=agentic
POSTGRES_PASSWORD=secure-password

# Observability
AGENTIC_LOG_LEVEL=INFO
AGENTIC_DEBUG=false

# Security
SECRET_KEY=your-secret-key-here
```

### Production Config (`config/production.yaml`)

```yaml
llm:
  model_name: "gpt-oss-120b"
  temperature: 0.7
  max_tokens: 4096
  mode: "active-active"

  endpoints:
    - url: "https://llm-primary.example.com/v1"
      api_key: "${LLM_API_KEY_1}"
      name: "primary"
      timeout: 30
      max_retries: 3

    - url: "https://llm-secondary.example.com/v1"
      api_key: "${LLM_API_KEY_2}"
      name: "secondary"
      timeout: 30
      max_retries: 3

  caching:
    enabled: true
    max_size: 1000
    ttl_seconds: 300

safety:
  enabled: true
  max_tool_calls_per_task: 100

  rate_limiting:
    enabled: true
    max_requests_per_minute: 60

  allowed_domains:
    - "github.com"
    - "stackoverflow.com"

persistence:
  checkpointing:
    enabled: true
    backend: "postgres"

    postgres:
      host: "${POSTGRES_HOST}"
      port: 5432
      database: "${POSTGRES_DB}"
      user: "${POSTGRES_USER}"
      password: "${POSTGRES_PASSWORD}"
      connection_pool_size: 10

observability:
  logging:
    enabled: true
    console_level: "INFO"
    file_level: "DEBUG"

  metrics:
    enabled: true
    export:
      enabled: true
      format: "prometheus"
      endpoint: "http://prometheus:9090"

production:
  endpoint_selection:
    enabled: true
    algorithm: "weighted"

  error_handling:
    enabled: true
    retry:
      max_retries: 3
      base_delay: 1.0

  graceful_degradation:
    enabled: true
    auto_recovery: true

  health_monitoring:
    enabled: true
    check_interval_seconds: 30
```

## Health Checks

### HTTP Endpoints

The application exposes health check endpoints:

- **Liveness**: `/health/live`
  - Returns 200 if application is running
  - Used by orchestrators to restart dead containers

- **Readiness**: `/health/ready`
  - Returns 200 if ready to accept traffic
  - Checks all critical components

- **Detailed Status**: `/health/status`
  - Returns detailed health information
  - Includes component-level status

### Example Health Check

```bash
# Liveness check
curl http://localhost:8080/health/live

# Readiness check
curl http://localhost:8080/health/ready

# Detailed status
curl http://localhost:8080/health/status | jq '.'
```

### Custom Health Checks

Add custom health checks:

```python
from production import HealthChecker

checker = HealthChecker()

# Add custom check
def redis_health_check():
    try:
        redis_client.ping()
        return True
    except:
        return False

checker.register_check("redis", redis_health_check)
```

## Monitoring

### Prometheus Metrics

Metrics are exported at `/metrics` endpoint:

```bash
curl http://localhost:8080/metrics
```

Available metrics:
- `agentic_workflow_executions_total`
- `agentic_llm_calls_total`
- `agentic_llm_call_duration_seconds`
- `agentic_tool_calls_total`
- `agentic_errors_total`
- `agentic_active_agents`

### Grafana Dashboards

Import dashboard from `deploy/grafana/dashboards/agentic.json`:

1. Open Grafana (http://localhost:3000)
2. Login (admin/admin)
3. Go to Dashboards → Import
4. Upload `agentic.json`

### Alerting

Configure alerts in `deploy/prometheus.yml`:

```yaml
rule_files:
  - 'alerts.yml'

alerting:
  alertmanagers:
    - static_configs:
        - targets:
            - alertmanager:9093
```

Example alert (`deploy/alerts.yml`):

```yaml
groups:
  - name: agentic
    interval: 30s
    rules:
      - alert: HighErrorRate
        expr: rate(agentic_errors_total[5m]) > 0.1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High error rate detected"

      - alert: LLMEndpointDown
        expr: up{job="agentic"} == 0
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "LLM endpoint is down"
```

## Backup and Recovery

### Database Backups

For PostgreSQL:

```bash
# Backup
pg_dump -h localhost -U agentic -d agentic_prod > backup.sql

# Restore
psql -h localhost -U agentic -d agentic_prod < backup.sql
```

Automated backup script:

```bash
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/backups"

# Backup database
pg_dump -h $POSTGRES_HOST -U $POSTGRES_USER -d $POSTGRES_DB \
  | gzip > $BACKUP_DIR/agentic_${DATE}.sql.gz

# Keep only last 7 days
find $BACKUP_DIR -name "agentic_*.sql.gz" -mtime +7 -delete
```

### Session Recovery

Sessions are automatically checkpointed. To recover:

```python
from persistence import StateRecovery

recovery = StateRecovery()

# List sessions
sessions = session_manager.list_sessions()

# Recover specific session
state = await recovery.load_state(session_id)
```

## Scaling

### Vertical Scaling

Increase resources per instance:

```yaml
resources:
  requests:
    memory: "4Gi"  # Increased from 2Gi
    cpu: "2000m"   # Increased from 1000m
  limits:
    memory: "8Gi"  # Increased from 4Gi
    cpu: "4000m"   # Increased from 2000m
```

### Horizontal Scaling

Scale replicas:

```bash
# Docker Compose
docker-compose up -d --scale agentic=3

# Kubernetes
kubectl scale deployment agentic --replicas=5
```

### Load Balancing

Use nginx for load balancing:

```nginx
upstream agentic {
    least_conn;
    server agentic-1:8080;
    server agentic-2:8080;
    server agentic-3:8080;
}

server {
    listen 80;
    location / {
        proxy_pass http://agentic;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## Security

### TLS/SSL

Enable HTTPS with Let's Encrypt:

```bash
# Install certbot
apt-get install certbot python3-certbot-nginx

# Get certificate
certbot --nginx -d agentic.example.com

# Auto-renewal
certbot renew --dry-run
```

### Secret Management

Use secret management tools:

**AWS Secrets Manager:**
```python
import boto3

client = boto3.client('secretsmanager')
secret = client.get_secret_value(SecretId='agentic/api-keys')
```

**HashiCorp Vault:**
```python
import hvac

client = hvac.Client(url='https://vault:8200')
client.auth.approle.login(role_id='...', secret_id='...')
secret = client.secrets.kv.v2.read_secret_version(path='agentic/api-keys')
```

### Network Security

1. Use firewalls to restrict access
2. Enable rate limiting
3. Implement IP whitelisting
4. Use VPC/private networks

### Application Security

1. Regularly update dependencies
2. Scan for vulnerabilities
3. Enable safety checks
4. Validate all inputs
5. Sanitize outputs

## Deployment Checklist

- [ ] Configuration reviewed and validated
- [ ] API keys and secrets configured
- [ ] Database initialized
- [ ] Health checks configured
- [ ] Monitoring set up
- [ ] Backup strategy in place
- [ ] Security measures enabled
- [ ] Load balancing configured (if needed)
- [ ] SSL/TLS certificates installed
- [ ] Firewall rules configured
- [ ] Logging and alerting working
- [ ] Documentation updated
- [ ] Team trained

## Troubleshooting Deployment

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for common issues and solutions.

## Support

For deployment issues:
- Check logs: `docker-compose logs -f`
- Review health: `curl http://localhost:8080/health/status`
- Check metrics: http://localhost:9090
- Open issue: <repository-url>/issues
