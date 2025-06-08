from binance.client import Client
from binance.exceptions import BinanceAPIException
import config
import logging
import math
import time
import requests

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class BinanceClient:
    def __init__(self):
        """Initialize Binance client with API credentials"""
        try:
            self.client = Client(config.API_KEY, config.API_SECRET, testnet=config.TESTNET)
            account_info = self.client.get_account()
            logger.info(f"Successfully connected to Binance{'_testnet' if config.TESTNET else ''}")
            logger.info(f"Account status: {account_info['accountType']}")
            
            # Get symbol info for price precision
            self.exchange_info = {}
            self._load_exchange_info()
            
        except BinanceAPIException as e:
            if "Invalid API-key" in str(e):
                logger.error("API Key Error: Pastikan API key valid dan memiliki izin yang benar")
                logger.error("1. Periksa API key dan secret")
                logger.error("2. Pastikan API key memiliki izin 'Enable Reading' dan 'Enable Spot & Margin Trading'")
                logger.error("3. Jika menggunakan pembatasan IP, tambahkan IP server ke whitelist")
                logger.error(f"Error detail: {e}")
            else:
                logger.error(f"Failed to connect to Binance API: {e}")
            raise

    def _load_exchange_info(self):
        """Load exchange info for symbol precision"""
        try:
            info = self.client.get_exchange_info()
            for symbol_data in info['symbols']:
                self.exchange_info[symbol_data['symbol']] = {
                    'baseAsset': symbol_data['baseAsset'],
                    'quoteAsset': symbol_data['quoteAsset'],
                    'filters': symbol_data['filters']
                }
            logger.info(f"Loaded exchange info for {len(self.exchange_info)} symbols")
        except BinanceAPIException as e:
            logger.error(f"Failed to load exchange info: {e}")

    def get_price_precision(self, symbol):
        """Get price precision for a symbol"""
        if symbol not in self.exchange_info:
            # Default precision if symbol not found
            return 2
        
        for filter_data in self.exchange_info[symbol]['filters']:
            if filter_data['filterType'] == 'PRICE_FILTER':
                tick_size = float(filter_data['tickSize'])
                # Calculate precision from tick size (e.g. 0.00001 -> 5)
                precision = int(round(-math.log10(float(tick_size))))
                return precision
        return 2  # Default precision

    def get_quantity_precision(self, symbol):
        """Get quantity precision for a symbol"""
        # Preferentially use configuration if available
        if symbol == config.SYMBOL and hasattr(config, 'QUANTITY_PRECISION'):
            return config.QUANTITY_PRECISION
        
        # Otherwise try to get from exchange info
        if symbol not in self.exchange_info:
            # Default precision if symbol not found
            return 2
        
        for filter_data in self.exchange_info[symbol]['filters']:
            if filter_data['filterType'] == 'LOT_SIZE':
                step_size = float(filter_data['stepSize'])
                # Calculate precision from step size (e.g. 0.00001 -> 5)
                if step_size == 1.0:  # Whole number precision
                    return 0
                precision = int(round(-math.log10(float(step_size))))
                return precision
        return 2  # Default precision

    def format_price(self, symbol, price):
        """Format price according to symbol's precision requirements"""
        precision = self.get_price_precision(symbol)
        return "{:.{}f}".format(float(price), precision)

    def format_quantity(self, symbol, quantity):
        """Format quantity according to symbol's precision requirements"""
        precision = self.get_quantity_precision(symbol)
        formatted_quantity = "{:.{}f}".format(float(quantity), precision)
        # Remove trailing zeros for integer values
        if precision == 0:
            return str(int(float(formatted_quantity)))
        return formatted_quantity

    def get_symbol_price(self, symbol=config.SYMBOL):
        """Get current price of a symbol"""
        try:
            ticker = self.client.get_symbol_ticker(symbol=symbol)
            return float(ticker['price'])
        except BinanceAPIException as e:
            logger.error(f"Failed to get {symbol} price: {e}")
            return None

    def get_account_balance(self, asset=None):
        """Get account balance for a specific asset or all assets"""
        try:
            account = self.client.get_account()
            balances = account['balances']
            
            if asset:
                for balance in balances:
                    if balance['asset'] == asset:
                        return {
                            'free': float(balance['free']),
                            'locked': float(balance['locked'])
                        }
                logger.warning(f"Asset {asset} not found in account")
                return None
            else:
                return {
                    bal['asset']: {
                        'free': float(bal['free']), 
                        'locked': float(bal['locked'])
                    } 
                    for bal in balances if float(bal['free']) > 0 or float(bal['locked']) > 0
                }
        except BinanceAPIException as e:
            logger.error(f"Failed to get account balance: {e}")
            return None

    def place_limit_order(self, symbol, side, quantity, price):
        """Place a limit order"""
        # Format price to match symbol's precision requirements
        formatted_price = self.format_price(symbol, price)
        
        # Format quantity to match symbol's precision requirements (NEW)
        formatted_quantity = self.format_quantity(symbol, quantity)
        
        try:
            order = self.client.create_order(
                symbol=symbol,
                side=side,  # SIDE.BUY or SIDE.SELL
                type=Client.ORDER_TYPE_LIMIT,
                timeInForce=Client.TIME_IN_FORCE_GTC,
                quantity=formatted_quantity,
                price=formatted_price
            )
            logger.info(f"Placed {side} order for {formatted_quantity} {symbol} at {formatted_price}")
            return order
        except BinanceAPIException as e:
            if "Account has insufficient balance" in str(e):
                logger.error(f"Insufficient balance error: {e}")
                logger.info("Pastikan akun memiliki saldo yang cukup untuk trading")
            else:
                logger.error(f"Failed to place {side} order: {e}")
            return None

    def get_open_orders(self, symbol=config.SYMBOL):
        """Get all open orders for a symbol"""
        try:
            orders = self.client.get_open_orders(symbol=symbol)
            return orders
        except BinanceAPIException as e:
            logger.error(f"Failed to get open orders: {e}")
            return None

    def get_usdt_idr_rate(self):
        """Mendapatkan harga USDT/IDR dari API publik untuk memastikan data realtime"""
        try:
            # Coba dapatkan dari API Indodax (Bursa crypto Indonesia)
            # API Indodax untuk USDT/IDR
            response = requests.get('https://indodax.com/api/ticker/usdtidr', timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                # Ambil harga terakhir (last) dari ticker
                if 'ticker' in data and 'last' in data['ticker']:
                    usdt_idr_rate = float(data['ticker']['last'])
                    logger.info(f"Realtime USDT/IDR dari Indodax: {usdt_idr_rate}")
                    return usdt_idr_rate
            
            # Fallback ke Binance P2P rate (estimasi)
            # Coba dapatkan dari API lain
            response = requests.get('https://api.binance.com/api/v3/ticker/price?symbol=USDTBIDR', timeout=5)
            if response.status_code == 200:
                data = response.json()
                if 'price' in data:
                    # BIDR digunakan sebagai proxy untuk IDR di Binance (1000 BIDR = 1000 IDR)
                    usdt_bidr_rate = float(data['price'])
                    logger.info(f"Realtime USDT/BIDR dari Binance: {usdt_bidr_rate}")
                    return usdt_bidr_rate
                    
            # Fallback ke nilai yang lebih akurat berdasarkan kurs pasar terkini
            return 16350.0  # Update dari nilai statis 15700 ke nilai yang lebih akurat per Mei 2025
            
        except Exception as e:
            # Log error hanya sekali setiap jam untuk menghindari spam log
            current_time = int(time.time())
            if not hasattr(self, 'last_idr_error_time') or current_time - self.last_idr_error_time > 3600:
                logger.warning(f"Gagal mendapatkan harga USDT/IDR realtime: {e}")
                self.last_idr_error_time = current_time
            return 16350.0  # Nilai fallback yang lebih akurat

    def cancel_order(self, order_id, symbol=config.SYMBOL):
        """Cancel an order by its ID"""
        try:
            result = self.client.cancel_order(symbol=symbol, orderId=order_id)
            logger.info(f"Cancelled order {order_id} for {symbol}")
            return result
        except BinanceAPIException as e:
            logger.error(f"Failed to cancel order {order_id}: {e}")
            return None 