#!/bin/bash
# Script de démarrage pour Railway

echo "🚀 Démarrage de Hermes-Agent sur Railway..."

# Activer l'environnement virtuel pour que la commande 'hermes' soit reconnue
source /opt/hermes/.venv/bin/activate

# 1. Lancer la Gateway en arrière-plan
hermes gateway run &
GATEWAY_PID=$!

sleep 5

PORT="${PORT:-9119}"
echo "🌐 Lémarrage du Dashboard web sur le port $PORT..."
hermes dashboard --host 0.0.0.0 --port $PORT --no-open --insecure

kill $GATEWAY_PID
