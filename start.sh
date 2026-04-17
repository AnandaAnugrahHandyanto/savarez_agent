#!/bin/bash

# Hermes startup script

# Set environment variables
export NODE_ENV=production
export PORT=3000

# Generate JWT_SECRET if not already set
export JWT_SECRET=$(head -c 64 /dev/urandom | base64 | tr -d '\n')
echo "JWT_SECRET generated successfully"

# Start the application
echo "Starting Hermes application..."

# Add your application start command here
# For example:
# npm start
# or
# python app.py
# or
# ./hermes-server
