#!/bin/bash

echo "===== Modifying Docker Compose Configuration ====="

# Check if docker-compose.yml exists
if [ ! -f "docker-compose.yml" ]; then
  echo "Error: docker-compose.yml not found!"
  exit 1
fi

# Create backup
echo "Creating backup of docker-compose.yml..."
cp docker-compose.yml docker-compose.yml.backup

# Default new port
NEW_PORT=5001

# Ask for port to use
read -p "Enter port to use (default: 5001): " port_input
if [ -n "$port_input" ]; then
  NEW_PORT=$port_input
fi

echo "Will use port $NEW_PORT instead of 5000"

# Check if the new port is already in use
if lsof -i :$NEW_PORT > /dev/null 2>&1 || netstat -tulpn 2>/dev/null | grep :$NEW_PORT > /dev/null; then
  echo "Warning: Port $NEW_PORT is already in use!"
  read -p "Continue anyway? (y/n): " continue_anyway
  if [[ ! $continue_anyway =~ ^[Yy]$ ]]; then
    echo "Aborted. No changes made."
    exit 1
  fi
fi

# Print the current docker-compose.yml content for port 5000
echo "Current port mapping in docker-compose.yml:"
grep -n -A3 -B3 "5000" docker-compose.yml || echo "No port 5000 mapping found"

# Update the port in docker-compose.yml
if grep -q "5000:5000" docker-compose.yml; then
  # Replace exact 5000:5000 mapping
  sed -i "s/5000:5000/$NEW_PORT:5000/g" docker-compose.yml
  echo "Updated port mapping from 5000:5000 to $NEW_PORT:5000"
elif grep -q ":5000" docker-compose.yml; then
  # Replace any port mapping to 5000
  sed -i "s/:5000/:$NEW_PORT/g" docker-compose.yml
  echo "Updated port mapping to use port $NEW_PORT"
else
  # Handle other formats or more complex port mappings
  # Look for port: ["5000:5000"] format
  sed -i "s/\"5000:5000\"/\"$NEW_PORT:5000\"/g" docker-compose.yml
  # Look for port: 5000:5000 format 
  sed -i "s/port: 5000:5000/port: $NEW_PORT:5000/g" docker-compose.yml
  # Look for - 5000:5000 format
  sed -i "s/- 5000:5000/- $NEW_PORT:5000/g" docker-compose.yml
  echo "Tried to update various port mapping formats"
fi

# Print the new docker-compose.yml content for the port
echo "New port mapping in docker-compose.yml:"
grep -n -A3 -B3 "$NEW_PORT" docker-compose.yml || echo "No port $NEW_PORT mapping found"

echo "===== Docker Compose configuration updated ====="
echo "To apply changes, run: docker-compose up -d"
echo "To access your app, use: http://your-server-ip:$NEW_PORT" 