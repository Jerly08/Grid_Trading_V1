import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Binance API credentials
API_KEY = os.getenv('API_KEY')
API_SECRET = os.getenv('API_SECRET')
TESTNET = os.getenv('BINANCE_TESTNET', 'True').lower() in ('true', 'yes', '1')

# Grid trading parameters - Dioptimalkan berdasarkan modal dan kondisi pasar terbaru
SYMBOL = 'ADAUSDT'      # Trading pair
UPPER_PRICE = 0.70      # Upper price boundary (sekitar 4% di atas harga saat ini 0.672)
LOWER_PRICE = 0.63      # Lower price boundary (sekitar 6% di bawah harga saat ini 0.672)
GRID_NUMBER = 7         # Ditingkatkan untuk grid lebih ketat dan peluang profit lebih banyak
GRID_SIZE = (UPPER_PRICE - LOWER_PRICE) / GRID_NUMBER  # Size of each grid

# Order parameters
QUANTITY = 21           # Disesuaikan dengan modal yang tersedia (berdasarkan log terbaru)
ORDER_TYPE = 'LIMIT'    # Order type: LIMIT or MARKET

# Binance precision settings
# Jumlah decimal places yang didukung oleh Binance (lihat API docs/exchange info)
QUANTITY_PRECISION = 0  # ADAUSDT menggunakan bilangan bulat, tidak ada desimal untuk quantity
PRICE_PRECISION = 4     # ADAUSDT menggunakan 4 angka desimal untuk price
MIN_NOTIONAL = 10.0     # Minimal order value dalam USDT (untuk ADAUSDT sebaiknya minimal 10 USDT)

# Risk management - Disesuaikan dengan modal tersedia
MAX_INVESTMENT = 180    # Berdasarkan total modal ~237 USDT, dengan buffer untuk fluktuasi
STOP_LOSS_PERCENTAGE = 2.0 # Sedikit ditingkatkan untuk memberi ruang fluktuasi harga

# Dashboard settings
DASHBOARD_USERNAME = os.getenv('DASHBOARD_USERNAME', 'admin')
DASHBOARD_PASSWORD = os.getenv('DASHBOARD_PASSWORD', 'Grid@Trading123')
EMOJI_SUPPORT = False   # Set to True if your terminal supports emoji 