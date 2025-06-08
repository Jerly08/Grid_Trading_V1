import logging
import time
from binance.exceptions import BinanceAPIException
import config

# Configure logging
logger = logging.getLogger(__name__)

class RiskManager:
    def __init__(self, binance_client):
        """Initialize the risk manager with a Binance client instance"""
        self.client = binance_client
        self.symbol = config.SYMBOL
        self.max_investment = config.MAX_INVESTMENT
        self.stop_loss_percentage = config.STOP_LOSS_PERCENTAGE
        
        # Extract base and quote assets from symbol (e.g., BTCUSDT -> BTC, USDT)
        if 'USDT' in self.symbol:
            self.base_asset = self.symbol.replace('USDT', '')
            self.quote_asset = 'USDT'
        elif 'BTC' in self.symbol and self.symbol != 'BTCUSDT':
            self.base_asset = self.symbol.replace('BTC', '')
            self.quote_asset = 'BTC'
        else:
            # Default fallback - may not be accurate for all pairs
            self.base_asset = self.symbol[:-4]
            self.quote_asset = self.symbol[-4:]
        
        logger.info(f"Risk manager initialized for {self.symbol}")
        logger.info(f"Base asset: {self.base_asset}, Quote asset: {self.quote_asset}")
        logger.info(f"Max investment: {self.max_investment} {self.quote_asset}")
        logger.info(f"Stop loss percentage: {self.stop_loss_percentage}%")

    def calculate_current_investment(self):
        """Calculate current investment value in quote asset (e.g., USDT)"""
        try:
            # Get balance of the quote asset (e.g., USDT)
            quote_balance = self.client.get_account_balance(self.quote_asset)
            if not quote_balance:
                logger.error(f"Failed to get {self.quote_asset} balance")
                return 0
            
            # Get balance of the base asset (e.g., ADA)
            base_balance = self.client.get_account_balance(self.base_asset)
            if not base_balance:
                logger.error(f"Failed to get {self.base_asset} balance")
                return 0
            
            # Get current price
            current_price = self.client.get_symbol_price(self.symbol)
            if not current_price:
                logger.error("Failed to get current price")
                return 0
            
            # Calculate total investment in quote asset
            quote_locked = quote_balance['locked']  # Only count locked USDT (in open buy orders)
            base_value_in_quote = (base_balance['free'] + base_balance['locked']) * current_price
            total_investment = quote_locked + base_value_in_quote
            
            return total_investment
            
        except Exception as e:
            logger.error(f"Error calculating current investment: {e}")
            return 0

    def check_investment_limit(self):
        """Check if current investment is within the maximum allowed limit"""
        try:
            # Calculate current investment
            total_investment = self.calculate_current_investment()
            
            # Check if investment is within limit
            return total_investment <= self.max_investment
        
        except Exception as e:
            logger.error(f"Error checking investment limit: {e}")
            return False

    def check_stop_loss(self, entry_price):
        """Check if current price is below stop loss threshold"""
        try:
            current_price = self.client.get_symbol_price(self.symbol)
            if not current_price:
                logger.error("Failed to get current price for stop loss check")
                return False
            
            stop_loss_price = entry_price * (1 - self.stop_loss_percentage / 100)
            
            if current_price < stop_loss_price:
                logger.warning(f"Stop loss triggered! Entry price: {entry_price}, "
                               f"Current price: {current_price}, Stop loss price: {stop_loss_price}")
                return True
            return False
        
        except Exception as e:
            logger.error(f"Error checking stop loss: {e}")
            return False

    def execute_emergency_exit(self):
        """Cancel all orders and sell all holdings in case of emergency"""
        logger.warning("Executing emergency exit strategy")
        
        try:
            # Cancel all open orders
            open_orders = self.client.get_open_orders(self.symbol)
            if open_orders:
                for order in open_orders:
                    self.client.cancel_order(order['orderId'], self.symbol)
                logger.info("Cancelled all open orders")
            
            # Sell all base asset at market price
            base_balance = self.client.get_account_balance(self.base_asset)
            if base_balance and base_balance['free'] > 0:
                # Get minimum order quantity from exchange info (not implemented)
                # For simplicity, assume we can sell the entire balance
                try:
                    result = self.client.client.create_order(
                        symbol=self.symbol,
                        side="SELL",
                        type="MARKET",
                        quantity=base_balance['free']
                    )
                    logger.info(f"Emergency sell executed: {result}")
                    return True
                except BinanceAPIException as e:
                    logger.error(f"Failed to execute emergency sell: {e}")
            
            return False
        
        except Exception as e:
            logger.error(f"Error during emergency exit: {e}")
            return False

    def monitor_market_volatility(self, time_window=3600, threshold=5.0):
        """Monitor market volatility over a specified time window (seconds)"""
        try:
            # Get historical klines (candlesticks)
            end_time = int(time.time() * 1000)  # Current time in milliseconds
            start_time = end_time - time_window * 1000  # Start time in milliseconds
            
            # Get 1-minute klines for the specified time window
            klines = self.client.client.get_klines(
                symbol=self.symbol,
                interval="1m",
                startTime=start_time,
                endTime=end_time
            )
            
            if not klines:
                logger.warning("No klines data available for volatility calculation")
                return False
            
            # Extract closing prices
            close_prices = [float(kline[4]) for kline in klines]
            
            # Calculate price range percentage
            max_price = max(close_prices)
            min_price = min(close_prices)
            price_range_percentage = ((max_price - min_price) / min_price) * 100
            
            logger.info(f"Market volatility over the last {time_window//60} minutes: {price_range_percentage:.2f}%")
            
            # Check if volatility exceeds threshold
            if price_range_percentage > threshold:
                logger.warning(f"High market volatility detected: {price_range_percentage:.2f}% (threshold: {threshold}%)")
                return True
            
            return False
        
        except Exception as e:
            logger.error(f"Error monitoring market volatility: {e}")
            return False 