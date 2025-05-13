#!/bin/bash

echo "=== Checking what's using port 5000 ==="

# Try different ways to identify the process
echo "Method 1: netstat"
netstat -tulpn | grep :5000

echo "Method 2: lsof"
lsof -i :5000

echo "Method 3: Check running containers"
docker ps

echo "=== End of port check ===" 