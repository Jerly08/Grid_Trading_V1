#!/bin/bash

echo "=== Port 5000 Conflict Resolution Script ==="

# Option 1: Find and stop the process using port 5000
find_and_stop_process() {
  echo "Looking for processes using port 5000..."
  
  # Find the process ID
  PID=$(lsof -t -i:5000 2>/dev/null)
  
  if [ -z "$PID" ]; then
    echo "No process found using lsof. Trying netstat..."
    PID=$(netstat -tulpn 2>/dev/null | grep :5000 | awk '{print $7}' | cut -d'/' -f1)
  fi
  
  if [ -n "$PID" ]; then
    echo "Found process using port 5000: PID $PID"
    
    # Get process name
    PROCESS_NAME=$(ps -p $PID -o comm=)
    echo "Process name: $PROCESS_NAME"
    
    read -p "Do you want to kill this process? (y/n): " confirm
    if [[ $confirm == [yY] || $confirm == [yY][eE][sS] ]]; then
      echo "Stopping process $PID..."
      kill -15 $PID
      sleep 2
      
      # Check if it's still running
      if ps -p $PID > /dev/null; then
        echo "Process still running. Trying force kill..."
        kill -9 $PID
        sleep 1
      fi
      
      # Check again
      if ! ps -p $PID > /dev/null; then
        echo "Process successfully stopped."
        return 0
      else
        echo "Failed to stop process."
        return 1
      fi
    else
      echo "Aborted. Process not killed."
      return 1
    fi
  else
    echo "Could not find specific process using port 5000."
    
    # Check if it's a Docker container
    CONTAINER_ID=$(docker ps | grep -E '5000->5000|:5000' | awk '{print $1}')
    if [ -n "$CONTAINER_ID" ]; then
      echo "Found Docker container using port 5000: $CONTAINER_ID"
      read -p "Do you want to stop this container? (y/n): " confirm
      if [[ $confirm == [yY] || $confirm == [yY][eE][sS] ]]; then
        echo "Stopping container..."
        docker stop $CONTAINER_ID
        return 0
      else
        echo "Aborted. Container not stopped."
        return 1
      fi
    fi
    
    return 1
  fi
}

# Option 2: Change port in docker-compose.yml
change_port() {
  echo "Modifying docker-compose.yml to use a different port..."
  
  if [ ! -f "docker-compose.yml" ]; then
    echo "Error: docker-compose.yml not found in current directory."
    return 1
  fi
  
  # Create backup
  cp docker-compose.yml docker-compose.yml.bak
  
  # Ask for new port
  read -p "Enter new port to use (e.g. 5001): " new_port
  
  # Validate port
  if ! [[ "$new_port" =~ ^[0-9]+$ ]] || [ "$new_port" -lt 1024 ] || [ "$new_port" -gt 65535 ]; then
    echo "Invalid port number. Please enter a number between 1024 and 65535."
    return 1
  fi
  
  # Check if the new port is available
  if lsof -i :"$new_port" > /dev/null 2>&1 || netstat -tulpn 2>/dev/null | grep :"$new_port" > /dev/null; then
    echo "Warning: Port $new_port also appears to be in use!"
    read -p "Continue anyway? (y/n): " continue
    if [[ ! $continue == [yY] && ! $continue == [yY][eE][sS] ]]; then
      echo "Aborted."
      return 1
    fi
  fi
  
  # Update the port in docker-compose.yml
  if grep -q "5000:5000" docker-compose.yml; then
    sed -i "s/5000:5000/$new_port:5000/g" docker-compose.yml
    echo "Updated port mapping from 5000:5000 to $new_port:5000"
  elif grep -q ":5000" docker-compose.yml; then
    sed -i "s/:5000/:$new_port/g" docker-compose.yml
    echo "Updated port mapping to use port $new_port"
  else
    echo "Couldn't find port 5000 mapping in docker-compose.yml"
    echo "You may need to edit the file manually."
    return 1
  fi
  
  echo "docker-compose.yml updated. Original saved as docker-compose.yml.bak"
  echo "You can now run 'docker-compose up -d' to start with the new port."
  
  return 0
}

# Main menu
echo "How would you like to resolve the port conflict?"
echo "1) Find and stop the process using port 5000"
echo "2) Change the port in docker-compose.yml"
echo "3) Exit without changes"

read -p "Enter your choice (1-3): " choice

case $choice in
  1)
    find_and_stop_process
    ;;
  2)
    change_port
    ;;
  3)
    echo "Exiting without changes."
    exit 0
    ;;
  *)
    echo "Invalid choice. Exiting."
    exit 1
    ;;
esac

echo "=== Script completed ===" 