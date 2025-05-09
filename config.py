import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Binance API credentials
API_KEY = os.getenv('API_KEY')
API_SECRET = os.getenv('API_SECRET')
TESTNET = os.getenv('BINANCE_TESTNET', 'True').lower() in ('true', 'yes', '1')

# Mode simulasi (tidak membuat order sungguhan)
SIMULATION_MODE = True  # Set ke False jika ingin membuat order sungguhan

# Grid trading parameters (Optimized for ADA/USDT with 500.000 IDR budget)
SYMBOL = 'ADAUSDT'  # Trading pair
UPPER_PRICE = 0.795  # Upper price boundary for grid (~2% above current price)
LOWER_PRICE = 0.765  # Lower price boundary for grid (~2% below current price)
GRID_NUMBER = 5      # Focus on 5 level grid for limited capital
GRID_SIZE = (UPPER_PRICE - LOWER_PRICE) / GRID_NUMBER  # Size of each grid

# Order parameters
QUANTITY = 20  # Quantity of crypto to buy/sell at each grid level
ORDER_TYPE = 'LIMIT'  # Order type: LIMIT or MARKET

# Risk management
MAX_INVESTMENT = 32  # Maximum investment in USDT (≈ 500.000 IDR)
STOP_LOSS_PERCENTAGE = 5  # Stop loss percentage 

# Dashboard settings
DASHBOARD_USERNAME = os.getenv('DASHBOARD_USERNAME', 'admin')
DASHBOARD_PASSWORD = os.getenv('DASHBOARD_PASSWORD', 'Grid@Trading123')
EMOJI_SUPPORT = False  # Set to True if your terminal supports emoji 