#!/bin/bash
set -e

# Pastikan file state ada
if [ ! -f "/app/grid_state_ADAUSDT.json" ]; then
  echo "{}" > /app/grid_state_ADAUSDT.json
  echo "Created empty grid state file"
fi

# Pastikan file .env ada
if [ ! -f "/app/.env" ]; then
  if [ -f "/app/env.template" ]; then
    cp /app/env.template /app/.env
    echo "Copied env.template to .env - PLEASE UPDATE WITH YOUR API KEYS!"
  else
    # Buat default .env file
    cat > /app/.env << EOL
API_KEY=your_binance_api_key_here
API_SECRET=your_binance_api_secret_here
BINANCE_TESTNET=False
DASHBOARD_USERNAME=admin
DASHBOARD_PASSWORD=Grid@Trading123
DASHBOARD_SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
EOL
    echo "Created default .env file - PLEASE UPDATE WITH YOUR API KEYS!"
  fi
fi

# Eksekusi command yang diberikan
exec "$@" 