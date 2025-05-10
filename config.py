import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Binance API credentials
API_KEY = os.getenv('API_KEY')
API_SECRET = os.getenv('API_SECRET')
TESTNET = os.getenv('BINANCE_TESTNET', 'True').lower() in ('true', 'yes', '1')

# Grid trading parameters (Optimized for ADA/USDT with 27 USDT budget)
SYMBOL = 'ADAUSDT'  # Trading pair
UPPER_PRICE = 0.815  # Upper price boundary for grid
LOWER_PRICE = 0.785  # Lower price boundary for grid
GRID_NUMBER = 3      # Jumlah grid optimal untuk modal kecil
GRID_SIZE = (UPPER_PRICE - LOWER_PRICE) / GRID_NUMBER  # Size of each grid

# Order parameters
QUANTITY = 13  # Ditingkatkan dari 8 menjadi 13 untuk memenuhi batas minimal 10 USDT per order
ORDER_TYPE = 'LIMIT'  # Order type: LIMIT or MARKET

# Risk management
MAX_INVESTMENT = 27  # Maximum investment in USDT
STOP_LOSS_PERCENTAGE = 5  # Stop loss percentage

# Dashboard settings
DASHBOARD_USERNAME = os.getenv('DASHBOARD_USERNAME', 'admin')
DASHBOARD_PASSWORD = os.getenv('DASHBOARD_PASSWORD', 'Grid@Trading123')
EMOJI_SUPPORT = False  # Set to True if your terminal supports emoji 