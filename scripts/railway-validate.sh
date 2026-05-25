#!/bin/bash
set -eu

echo "🔍 Validating Railway configuration..."
echo ""

ERRORS=0

[ -f railway.json ] && echo "✅ railway.json" || { echo "❌ railway.json"; ERRORS=$((ERRORS+1)); }
[ -f docker/railway-entrypoint.sh ] && echo "✅ docker/railway-entrypoint.sh" || { echo "❌ docker/railway-entrypoint.sh"; ERRORS=$((ERRORS+1)); }
[ -f docker/railway-healthcheck.sh ] && echo "✅ docker/railway-healthcheck.sh" || { echo "❌ docker/railway-healthcheck.sh"; ERRORS=$((ERRORS+1)); }
grep -q "HEALTHCHECK" Dockerfile && echo "✅ Dockerfile health check" || echo "⚠️  Dockerfile missing health check"
[ -f .env.railway.example ] && echo "✅ .env.railway.example" || { echo "❌ .env.railway.example"; ERRORS=$((ERRORS+1)); }
[ -f docs/railway-deployment.md ] && echo "✅ docs/railway-deployment.md" || { echo "❌ docs/railway-deployment.md"; ERRORS=$((ERRORS+1)); }

echo ""
if [ $ERRORS -eq 0 ]; then
    echo "✅ All checks passed!"
    exit 0
else
    echo "❌ $ERRORS error(s) found"
    exit 1
fi
