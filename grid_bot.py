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
        try:
            logger.info("Setting up grid orders...")
            
            # Get current price
            current_price = self.client.get_symbol_price(self.symbol)
            if not current_price:
                logger.error("Failed to get current price. Grid setup aborted.")
                return False
            
            # Set initial price for overall stop loss
            self.initial_price = current_price
            
            # Get quote and base asset from symbol (e.g., BTCUSDT -> BTC, USDT)
            base_asset = self.symbol.replace('USDT', '')
            quote_asset = 'USDT'
            
            # Get available balance
            quote_balance = self.client.get_account_balance(quote_asset)
            base_balance = self.client.get_account_balance(base_asset)
            
            if not quote_balance or not base_balance:
                logger.error("Failed to get account balance. Grid setup aborted.")
                return False
            
            # Calculate investment
            total_investment = self.risk_manager.calculate_current_investment()
            logger.info(f"Current investment: {total_investment} {quote_asset}")
            
            # Check if investment would exceed limit
            if total_investment > self.risk_manager.max_investment:
                logger.warning("Investment limit would be exceeded. Adjusting grid parameters...")
            
            # Get usable balances
            usdt_free = quote_balance['free']
            ada_free = base_balance['free']
            
            # Log current balance
            logger.info(f"[BALANCE] {quote_asset}: {usdt_free:.4f} (Free) + {quote_balance['locked']:.4f} (Locked) | {base_asset}: {ada_free:.4f} (Free) + {base_balance['locked']:.4f} (Locked)")
            
            # Count how many grid levels are below and above current price
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
                
                # PERBAIKAN: Pastikan new_quantity adalah bilangan bulat untuk ADAUSDT
                if hasattr(config, 'QUANTITY_PRECISION') and config.QUANTITY_PRECISION == 0:
                    new_quantity = int(new_quantity)
                
                # Jika quantity baru > 0, gunakan itu
                if new_quantity > 0:
                    adjusted = True
                    self.quantity = new_quantity
                    logger.warning(f"Insufficient {base_asset} balance. Adjusting quantity from {original_quantity} to {self.quantity}")
                else:
                    logger.warning(f"Critically low {base_asset} balance. Cannot place sell orders.")
            
            # Periksa saldo USDT untuk buy orders
            if usdt_free < required_usdt and grid_below_current > 0:
                # Hitung quantity yang lebih kecil berdasarkan saldo USDT (dengan 5% buffer)
                safe_usdt_balance = usdt_free * 0.95  # 95% dari saldo USDT yang tersedia
                usdt_quantity = safe_usdt_balance / (grid_below_current * current_price)
                
                # PERBAIKAN: Pastikan usdt_quantity adalah bilangan bulat untuk ADAUSDT
                if hasattr(config, 'QUANTITY_PRECISION') and config.QUANTITY_PRECISION == 0:
                    usdt_quantity = int(usdt_quantity)
                
                # Jika quantity baru untuk USDT lebih kecil dari quantity saat ini, gunakan itu
                if usdt_quantity > 0 and (not adjusted or usdt_quantity < self.quantity):
                    self.quantity = usdt_quantity
                    logger.warning(f"Insufficient {quote_asset} balance. Adjusting quantity to {self.quantity}")
            
            # PERBAIKAN: Pastikan quantity sudah dalam format yang benar
            if hasattr(config, 'QUANTITY_PRECISION'):
                # Format quantity berdasarkan precision dari config
                formatted_quantity = int(self.quantity) if config.QUANTITY_PRECISION == 0 else round(self.quantity, config.QUANTITY_PRECISION)
                self.quantity = formatted_quantity
            
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
            
            # PERBAIKAN: Periksa MIN_NOTIONAL sebelum menempatkan order
            min_notional_met = True
            if hasattr(config, 'MIN_NOTIONAL'):
                min_value = self.quantity * current_price
                if min_value < config.MIN_NOTIONAL:
                    logger.warning(f"Order value ({min_value:.4f} USDT) is below MIN_NOTIONAL ({config.MIN_NOTIONAL} USDT)")
                    
                    # Sesuaikan quantity untuk memenuhi MIN_NOTIONAL
                    adjusted_quantity = int(config.MIN_NOTIONAL / current_price) + 1
                    
                    if adjusted_quantity > self.quantity:
                        logger.warning(f"Adjusting quantity from {self.quantity} to {adjusted_quantity} to meet MIN_NOTIONAL")
                        self.quantity = adjusted_quantity
                    else:
                        min_notional_met = False
                        logger.error("Cannot place orders: Unable to meet MIN_NOTIONAL requirement")
            
            # Hanya lanjutkan jika MIN_NOTIONAL terpenuhi
            if not min_notional_met:
                logger.error("Grid setup aborted due to MIN_NOTIONAL constraint")
                return False
            
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
            
        except Exception as e:
            logger.error(f"Error setting up grid: {e}")
            return False

    def check_filled_orders(self):
        """Check if any grid orders have been filled"""
        try:
            # Get all open orders
            open_orders = self.client.get_open_orders(self.symbol)
            open_order_ids = [order['orderId'] for order in open_orders]
            
            # Update latest price
            current_price = self.client.get_symbol_price(self.symbol)
            if current_price and (not self.last_price or abs(current_price - self.last_price) > 0.0001):
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
                    
                    # Log the filled buy order - tanpa menambahkan profit pada BUY order
                    logger.info(f"Buy order at {price} filled. Setting up sell order at {sell_price}")
                    
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
                            'potential_profit': 0  # Profit potensial, belum direalisasikan
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
                    
                    # Hitung profit dengan formula yang benar: selisih antara harga jual dan beli
                    # Asumsi buy_price adalah harga pembelian sebelumnya untuk posisi ini
                    profit = (price - buy_price) * self.quantity
                    self.total_profit += profit
                    profit_percentage = (profit / (buy_price * self.quantity)) * 100
                    
                    # Log perhitungan profit dengan lebih detail
                    logger.info(f"[PROFIT DETAIL] Sell Price: {price}, Buy Price: {buy_price}, Quantity: {self.quantity}")
                    logger.info(f"[PROFIT CALCULATION] ({price} - {buy_price}) * {self.quantity} = {profit:.4f} USDT")
                    
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
            
            # Check if price is outside grid range or terlalu dekat dengan batas
            outside_range = current_price < self.lower_price or current_price > self.upper_price
            near_edge = current_price < (self.lower_price + self.grid_size) or current_price > (self.upper_price - self.grid_size)
            
            if outside_range or near_edge:
                logger.info(f"Price ({current_price}) is outside grid range or near edge. Adjusting grid...")
                
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
                
                # Set new grid around current price with 2% di kedua sisi
                margin_percentage = 0.02
                self.lower_price = current_price * (1 - margin_percentage)
                self.upper_price = current_price * (1 + margin_percentage)
                self.grid_size = (self.upper_price - self.lower_price) / self.grid_number
                self.grid_prices = self._calculate_grid_prices()
                
                # Hitung dan log level-level grid yang dibuat
                grid_levels_str = ", ".join([f"{price:.4f}" for price in self.grid_prices])
                logger.info(f"Grid levels adjusted to: {grid_levels_str}")
                
                logger.info(f"New grid range: {self.lower_price:.4f} - {self.upper_price:.4f}")
                
                # Set up new grid
                self.setup_grid()
                
                # Update last grid adjustment time
                self.last_grid_adjustment = datetime.datetime.now()
                
            # Log current grid status
            logger.info(f"Current grid status: {len(self.buy_orders)} buy orders, {len(self.sell_orders)} sell orders")
            logger.info(f"Grid range: {self.lower_price:.4f} - {self.upper_price:.4f}, Current price: {current_price:.4f}")
        
        except Exception as e:
            logger.error(f"Error adjusting grid: {e}")

    def run(self):
        """Run the grid trading bot"""
        logger.info("Starting grid trading bot...")
        
        # Cek dan verifikasi nilai profit
        recalculated_profit = self.recalculate_profit_from_trades()
        if abs(recalculated_profit - self.total_profit) > 0.01:
            logger.warning(f"Perbedaan profit terdeteksi! Nilai lama: {self.total_profit:.4f}, Nilai seharusnya: {recalculated_profit:.4f}")
            logger.warning("Untuk menghindari masalah perhitungan, profit direkalkulasi. Nilai lama diabaikan.")
            self.total_profit = recalculated_profit
            self._save_state()
        
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
                    if 'actual_profit' in trade:
                        profit = trade['actual_profit']
                        total_profit += profit
                        trades_analyzed += 1
                    elif 'profit' in trade and trade['profit'] > 0:
                        profit = trade['profit']
                        total_profit += profit
                        trades_analyzed += 1
                elif trade.get('side') == 'BUY' or trade.get('type') == 'BUY':
                    buy_count += 1
            
            logger.info(f"Analisis selesai: {trades_analyzed} transaksi profit ditemukan dari {sell_count} transaksi SELL dan {buy_count} transaksi BUY")
            logger.info(f"Total profit dari analisis: {total_profit:.4f} USDT (sebelumnya: {self.total_profit:.4f} USDT)")
            
            if abs(total_profit - self.total_profit) > 0.01:
                logger.warning(f"Perbedaan signifikan dalam perhitungan profit: {abs(total_profit - self.total_profit):.4f} USDT")
                
                # Tanyakan apakah ingin perbarui nilai total profit
                logger.info("Untuk memperbarui nilai total profit, set self.total_profit = recalculate_profit_from_trades() dalam kode")
            
            return total_profit
            
        except Exception as e:
            logger.error(f"Error menghitung ulang profit: {e}")
            return self.total_profit

if __name__ == "__main__":
    bot = GridTradingBot()
    bot.run() 