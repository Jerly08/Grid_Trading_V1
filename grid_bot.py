import time
import logging
import numpy as np
from binance.exceptions import BinanceAPIException
from binance_client import BinanceClient
from risk_management import RiskManager
import config
import datetime
import json
import os

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

class GridTradingBot:
    # Simpan instance untuk diakses oleh dashboard
    instance = None
    
    def __init__(self):
        """Initialize the grid trading bot"""
        # Set instance untuk referensi global
        GridTradingBot.instance = self
        
        self.client = BinanceClient()
        self.risk_manager = RiskManager(self.client)
        self.symbol = config.SYMBOL
        self.upper_price = config.UPPER_PRICE
        self.lower_price = config.LOWER_PRICE
        self.grid_number = config.GRID_NUMBER
        self.grid_size = config.GRID_SIZE
        self.quantity = config.QUANTITY
        
        # Calculate price levels for the grid
        self.grid_prices = self._calculate_grid_prices()
        
        # Track orders
        self.buy_orders = {}  # Key: price, Value: order_id
        self.sell_orders = {}  # Key: price, Value: order_id
        
        # Price tracking
        self.last_price = None
        self.price_history = []  # Store recent price history, format: {"time": ISO-string, "price": float, "usdt_idr": float}
        self.price_update_time = datetime.datetime.now()
        self.last_grid_adjustment = datetime.datetime.now()
        
        # Profit tracking
        self.total_profit = 0
        self.trades = []
        
        # Track entry prices for stop loss calculation
        self.entry_prices = {}  # Key: price, Value: entry_timestamp
        
        # Initial price for overall stop loss
        self.initial_price = None
        
        # Load previous state if exists
        self._load_state()
        
        logger.info(f"Grid bot initialized for {self.symbol}")
        logger.info(f"Price range: {self.lower_price} - {self.upper_price}")
        logger.info(f"Grid number: {self.grid_number}, Grid size: {self.grid_size}")
        logger.info(f"Order quantity: {self.quantity}")
        if self.total_profit > 0:
            logger.info(f"Loaded previous profit: {self.total_profit} USDT")

    def _calculate_grid_prices(self):
        """Calculate the price levels for the grid"""
        return np.linspace(self.lower_price, self.upper_price, self.grid_number + 1)

    def _load_state(self):
        """Load previous state from file if exists"""
        state_file = f"grid_state_{self.symbol}.json"
        if os.path.exists(state_file):
            try:
                with open(state_file, 'r') as f:
                    state = json.load(f)
                    self.total_profit = state.get('total_profit', 0)
                    self.trades = state.get('trades', [])
                    self.last_price = state.get('last_price', None)
                    logger.info(f"Loaded previous state from {state_file}")
                    logger.info(f"Loaded previous profit: {self.total_profit:.4f} USDT")
            except Exception as e:
                logger.error(f"Failed to load previous state: {e}")

    def _save_state(self):
        """Save current state to file"""
        state_file = f"grid_state_{self.symbol}.json"
        try:
            state = {
                'total_profit': self.total_profit,
                'trades': self.trades,
                'last_update': datetime.datetime.now().isoformat(),
                'price_range': [self.lower_price, self.upper_price],
                'grid_number': self.grid_number,
                'last_price': self.last_price  # Simpan harga terakhir dalam state
            }
            with open(state_file, 'w') as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save state: {e}")

    def setup_grid(self):
        """Setup the initial grid orders"""
        logger.info("Setting up grid orders...")
        
        # Check investment limit before starting
        if not self.risk_manager.check_investment_limit():
            logger.warning("Investment limit would be exceeded. Adjusting grid parameters...")
            # Implementasi logika untuk mengurangi ukuran grid atau kuantitas order bisa ditambahkan di sini
        
        # Check account balance
        quote_asset = self.symbol[len(self.symbol)-4:]  # USDT for ADAUSDT
        base_asset = self.symbol[:len(self.symbol)-4]   # ADA for ADAUSDT
        
        usdt_balance = self.client.get_account_balance(quote_asset)
        ada_balance = self.client.get_account_balance(base_asset)
        
        usdt_free = usdt_balance['free'] if usdt_balance else 0
        usdt_locked = usdt_balance['locked'] if usdt_balance else 0
        ada_free = ada_balance['free'] if ada_balance else 0
        ada_locked = ada_balance['locked'] if ada_balance else 0
        
        # Log balance before grid setup
        logger.info(f"[BALANCE] {quote_asset}: {usdt_free:.4f} (Free) + {usdt_locked:.4f} (Locked) | {base_asset}: {ada_free:.4f} (Free) + {ada_locked:.4f} (Locked)")
        
        # Calculate minimum balance required
        grid_below_current = 0
        grid_above_current = 0
        
        # Get current price
        current_price = self.client.get_symbol_price(self.symbol)
        if not current_price:
            logger.error("Failed to get current price. Grid setup aborted.")
            return False
        
        self.last_price = current_price
        # Set initial price for overall stop loss
        self.initial_price = current_price
        
        self.price_history.append({
            "time": datetime.datetime.now().isoformat(),
            "price": current_price,
            "usdt_idr": self.client.get_usdt_idr_rate()
        })
        
        # Check market volatility
        if self.risk_manager.monitor_market_volatility(time_window=3600, threshold=5.0):
            logger.warning("High market volatility detected. Consider adjusting grid parameters.")
            # Implementasi penyesuaian parameter grid berdasarkan volatilitas bisa ditambahkan di sini
        
        # Count grid levels above and below current price
        for price in self.grid_prices:
            if price < current_price:
                grid_below_current += 1
            elif price > current_price:
                grid_above_current += 1
        
        # Calculate required balances
        required_usdt = grid_below_current * self.quantity * current_price
        required_ada = grid_above_current * self.quantity
        
        # Log required balances
        logger.info(f"[REQUIREMENT] Need {required_usdt:.4f} {quote_asset} for {grid_below_current} buy orders")
        logger.info(f"[REQUIREMENT] Need {required_ada:.4f} {base_asset} for {grid_above_current} sell orders")
        
        # Check if balance is sufficient
        if usdt_free < required_usdt:
            logger.warning(f"Insufficient {quote_asset} balance. Have: {usdt_free:.4f}, Need: {required_usdt:.4f}")
        
        if ada_free < required_ada:
            logger.warning(f"Insufficient {base_asset} balance. Have: {ada_free:.4f}, Need: {required_ada:.4f}")
        
        # Adjust grid around current price if needed
        if current_price < self.lower_price or current_price > self.upper_price:
            logger.info(f"Current price {current_price} is outside grid range. Adjusting grid...")
            # Center grid around current price with 2% buffer on each side
            self.lower_price = current_price * 0.98
            self.upper_price = current_price * 1.02
            self.grid_size = (self.upper_price - self.lower_price) / self.grid_number
            self.grid_prices = self._calculate_grid_prices()
            logger.info(f"New grid range: {self.lower_price} - {self.upper_price}")
        
        logger.info(f"Current {self.symbol} price: {current_price}")
        
        # Cancel all existing open orders
        open_orders = self.client.get_open_orders(self.symbol)
        if open_orders:
            for order in open_orders:
                self.client.cancel_order(order['orderId'], self.symbol)
            logger.info("Cancelled all existing orders")
        
        # Place buy orders below current price
        buy_orders_placed = 0
        for price in self.grid_prices:
            if price < current_price:
                order = self.client.place_limit_order(
                    symbol=self.symbol,
                    side="BUY",
                    quantity=self.quantity,
                    price=price
                )
                if order:
                    self.buy_orders[price] = order['orderId']
                    buy_orders_placed += 1
        
        # Place sell orders above current price
        sell_orders_placed = 0
        for price in self.grid_prices:
            if price > current_price:
                order = self.client.place_limit_order(
                    symbol=self.symbol,
                    side="SELL",
                    quantity=self.quantity,
                    price=price
                )
                if order:
                    self.sell_orders[price] = order['orderId']
                    sell_orders_placed += 1
        
        logger.info(f"Grid setup complete. {buy_orders_placed} buy orders and {sell_orders_placed} sell orders placed.")
        return True

    def check_filled_orders(self):
        """Check for filled orders and place new orders accordingly"""
        try:
            # Get current open orders
            open_orders = self.client.get_open_orders(self.symbol)
            if open_orders is None:
                logger.error("Failed to get open orders")
                return
            
            # Convert to set of order IDs for easier lookup
            open_order_ids = {order['orderId'] for order in open_orders}
            
            # Get current price for price tracking and risk assessment
            current_price = self.client.get_symbol_price(self.symbol)
            if current_price:
                self.last_price = current_price
                self.price_history.append({
                    "time": datetime.datetime.now().isoformat(), 
                    "price": current_price,
                    "usdt_idr": self.client.get_usdt_idr_rate()
                })
                self.price_update_time = datetime.datetime.now()
                
                # Keep only recent price history to save memory
                if len(self.price_history) > 1000:
                    self.price_history = self.price_history[-1000:]
            
            # Check overall stop loss
            if self.initial_price and self.risk_manager.check_stop_loss(self.initial_price):
                logger.warning("Overall stop loss triggered!")
                self.risk_manager.execute_emergency_exit()
                return
            
            # Check if any buy orders have been filled
            for price, order_id in list(self.buy_orders.items()):
                if order_id not in open_order_ids:
                    # Buy order was filled, place a sell order at the next price level
                    sell_price = price + self.grid_size
                    
                    # Record entry price for this position
                    self.entry_prices[price] = time.time()
                    
                    # Calculate profit for this grid level
                    profit = self.grid_size * self.quantity
                    self.total_profit += profit
                    profit_percentage = (self.grid_size / price) * 100
                    
                    # Log the filled buy order
                    logger.info(f"Buy order at {price} filled. Potential profit at sell price {sell_price}: {profit:.4f} USDT ({profit_percentage:.2f}%)")
                    
                    # Check investment limit before placing new order
                    if not self.risk_manager.check_investment_limit():
                        logger.warning("Investment limit reached. Not placing sell order.")
                        continue
                    
                    # Place a new sell order at the next price level
                    order = self.client.place_limit_order(
                        symbol=self.symbol,
                        side="SELL",
                        quantity=self.quantity,
                        price=sell_price
                    )
                    
                    if order:
                        self.sell_orders[sell_price] = order['orderId']
                        
                        # Record the trade
                        trade = {
                            'time': datetime.datetime.now().isoformat(),
                            'side': 'BUY',
                            'price': price,
                            'quantity': self.quantity,
                            'value': price * self.quantity,
                            'next_target': sell_price,
                            'potential_profit': profit
                        }
                        self.trades.append(trade)
                        
                        # Save updated state
                        self._save_state()
                    
                    # Remove the filled buy order from our tracking
                    del self.buy_orders[price]
            
            # Check if any sell orders have been filled
            for price, order_id in list(self.sell_orders.items()):
                if order_id not in open_order_ids:
                    # Sell order was filled, place a buy order at the next price level
                    buy_price = price - self.grid_size
                    
                    # Calculate profit for this grid level
                    profit = self.grid_size * self.quantity
                    self.total_profit += profit
                    profit_percentage = (self.grid_size / buy_price) * 100
                    
                    # Log the filled sell order
                    logger.info(f"Sell order at {price} filled. Profit: {profit:.4f} USDT ({profit_percentage:.2f}%). Total profit: {self.total_profit:.4f} USDT")
                    
                    # Check investment limit before placing new order
                    if not self.risk_manager.check_investment_limit():
                        logger.warning("Investment limit reached. Not placing buy order.")
                        continue
                    
                    # Place a new buy order at the next price level
                    order = self.client.place_limit_order(
                        symbol=self.symbol,
                        side="BUY",
                        quantity=self.quantity,
                        price=buy_price
                    )
                    
                    if order:
                        self.buy_orders[buy_price] = order['orderId']
                        
                        # Record the trade
                        trade = {
                            'time': datetime.datetime.now().isoformat(),
                            'side': 'SELL',
                            'price': price,
                            'quantity': self.quantity,
                            'value': price * self.quantity,
                            'next_target': buy_price,
                            'actual_profit': profit,
                            'total_profit': self.total_profit
                        }
                        self.trades.append(trade)
                        
                        # Save updated state
                        self._save_state()
                    
                    # Remove the filled sell order from our tracking
                    del self.sell_orders[price]
                    
                    # Remove corresponding entry price
                    if buy_price in self.entry_prices:
                        del self.entry_prices[buy_price]
        
        except Exception as e:
            logger.error(f"Error checking filled orders: {e}")

    def _log_current_balance(self):
        """Log current account balance"""
        quote_asset = self.symbol[len(self.symbol)-4:]  # USDT for ADAUSDT
        base_asset = self.symbol[:len(self.symbol)-4]   # ADA for ADAUSDT
        
        usdt_balance = self.client.get_account_balance(quote_asset)
        ada_balance = self.client.get_account_balance(base_asset)
        
        usdt_free = usdt_balance['free'] if usdt_balance else 0
        usdt_locked = usdt_balance['locked'] if usdt_balance else 0
        ada_free = ada_balance['free'] if ada_balance else 0
        ada_locked = ada_balance['locked'] if ada_balance else 0
        
        # Log balance information
        logger.info(f"[BALANCE] {quote_asset}: {usdt_free:.4f} (Free) + {usdt_locked:.4f} (Locked) | {base_asset}: {ada_free:.4f} (Free) + {ada_locked:.4f} (Locked)")

    def adjust_grid(self):
        """Adjust grid parameters based on market conditions"""
        try:
            # Get current price
            current_price = self.client.get_symbol_price(self.symbol)
            if not current_price:
                logger.error("Failed to get current price for grid adjustment")
                return
            
            # Check if price is outside grid range
            if current_price < self.lower_price * 0.95 or current_price > self.upper_price * 1.05:
                logger.info(f"Price ({current_price}) has moved significantly outside grid range ({self.lower_price} - {self.upper_price}). Adjusting grid...")
                
                # Check market volatility before adjusting
                if self.risk_manager.monitor_market_volatility():
                    logger.warning("High market volatility detected during grid adjustment")
                
                # Cancel all existing orders
                open_orders = self.client.get_open_orders(self.symbol)
                if open_orders:
                    for order in open_orders:
                        self.client.cancel_order(order['orderId'], self.symbol)
                    logger.info("Cancelled all existing orders for grid adjustment")
                
                # Reset order tracking
                self.buy_orders = {}
                self.sell_orders = {}
                
                # Set new grid around current price
                self.lower_price = current_price * 0.98
                self.upper_price = current_price * 1.02
                self.grid_size = (self.upper_price - self.lower_price) / self.grid_number
                self.grid_prices = self._calculate_grid_prices()
                
                logger.info(f"New grid range: {self.lower_price} - {self.upper_price}")
                
                # Set up new grid
                self.setup_grid()
                
                # Update last grid adjustment time
                self.last_grid_adjustment = datetime.datetime.now()
                
            # Log current grid status
            logger.info(f"Current grid status: {len(self.buy_orders)} buy orders, {len(self.sell_orders)} sell orders")
            logger.info(f"Grid range: {self.lower_price} - {self.upper_price}, Current price: {current_price}")
        
        except Exception as e:
            logger.error(f"Error adjusting grid: {e}")

    def run(self):
        """Run the grid trading bot"""
        logger.info("Starting grid trading bot...")
        
        # Set up the initial grid
        if not self.setup_grid():
            logger.error("Failed to set up grid. Exiting.")
            return
        
        try:
            # Main bot loop
            while True:
                try:
                    # Check for filled orders
                    self.check_filled_orders()
                    
                    # Check if we need to adjust the grid (every 15 minutes)
                    now = datetime.datetime.now()
                    if (now - self.last_grid_adjustment).total_seconds() > 900:  # 15 minutes
                        self.adjust_grid()
                        self.last_grid_adjustment = now
                    
                    # Log current balance occasionally (every hour)
                    if not hasattr(self, 'last_balance_log') or (now - self.last_balance_log).total_seconds() > 3600:
                        self._log_current_balance()
                        self.last_balance_log = now
                    
                    # Save state occasionally
                    if not hasattr(self, 'last_state_save') or (now - self.last_state_save).total_seconds() > 300:
                        self._save_state()
                        self.last_state_save = now
                    
                    # Sleep to avoid API rate limits
                    time.sleep(10)
                    
                except Exception as e:
                    logger.error(f"Error in bot main loop: {e}")
                    time.sleep(30)  # Sleep longer on error
        finally:
            # Hapus instance referensi ketika bot berhenti
            if GridTradingBot.instance == self:
                GridTradingBot.instance = None
            logger.info(f"Grid trading bot stopped. Total profit: {self.total_profit:.4f} USDT")

if __name__ == "__main__":
    bot = GridTradingBot()
    bot.run() 