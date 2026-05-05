# Deployment Templates

Reference configurations for Kubernetes and Docker deployments.

## Kubernetes Base Template

### Namespace

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: {{PROJECT_NAME}}
  labels:
    app: {{PROJECT_NAME}}
```

### Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{PROJECT_NAME}}-app
  namespace: {{PROJECT_NAME}}
spec:
  replicas: 2
  selector:
    matchLabels:
      app: {{PROJECT_NAME}}
  template:
    metadata:
      labels:
        app: {{PROJECT_NAME}}
    spec:
      containers:
      - name: app
        image: {{IMAGE}}:{{TAG}}
        ports:
        - containerPort: 3000
        env:
        - name: NODE_ENV
          value: "production"
        resources:
          requests:
            memory: "128Mi"
            cpu: "100m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /health
            port: 3000
          initialDelaySeconds: 10
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 3000
          initialDelaySeconds: 5
          periodSeconds: 5
```

### Service

```yaml
apiVersion: v1
kind: Service
metadata:
  name: {{PROJECT_NAME}}-svc
  namespace: {{PROJECT_NAME}}
spec:
  selector:
    app: {{PROJECT_NAME}}
  ports:
  - port: 80
    targetPort: 3000
  type: ClusterIP
```

### Ingress

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: {{PROJECT_NAME}}-ingress
  namespace: {{PROJECT_NAME}}
  annotations:
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
spec:
  tls:
  - hosts:
    - {{DOMAIN}}
    secretName: {{PROJECT_NAME}}-tls
  rules:
  - host: {{DOMAIN}}
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: {{PROJECT_NAME}}-svc
            port:
              number: 80
```

## Dockerfile Template

### Node.js/React Frontend

```dockerfile
# Build stage
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci --only=production
COPY . .
RUN npm run build

# Production stage
FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
```

### Node.js Backend

```dockerfile
FROM node:20-alpine
WORKDIR /app
COPY package*.json ./
RUN npm ci --only=production
COPY . .
USER node
EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:3000/health || exit 1
CMD ["node", "server.js"]
```

### Python/FastAPI

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## Docker Compose Template

```yaml
version: '3.8'
services:
  app:
    build: .
    ports:
      - "3000:3000"
    environment:
      - NODE_ENV=production
      - DATABASE_URL=${DATABASE_URL}
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:3000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

## Cloudflare Tunnel (Alternative)

For simple deployments without public IP:

```bash
# Create tunnel
cf tunnel-create {{PROJECT_NAME}}

# Configure DNS
cf tunnel-dns <tunnel-id> {{DOMAIN}} @

# Run tunnel
cf tunnel run <tunnel-id>
```

## Template Variables

Replace these in templates:
- `{{PROJECT_NAME}}` - Project slug (lowercase, hyphenated)
- `{{DOMAIN}}` - Full domain name
- `{{IMAGE}}` - Container image path
- `{{TAG}}` - Image tag (usually `latest` or git sha)
