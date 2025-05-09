from binance.client import Client
from binance.exceptions import BinanceAPIException
import config
import logging
import math
import time
import uuid
import numpy as np

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
            
            # Untuk mode simulasi
            if config.SIMULATION_MODE:
                logger.info("Running in SIMULATION MODE - No real orders will be placed")
                
                # Saldo simulasi - dapat disesuaikan sesuai kebutuhan
                self.simulated_balance = {
                    'USDT': 32.0,  # 500k IDR
                    'ADA': 40.0    # Sedikit ADA untuk trading
                }
                
                # Order simulasi
                self.simulated_orders = {}  # order_id: order_details
                # Order fill history
                self.simulated_order_history = []
                # Flag to force simulation even with insufficient balance
                self.force_simulation = False
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
        if config.SIMULATION_MODE:
            # Return simulated balance
            if asset:
                balance_value = self.simulated_balance.get(asset, 0)
                return {
                    'free': balance_value,
                    'locked': 0
                } if balance_value > 0 else None
            else:
                return {
                    asset: {
                        'free': amount,
                        'locked': 0
                    } 
                    for asset, amount in self.simulated_balance.items() if amount > 0
                }
        
        # Real balance from Binance
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
        
        if config.SIMULATION_MODE:
            # Simulasi order
            try:
                # Validasi saldo
                base_asset = symbol.replace('USDT', '')
                
                if side == "BUY":
                    # Cek saldo USDT
                    cost = float(quantity) * float(formatted_price)
                    if self.simulated_balance.get('USDT', 0) < cost:
                        logger.warning(f"[SIMULATION] Insufficient USDT balance for BUY order. Required: {cost}, Available: {self.simulated_balance.get('USDT', 0)}")
                        if not self.force_simulation:
                            return None
                    else:
                        # Deduct USDT from simulated balance
                        self.simulated_balance['USDT'] -= cost
                    
                else:  # SELL
                    # Cek saldo base asset (misalnya ADA)
                    if self.simulated_balance.get(base_asset, 0) < float(quantity):
                        logger.warning(f"[SIMULATION] Insufficient {base_asset} balance for SELL order. Required: {quantity}, Available: {self.simulated_balance.get(base_asset, 0)}")
                        if not self.force_simulation:
                            return None
                    else:
                        # Deduct base asset from simulated balance
                        self.simulated_balance[base_asset] -= float(quantity)
                
                # Buat order ID unik
                order_id = str(uuid.uuid4())
                
                # Buat order simulasi
                order = {
                    'orderId': order_id,
                    'symbol': symbol,
                    'side': side,
                    'type': 'LIMIT',
                    'timeInForce': 'GTC',
                    'quantity': float(quantity),
                    'price': float(formatted_price),
                    'status': 'NEW',
                    'time': int(time.time() * 1000)
                }
                
                self.simulated_orders[order_id] = order
                logger.info(f"[SIMULATION] Placed {side} order for {quantity} {symbol} at {formatted_price}")
                
                # Auto-fill the order with 50% probability in simulation
                if np.random.random() > 0.5:
                    self.simulate_order_fill(order_id)
                
                return order
                
            except Exception as e:
                logger.error(f"[SIMULATION] Error placing simulated order: {e}")
                return None
        
        # Real order to Binance
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
                logger.info("Consider using SIMULATION_MODE=True if you want to test without funds")
                
                # Option to auto-switch to simulation mode
                if not config.SIMULATION_MODE:
                    logger.info("Auto-switching to simulation mode due to insufficient balance")
                    config.SIMULATION_MODE = True
                    self.simulated_balance = {
                        'USDT': 32.0,  # 500k IDR
                        'ADA': 40.0    # Initial ADA for trading
                    }
                    self.simulated_orders = {}
                    self.simulated_order_history = []
                    self.force_simulation = True
                    # Try again in simulation mode
                    return self.place_limit_order(symbol, side, quantity, price)
            else:
                logger.error(f"Failed to place {side} order: {e}")
            return None

    def get_open_orders(self, symbol=config.SYMBOL):
        """Get all open orders for a symbol"""
        if config.SIMULATION_MODE:
            # Return simulated open orders
            return [
                order for order_id, order in self.simulated_orders.items()
                if order['symbol'] == symbol and order['status'] == 'NEW'
            ]
        
        # Real orders from Binance
        try:
            orders = self.client.get_open_orders(symbol=symbol)
            return orders
        except BinanceAPIException as e:
            logger.error(f"Failed to get open orders: {e}")
            return None

    def cancel_order(self, order_id, symbol=config.SYMBOL):
        """Cancel an order by its ID"""
        if config.SIMULATION_MODE:
            # Cancel simulated order
            if order_id in self.simulated_orders:
                self.simulated_orders[order_id]['status'] = 'CANCELED'
                logger.info(f"[SIMULATION] Cancelled order {order_id} for {symbol}")
                return self.simulated_orders[order_id]
            logger.warning(f"[SIMULATION] Order {order_id} not found for cancellation")
            return None
        
        # Real cancel on Binance
        try:
            result = self.client.cancel_order(symbol=symbol, orderId=order_id)
            logger.info(f"Cancelled order {order_id} for {symbol}")
            return result
        except BinanceAPIException as e:
            logger.error(f"Failed to cancel order {order_id}: {e}")
            return None
    
    def simulate_order_fill(self, order_id, fill_price=None):
        """Simulate an order being filled"""
        if order_id not in self.simulated_orders:
            logger.warning(f"[SIMULATION] Order {order_id} not found for simulated fill")
            return False
            
        order = self.simulated_orders[order_id]
        if fill_price is None:
            fill_price = order['price']  # Use order price if no fill price specified
            
        # Mark order as filled
        order['status'] = 'FILLED'
        order['executedQty'] = order['quantity']
        order['fillTime'] = int(time.time() * 1000)
        
        # Adjust balances based on the filled order
        base_asset = order['symbol'].replace('USDT', '')
        if order['side'] == 'BUY':
            # When buy order is filled, increase base asset
            self.simulated_balance[base_asset] = self.simulated_balance.get(base_asset, 0) + order['quantity']
        else:  # SELL
            # When sell order is filled, increase USDT
            order_value = order['quantity'] * fill_price
            self.simulated_balance['USDT'] = self.simulated_balance.get('USDT', 0) + order_value
            
        # Add to order history
        self.simulated_order_history.append(order.copy())
        
        # Remove from active orders
        del self.simulated_orders[order_id]
        
        logger.info(f"[SIMULATION] Order {order_id} filled at price {fill_price}")
        return True 