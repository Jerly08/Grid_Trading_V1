import time
import logging
import numpy as np
from binance.exceptions import BinanceAPIException
from binance_client import BinanceClient
from risk_management import RiskManager
import config

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

class EnhancedGridTradingBot:
    def __init__(self):
        """Initialize the enhanced grid trading bot with risk management"""
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
        
        # Track entry prices for stop loss calculation
        self.entry_prices = {}  # Key: price, Value: entry_timestamp
        
        # Initial price for overall stop loss
        self.initial_price = None
        
        logger.info(f"Enhanced grid bot initialized for {self.symbol}")
        logger.info(f"Price range: {self.lower_price} - {self.upper_price}")
        logger.info(f"Grid number: {self.grid_number}, Grid size: {self.grid_size}")
        logger.info(f"Order quantity: {self.quantity}")

    def _calculate_grid_prices(self):
        """Calculate the price levels for the grid"""
        return np.linspace(self.lower_price, self.upper_price, self.grid_number + 1)

    def setup_grid(self):
        """Setup the initial grid orders with risk checks"""
        logger.info("Setting up grid orders...")
        
        # Check investment limit before starting
        if not self.risk_manager.check_investment_limit():
            logger.warning("Investment limit would be exceeded. Adjusting grid parameters...")
            # Here you could implement logic to reduce grid size or order quantity
            # For now, we'll just continue with a warning
        
        # Get current price
        current_price = self.client.get_symbol_price(self.symbol)
        if not current_price:
            logger.error("Failed to get current price. Grid setup aborted.")
            return False
        
        # Set initial price for overall stop loss
        self.initial_price = current_price
        
        logger.info(f"Current {self.symbol} price: {current_price}")
        
        # Check market volatility
        if self.risk_manager.monitor_market_volatility(time_window=3600, threshold=5.0):
            logger.warning("High market volatility detected. Consider adjusting grid parameters.")
            # Here you could automatically adjust grid parameters based on volatility
        
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
        """Check for filled orders and place new orders accordingly with risk management"""
        # Get current open orders
        open_orders = self.client.get_open_orders(self.symbol)
        if open_orders is None:
            logger.error("Failed to get open orders")
            return
        
        # Convert to dict of order_id: order
        open_order_ids = {order['orderId']: order for order in open_orders}
        
        # Get current price for risk assessment
        current_price = self.client.get_symbol_price(self.symbol)
        if not current_price:
            logger.error("Failed to get current price for risk assessment")
            return
        
        # Check overall stop loss
        if self.initial_price and self.risk_manager.check_stop_loss(self.initial_price):
            logger.warning("Overall stop loss triggered!")
            self.risk_manager.execute_emergency_exit()
            return
        
        # Check buy orders
        for price, order_id in list(self.buy_orders.items()):
            if order_id not in open_order_ids:
                # Buy order was filled, place sell order at next grid level up
                sell_price = price + self.grid_size
                logger.info(f"Buy order at {price} was filled. Placing sell order at {sell_price}")
                
                # Record entry price
                self.entry_prices[price] = time.time()
                
                # Check investment limit before placing new order
                if not self.risk_manager.check_investment_limit():
                    logger.warning("Investment limit reached. Not placing sell order.")
                    continue
                
                order = self.client.place_limit_order(
                    symbol=self.symbol,
                    side="SELL",
                    quantity=self.quantity,
                    price=sell_price
                )
                if order:
                    self.sell_orders[sell_price] = order['orderId']
                
                # Remove the filled buy order from our tracking
                del self.buy_orders[price]
        
        # Check sell orders
        for price, order_id in list(self.sell_orders.items()):
            if order_id not in open_order_ids:
                # Sell order was filled, place buy order at next grid level down
                buy_price = price - self.grid_size
                logger.info(f"Sell order at {price} was filled. Placing buy order at {buy_price}")
                
                # Check investment limit before placing new order
                if not self.risk_manager.check_investment_limit():
                    logger.warning("Investment limit reached. Not placing buy order.")
                    continue
                
                order = self.client.place_limit_order(
                    symbol=self.symbol,
                    side="BUY",
                    quantity=self.quantity,
                    price=buy_price
                )
                if order:
                    self.buy_orders[buy_price] = order['orderId']
                
                # Remove the filled sell order from our tracking
                del self.sell_orders[price]
                
                # Remove corresponding entry price
                if buy_price in self.entry_prices:
                    del self.entry_prices[buy_price]

    def adjust_grid(self):
        """Adjust grid parameters based on market conditions"""
        current_price = self.client.get_symbol_price(self.symbol)
        if not current_price:
            logger.error("Failed to get current price for grid adjustment")
            return
        
        # Check if price is near grid boundaries
        if current_price > self.upper_price * 0.95:
            logger.info(f"Price approaching upper grid boundary. Considering grid adjustment.")
            # Could implement logic to shift grid upward
        
        elif current_price < self.lower_price * 1.05:
            logger.info(f"Price approaching lower grid boundary. Considering grid adjustment.")
            # Could implement logic to shift grid downward
        
        # Additional adjustment based on volatility
        self.risk_manager.monitor_market_volatility()

    def run(self):
        """Run the enhanced grid trading bot with risk management"""
        if not self.setup_grid():
            logger.error("Failed to setup grid. Exiting.")
            return
        
        logger.info("Enhanced grid trading bot is running...")
        
        try:
            while True:
                # Check filled orders and maintain grid
                self.check_filled_orders()
                
                # Periodically adjust grid if needed
                if int(time.time()) % 3600 < 60:  # Once per hour
                    self.adjust_grid()
                
                # Wait for some time before checking again
                time.sleep(60)  # Check every minute
        except KeyboardInterrupt:
            logger.info("Bot stopped by user")
        except Exception as e:
            logger.error(f"An error occurred: {e}")
        finally:
            # Cancel all open orders when shutting down
            open_orders = self.client.get_open_orders(self.symbol)
            if open_orders:
                for order in open_orders:
                    self.client.cancel_order(order['orderId'], self.symbol)
                logger.info("Cancelled all open orders")
            logger.info("Enhanced grid trading bot stopped")

if __name__ == "__main__":
    bot = EnhancedGridTradingBot()
    bot.run() 