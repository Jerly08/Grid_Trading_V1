import time
import logging
import numpy as np
from binance.exceptions import BinanceAPIException
from binance_client import BinanceClient
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
        
        # Get current price
        current_price = self.client.get_symbol_price(self.symbol)
        if not current_price:
            logger.error("Failed to get current price. Grid setup aborted.")
            return False
        
        self.last_price = current_price
        self.price_history.append({
            "time": datetime.datetime.now().isoformat(),
            "price": current_price,
            "usdt_idr": self.client.get_usdt_idr_rate()
        })
        
        # MODIFIKASI: Selalu atur grid untuk menempatkan harga saat ini di tengah
        # Ini memastikan bahwa akan selalu ada level grid di atas dan di bawah harga saat ini
        margin_percentage = 0.02  # 2% margin di setiap sisi
        
        # Atur ulang batas untuk menempatkan harga saat ini di tengah
        self.lower_price = current_price * (1 - margin_percentage)
        self.upper_price = current_price * (1 + margin_percentage)
        
        # Pastikan lebarnya relatif konsisten 
        self.grid_size = (self.upper_price - self.lower_price) / self.grid_number
        self.grid_prices = self._calculate_grid_prices()
        
        logger.info(f"Grid adjusted to center around current price: {current_price}")
        logger.info(f"New grid range: {self.lower_price:.4f} - {self.upper_price:.4f}")
        
        # Hitung dan log level-level grid yang dibuat
        grid_levels_str = ", ".join([f"{price:.4f}" for price in self.grid_prices])
        logger.info(f"Grid levels created: {grid_levels_str}")
        
        # Count grid levels above and below current price
        grid_below_current = 0
        grid_above_current = 0
        
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
        
        # Menyesuaikan quantity jika saldo tidak mencukupi
        original_quantity = self.quantity
        adjusted = False
        
        # Periksa saldo ADA untuk sell orders
        if ada_free < required_ada and grid_above_current > 0:
            # Hitung quantity yang lebih kecil berdasarkan saldo yang tersedia (dengan 5% buffer)
            safe_ada_balance = ada_free * 0.95  # 95% dari saldo ADA yang tersedia
            new_quantity = safe_ada_balance / grid_above_current
            
            # Jika quantity baru > 0, gunakan itu
            if new_quantity > 0:
                adjusted = True
                self.quantity = new_quantity
                logger.warning(f"Insufficient {base_asset} balance. Adjusting quantity from {original_quantity} to {self.quantity:.4f}")
            else:
                logger.warning(f"Critically low {base_asset} balance. Cannot place sell orders.")
        
        # Periksa saldo USDT untuk buy orders
        if usdt_free < required_usdt and grid_below_current > 0:
            # Hitung quantity yang lebih kecil berdasarkan saldo USDT (dengan 5% buffer)
            safe_usdt_balance = usdt_free * 0.95  # 95% dari saldo USDT yang tersedia
            usdt_quantity = safe_usdt_balance / (grid_below_current * current_price)
            
            # Jika quantity baru untuk USDT lebih kecil dari quantity saat ini, gunakan itu
            if usdt_quantity > 0 and (not adjusted or usdt_quantity < self.quantity):
                self.quantity = usdt_quantity
                logger.warning(f"Insufficient {quote_asset} balance. Adjusting quantity to {self.quantity:.4f}")
        
        # Jika quantity disesuaikan, recalculate requirements
        if adjusted or self.quantity != original_quantity:
            required_usdt = grid_below_current * self.quantity * current_price
            required_ada = grid_above_current * self.quantity
            
            logger.info(f"[ADJUSTED REQUIREMENT] Need {required_usdt:.4f} {quote_asset} for {grid_below_current} buy orders")
            logger.info(f"[ADJUSTED REQUIREMENT] Need {required_ada:.4f} {base_asset} for {grid_above_current} sell orders")
        
        # Check if balance is sufficient (cek ulang setelah penyesuaian)
        if usdt_free < required_usdt:
            logger.warning(f"Still insufficient {quote_asset} balance after adjustment. Have: {usdt_free:.4f}, Need: {required_usdt:.4f}")
        
        if ada_free < required_ada:
            logger.warning(f"Still insufficient {base_asset} balance after adjustment. Have: {ada_free:.4f}, Need: {required_ada:.4f}")
        
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
        # Get current price
        current_price = self.client.get_symbol_price(self.symbol)
        if not current_price:
            logger.error("Failed to get current price")
            return
        
        # Log current balance
        self._log_current_balance()
        
        # Get USDT/IDR rate
        usdt_idr_rate = self.client.get_usdt_idr_rate()
        
        # Update price history
        now = datetime.datetime.now()
        self.price_history.append({
            "time": now.isoformat(),
            "price": current_price,
            "usdt_idr": usdt_idr_rate
        })
            
        # Limit price history to last 100 entries
        if len(self.price_history) > 100:
            self.price_history.pop(0)
        
        # Calculate price change since last check
        price_change = 0
        if self.last_price:
            price_change = ((current_price - self.last_price) / self.last_price) * 100
        
        # Calculate ADA value in IDR
        ada_idr_value = current_price * usdt_idr_rate
        
        # Log price with change percentage, total profit, and IDR value
        logger.info(f"[PRICE UPDATE] {self.symbol}: {current_price} | USDT/IDR: {usdt_idr_rate:.2f} | ADA/IDR: {ada_idr_value:.2f} | Change: {price_change:.2f}% | Profit: {self.total_profit:.4f} USDT | Time: {now.strftime('%H:%M:%S')}")
        
        # Check if price is outside grid range (with 10% buffer)
        if current_price < self.lower_price * 0.9 or current_price > self.upper_price * 1.1:
            hours_since_adjustment = (now - self.last_grid_adjustment).total_seconds() / 3600
            if hours_since_adjustment >= 1:  # Wait at least 1 hour between adjustments
                logger.warning(f"Price {current_price} is far outside grid range. Consider manual adjustment.")
        
        # Update last price
        self.last_price = current_price
        
        # Save state untuk memastikan dashboard selalu memiliki harga terbaru
        self._save_state()
        
        # Get current open orders
        open_orders = self.client.get_open_orders(self.symbol)
        if open_orders is None:
            logger.error("Failed to get open orders")
            return
        
        # Convert to dict of order_id: order
        open_order_ids = {order['orderId']: order for order in open_orders}
        
        # Check buy orders
        for price, order_id in list(self.buy_orders.items()):
            if order_id not in open_order_ids:
                # Buy order was filled, place sell order at next grid level up
                sell_price = price + self.grid_size
                logger.info(f"Buy order at {price} was filled. Placing sell order at {sell_price}")
                
                # Track potential profit
                potential_profit = (sell_price - price) * self.quantity
                logger.info(f"Potential profit if sell order fills: {potential_profit:.4f} USDT")
                
                # Record trade
                self.trades.append({
                    'time': datetime.datetime.now().isoformat(),
                    'type': 'BUY',
                    'price': price,
                    'quantity': self.quantity,
                    'symbol': self.symbol
                })
                self._save_state()
                
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
                
                # Log updated balance after order filled
                self._log_current_balance()
        
        # Check sell orders
        for price, order_id in list(self.sell_orders.items()):
            if order_id not in open_order_ids:
                # Sell order was filled, place buy order at next grid level down
                buy_price = price - self.grid_size
                logger.info(f"Sell order at {price} was filled. Placing buy order at {buy_price}")
                
                # Calculate and log actual profit from this grid level
                profit = (price - buy_price) * self.quantity
                self.total_profit += profit
                
                # Log perhitungan profit dengan lebih detail
                logger.info(f"[PROFIT DETAIL] Sell Price: {price}, Buy Price: {buy_price}, Quantity: {self.quantity}")
                logger.info(f"[PROFIT CALCULATION] ({price} - {buy_price}) * {self.quantity} = {profit:.4f} USDT")
                
                logger.info(f"Profit from this trade: {profit:.4f} USDT. Total profit: {self.total_profit:.4f} USDT")
                
                # Record trade
                self.trades.append({
                    'time': datetime.datetime.now().isoformat(),
                    'type': 'SELL',
                    'price': price,
                    'quantity': self.quantity,
                    'symbol': self.symbol,
                    'profit': profit
                })
                self._save_state()
                
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
                
                # Log updated balance after order filled
                self._log_current_balance()

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
        # Only adjust grid if significant time has passed since last adjustment
        now = datetime.datetime.now()
        hours_since_last = (now - self.last_grid_adjustment).total_seconds() / 3600
        
        if hours_since_last < 12:  # Limit adjustments to once per 12 hours
            return
            
        # Get current price
        current_price = self.client.get_symbol_price(self.symbol)
        if not current_price:
            logger.error("Failed to get current price for grid adjustment")
            return
        
        # Log current balance before adjustment
        logger.info("Checking if grid adjustment is needed...")
        self._log_current_balance()
        
        # Check jika harga di luar grid atau terlalu dekat dengan batas
        outside_range = current_price < self.lower_price or current_price > self.upper_price
        near_edge = current_price < (self.lower_price + self.grid_size) or current_price > (self.upper_price - self.grid_size)
        
        # Calculate grid width as percentage of price
        current_width_percent = ((self.upper_price - self.lower_price) / current_price) * 100
        
        # If price is outside range, near edge, or grid is too wide/narrow, adjust it
        if (outside_range or near_edge or
            current_width_percent < 3 or 
            current_width_percent > 10):
            
            logger.info(f"Adjusting grid. Current price: {current_price:.4f}, Current grid: {self.lower_price:.4f} - {self.upper_price:.4f}")
            
            # Cancel all existing orders
            open_orders = self.client.get_open_orders(self.symbol)
            if open_orders:
                for order in open_orders:
                    self.client.cancel_order(order['orderId'], self.symbol)
                logger.info("Cancelled all orders for grid adjustment")
                
            # Reset order tracking
            self.buy_orders = {}
            self.sell_orders = {}
            
            # Set new grid around current price
            margin_percentage = 0.02  # 2% margin di setiap sisi
            self.lower_price = current_price * (1 - margin_percentage)
            self.upper_price = current_price * (1 + margin_percentage)
            self.grid_size = (self.upper_price - self.lower_price) / self.grid_number
            self.grid_prices = self._calculate_grid_prices()
            
            # Log level grid yang dibuat
            grid_levels_str = ", ".join([f"{price:.4f}" for price in self.grid_prices])
            logger.info(f"Grid levels adjusted to: {grid_levels_str}")
            
            # Place new orders
            buy_orders_placed = 0
            sell_orders_placed = 0
            
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
                else:
                    order = self.client.place_limit_order(
                        symbol=self.symbol,
                        side="SELL",
                        quantity=self.quantity,
                        price=price
                    )
                    if order:
                        self.sell_orders[price] = order['orderId']
                        sell_orders_placed += 1
            
            logger.info(f"Grid adjusted. New range: {self.lower_price:.4f} - {self.upper_price:.4f}")
            logger.info(f"Grid setup complete. {buy_orders_placed} buy orders and {sell_orders_placed} sell orders placed.")
            
            self.last_grid_adjustment = now
            self._save_state()

    def recalculate_profit_from_trades(self):
        """Menghitung ulang total profit dari riwayat transaksi"""
        try:
            total_profit = 0
            trades_analyzed = 0
            sell_count = 0
            buy_count = 0
            
            logger.info("Menghitung ulang profit dari riwayat transaksi...")
            
            for trade in self.trades:
                # Hanya hitung profit dari transaksi SELL yang memiliki data profit
                if trade.get('side') == 'SELL' or trade.get('type') == 'SELL':
                    sell_count += 1
                    if 'profit' in trade and trade['profit'] > 0:
                        profit = trade['profit']
                        total_profit += profit
                        trades_analyzed += 1
                elif trade.get('side') == 'BUY' or trade.get('type') == 'BUY':
                    buy_count += 1
            
            logger.info(f"Analisis selesai: {trades_analyzed} transaksi profit ditemukan dari {sell_count} transaksi SELL dan {buy_count} transaksi BUY")
            logger.info(f"Total profit dari analisis: {total_profit:.4f} USDT (sebelumnya: {self.total_profit:.4f} USDT)")
            
            if abs(total_profit - self.total_profit) > 0.01:
                logger.warning(f"Perbedaan signifikan dalam perhitungan profit: {abs(total_profit - self.total_profit):.4f} USDT")
            
            return total_profit
            
        except Exception as e:
            logger.error(f"Error menghitung ulang profit: {e}")
            return self.total_profit
            
    def run(self):
        """Run the grid trading bot"""
        try:
            logger.info("Grid trading bot is running...")
            
            # Cek dan verifikasi nilai profit
            recalculated_profit = self.recalculate_profit_from_trades()
            if abs(recalculated_profit - self.total_profit) > 0.01:
                logger.warning(f"Perbedaan profit terdeteksi! Nilai lama: {self.total_profit:.4f}, Nilai seharusnya: {recalculated_profit:.4f}")
                logger.warning("Untuk menghindari masalah perhitungan, profit direkalkulasi. Nilai lama diabaikan.")
                self.total_profit = recalculated_profit
                self._save_state()
            
            logger.info("Price will be updated every 10 seconds")
            logger.info("Grid will be adjusted as needed (max once per 12 hours)")
            
            # Log current profit at startup
            logger.info(f"Current total profit: {self.total_profit:.4f} USDT")
            
            # Log current balance
            self._log_current_balance()
            
            self.setup_grid()
            
            while True:
                self.check_filled_orders()
                time.sleep(10)
                
        except KeyboardInterrupt:
            logger.info(f"Bot stopped by user. Final profit: {self.total_profit:.4f} USDT")
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
        finally:
            # Hapus instance referensi ketika bot berhenti
            if GridTradingBot.instance == self:
                GridTradingBot.instance = None
            logger.info(f"Grid trading bot stopped. Total profit: {self.total_profit:.4f} USDT")

if __name__ == "__main__":
    bot = GridTradingBot()
    bot.run() 
