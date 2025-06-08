import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Binance API credentials
API_KEY = os.getenv('API_KEY')
API_SECRET = os.getenv('API_SECRET')
TESTNET = os.getenv('BINANCE_TESTNET', 'True').lower() in ('true', 'yes', '1')

# Grid trading parameters - Optimized untuk ADAUSDT dengan modal yang tersedia
SYMBOL = 'ADAUSDT'      # Trading pair
UPPER_PRICE = 0.69      # Upper price boundary (4% above current price 0.6642)
LOWER_PRICE = 0.64      # Lower price boundary (3.6% below current price 0.6642)
GRID_NUMBER = 5         # Ditingkatkan untuk profit lebih sering dengan range yang lebar
GRID_SIZE = (UPPER_PRICE - LOWER_PRICE) / GRID_NUMBER  # Size of each grid

# Order parameters
QUANTITY = 30           # ADAUSDT quantity untuk memenuhi MIN_NOTIONAL
ORDER_TYPE = 'LIMIT'    # Order type: LIMIT or MARKET

# Binance precision settings - DITAMBAHKAN UNTUK MENGATASI ERROR
# Jumlah decimal places yang didukung oleh Binance (lihat API docs/exchange info)
QUANTITY_PRECISION = 0  # ADAUSDT menggunakan bilangan bulat, tidak ada desimal untuk quantity
PRICE_PRECISION = 4     # ADAUSDT menggunakan 4 angka desimal untuk price
MIN_NOTIONAL = 10.0     # Minimal order value dalam USDT (untuk ADAUSDT sebaiknya minimal 10 USDT)

# Risk management - Menggunakan modal yang tersedia dengan lebih optimal
MAX_INVESTMENT = 200    # Sesuai dengan total USDT Anda (129.72 Free + 64.00 Locked)
STOP_LOSS_PERCENTAGE = 1.5 # Sedikit ditingkatkan untuk menghindari stop loss terlalu cepat

# Dashboard settings
DASHBOARD_USERNAME = os.getenv('DASHBOARD_USERNAME', 'admin')
DASHBOARD_PASSWORD = os.getenv('DASHBOARD_PASSWORD', 'Grid@Trading123')
EMOJI_SUPPORT = False   # Set to True if your terminal supports emoji 