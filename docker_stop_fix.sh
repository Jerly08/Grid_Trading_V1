#!/bin/bash

echo "===== Fixing Docker container conflict ====="

# 1. Stop the existing container using port 5000
echo "Stopping existing grid-bot container..."
docker stop grid-bot
docker rm grid-bot

# 2. Check if the port is now free
echo "Checking if port 5000 is now free..."
if lsof -i :5000 || netstat -tulpn | grep :5000; then
  echo "Port 5000 is still in use. Let's try to find what's using it..."
  
  # Find the PID using port 5000
  PID=$(lsof -t -i:5000 2>/dev/null)
  if [ -n "$PID" ]; then
    echo "Found process using port 5000: PID $PID"
    echo "Stopping process..."
    kill -9 $PID
    sleep 2
  fi
  
  # Check Docker for any containers using port 5000
  CONTAINERS=$(docker ps -q --filter publish=5000)
  if [ -n "$CONTAINERS" ]; then
    echo "Found containers using port 5000. Stopping them..."
    docker stop $CONTAINERS
    docker rm $CONTAINERS
  fi
fi

# 3. Run the docker_restart.sh script
echo "Now running docker_restart.sh..."
./docker_restart.sh

# 4. If we still can't start, offer to change the port
if [ $? -ne 0 ]; then
  echo "Still having issues. Would you like to modify docker-compose.yml to use a different port?"
  read -p "Enter new port (e.g. 5001) or press enter to skip: " new_port
  
  if [ -n "$new_port" ]; then
    # Backup the file
    cp docker-compose.yml docker-compose.yml.bak
    
    # Update the port
    if grep -q "5000:5000" docker-compose.yml; then
      sed -i "s/5000:5000/$new_port:5000/g" docker-compose.yml
    elif grep -q ":5000" docker-compose.yml; then
      sed -i "s/:5000/:$new_port/g" docker-compose.yml
    fi
    
    echo "Updated docker-compose.yml to use port $new_port"
    echo "Trying to restart with new port..."
    ./docker_restart.sh
  fi
fi

echo "===== Process completed =====" 