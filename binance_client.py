from binance.client import Client
from binance.exceptions import BinanceAPIException
import config
import logging
import math
import time

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

    def format_price(self, symbol, price):
        """Format price according to symbol's precision requirements"""
        precision = self.get_price_precision(symbol)
        return "{:.{}f}".format(float(price), precision)

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
        
        try:
            order = self.client.create_order(
                symbol=symbol,
                side=side,  # SIDE.BUY or SIDE.SELL
                type=Client.ORDER_TYPE_LIMIT,
                timeInForce=Client.TIME_IN_FORCE_GTC,
                quantity=quantity,
                price=formatted_price
            )
            logger.info(f"Placed {side} order for {quantity} {symbol} at {formatted_price}")
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

    def cancel_order(self, order_id, symbol=config.SYMBOL):
        """Cancel an order by its ID"""
        try:
            result = self.client.cancel_order(symbol=symbol, orderId=order_id)
            logger.info(f"Cancelled order {order_id} for {symbol}")
            return result
        except BinanceAPIException as e:
            logger.error(f"Failed to cancel order {order_id}: {e}")
            return None 