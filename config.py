import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Binance API credentials
API_KEY = os.getenv('API_KEY')
API_SECRET = os.getenv('API_SECRET')
TESTNET = os.getenv('BINANCE_TESTNET', 'True').lower() in ('true', 'yes', '1')

# Grid trading parameters - Mode Agresif untuk ADA/USDT dengan modal terbatas
SYMBOL = 'ADAUSDT'      # Trading pair
UPPER_PRICE = 0.81      # Upper price boundary (mode agresif)
LOWER_PRICE = 0.79      # Lower price boundary (mode agresif)
GRID_NUMBER = 4         # Jumlah grid dikurangi untuk disesuaikan dengan modal
GRID_SIZE = (UPPER_PRICE - LOWER_PRICE) / GRID_NUMBER  # Size of each grid

# Order parameters
QUANTITY = 10           # Quantity disesuaikan dengan saldo yang tersedia
ORDER_TYPE = 'LIMIT'    # Order type: LIMIT or MARKET

# Risk management - Mode Agresif
MAX_INVESTMENT = 30     # Menggunakan hampir seluruh USDT yang tersedia
STOP_LOSS_PERCENTAGE = 1 # Mode agresif dengan stop loss yang lebih kecil

# Dashboard settings
DASHBOARD_USERNAME = os.getenv('DASHBOARD_USERNAME', 'admin')
DASHBOARD_PASSWORD = os.getenv('DASHBOARD_PASSWORD', 'Grid@Trading123')
EMOJI_SUPPORT = False   # Set to True if your terminal supports emoji 