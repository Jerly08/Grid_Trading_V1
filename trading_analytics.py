import os
import json
import logging
import datetime
import pandas as pd
from pathlib import Path
import matplotlib.pyplot as plt
import time

# Configure logging
logger = logging.getLogger(__name__)

class TradingAnalytics:
    """
    Class for recording and analyzing detailed trading data
    Provides enhanced logging for analysis and visualization
    """
    
    def __init__(self, symbol, log_dir="trading_logs"):
        """Initialize the trading analytics"""
        self.symbol = symbol
        self.log_dir = log_dir
        self.transactions_log_file = f"{log_dir}/transactions_{symbol}.json"
        self.price_log_file = f"{log_dir}/price_history_{symbol}.csv"
        self.balance_log_file = f"{log_dir}/balance_history.json"
        self.performance_log_file = f"{log_dir}/performance_metrics_{symbol}.json"
        
        # Ensure log directory exists
        os.makedirs(log_dir, exist_ok=True)
        
        # Store transactions
        self.transactions = []
        self.price_history = []
        self.balance_history = []
        self.performance_metrics = {
            'daily_profits': {},
            'cumulative_profit': 0,
            'win_count': 0,
            'loss_count': 0,
            'largest_profit': 0,
            'largest_loss': 0,
            'avg_profit_per_trade': 0,
            'total_volume_traded': 0,
            'roi': 0,
        }
        
        # Load existing data if available
        self._load_data()
        
        logger.info(f"Trading Analytics initialized for {symbol}")
        
    def _load_data(self):
        """Load existing analytics data if available"""
        try:
            # Load transactions
            if os.path.exists(self.transactions_log_file):
                with open(self.transactions_log_file, 'r') as f:
                    self.transactions = json.load(f)
                logger.info(f"Loaded {len(self.transactions)} existing transactions from log")
            
            # Load price history
            if os.path.exists(self.price_log_file):
                self.price_history = pd.read_csv(self.price_log_file).to_dict('records')
                logger.info(f"Loaded {len(self.price_history)} price data points from log")
            
            # Load balance history
            if os.path.exists(self.balance_log_file):
                with open(self.balance_log_file, 'r') as f:
                    self.balance_history = json.load(f)
                logger.info(f"Loaded {len(self.balance_history)} balance entries from log")
            
            # Load performance metrics
            if os.path.exists(self.performance_log_file):
                with open(self.performance_log_file, 'r') as f:
                    self.performance_metrics = json.load(f)
                logger.info(f"Loaded performance metrics from log")
                
        except Exception as e:
            logger.error(f"Error loading analytics data: {e}")
    
    def log_transaction(self, transaction_data):
        """
        Log a completed transaction with detailed data
        
        Args:
            transaction_data: Dictionary with transaction details including:
                - time: Timestamp
                - type: 'BUY' or 'SELL'
                - price: Execution price
                - quantity: Amount traded
                - profit: Profit from this transaction (should be 0 for buys)
                - total_profit: Running total profit
                - grid_level: Which grid level this trade occurred at
                - market_conditions: Additional market context
        """
        # Add timestamp if not present
        if 'timestamp' not in transaction_data:
            transaction_data['timestamp'] = datetime.datetime.now().isoformat()
            
        # Add unique transaction ID
        transaction_data['transaction_id'] = f"tx_{int(time.time() * 1000)}_{len(self.transactions)}"
        
        # Add to transactions list
        self.transactions.append(transaction_data)
        
        # Update performance metrics if it's a SELL (profit-generating) transaction
        if transaction_data.get('type') == 'SELL' and 'profit' in transaction_data:
            profit = transaction_data['profit']
            self.performance_metrics['cumulative_profit'] += profit
            
            # Update win/loss counts
            if profit > 0:
                self.performance_metrics['win_count'] += 1
                self.performance_metrics['largest_profit'] = max(self.performance_metrics['largest_profit'], profit)
            elif profit < 0:
                self.performance_metrics['loss_count'] += 1
                self.performance_metrics['largest_loss'] = min(self.performance_metrics['largest_loss'], profit)
            
            # Update daily profits
            trade_date = transaction_data.get('time', datetime.datetime.now().isoformat()).split('T')[0]
            if trade_date not in self.performance_metrics['daily_profits']:
                self.performance_metrics['daily_profits'][trade_date] = 0
            self.performance_metrics['daily_profits'][trade_date] += profit
            
            # Update average profit
            total_trades = self.performance_metrics['win_count'] + self.performance_metrics['loss_count']
            if total_trades > 0:
                self.performance_metrics['avg_profit_per_trade'] = self.performance_metrics['cumulative_profit'] / total_trades
            
            # Update total volume
            self.performance_metrics['total_volume_traded'] += transaction_data.get('quantity', 0) * transaction_data.get('price', 0)
            
        # Save updated data
        self._save_data()
        
        # Log transaction details
        details_str = ", ".join([f"{k}: {v}" for k, v in transaction_data.items() if k != 'market_conditions'])
        logger.info(f"[TRANSACTION] {details_str}")
        
        return transaction_data['transaction_id']
    
    def log_price_data(self, price_data):
        """
        Log current price data for later analysis
        
        Args:
            price_data: Dictionary with price information:
                - timestamp: Current time
                - price: Current price
                - usdt_idr: Current USDT/IDR rate
                - volume: Optional trading volume
                - bid: Optional highest bid
                - ask: Optional lowest ask
        """
        # Add timestamp if not present
        if 'timestamp' not in price_data:
            price_data['timestamp'] = datetime.datetime.now().isoformat()
            
        # Add to price history
        self.price_history.append(price_data)
        
        # Limit size to prevent memory issues (keep last 10000 data points)
        if len(self.price_history) > 10000:
            self.price_history = self.price_history[-10000:]
        
        # Save periodically (every 100 entries to avoid constant writes)
        if len(self.price_history) % 100 == 0:
            self._save_price_data()
            
        return len(self.price_history)
    
    def log_balance(self, balance_data):
        """
        Log current account balances for tracking
        
        Args:
            balance_data: Dictionary with balance information:
                - timestamp: Current time
                - base_free: Free base asset amount (e.g., ADA)
                - base_locked: Locked base asset amount
                - quote_free: Free quote asset amount (e.g., USDT)
                - quote_locked: Locked quote asset amount
                - total_value_usdt: Total portfolio value in USDT
        """
        # Add timestamp if not present
        if 'timestamp' not in balance_data:
            balance_data['timestamp'] = datetime.datetime.now().isoformat()
            
        # Add to balance history
        self.balance_history.append(balance_data)
        
        # Calculate ROI if we have initial balance
        if len(self.balance_history) > 1:
            initial_value = self.balance_history[0].get('total_value_usdt', 0)
            current_value = balance_data.get('total_value_usdt', 0)
            
            if initial_value > 0:
                roi = ((current_value - initial_value) / initial_value) * 100
                self.performance_metrics['roi'] = roi
        
        # Save balance history
        self._save_data()
        
        # Log balance summary
        logger.info(f"[BALANCE SNAPSHOT] Base free: {balance_data.get('base_free', 0):.4f}, " +
                   f"Quote free: {balance_data.get('quote_free', 0):.4f}, " +
                   f"Total USDT value: {balance_data.get('total_value_usdt', 0):.4f}")
        
        return len(self.balance_history)
    
    def get_performance_summary(self):
        """Get a summary of trading performance metrics"""
        return {
            'total_profit': self.performance_metrics['cumulative_profit'],
            'win_rate': self._calculate_win_rate(),
            'roi': self.performance_metrics['roi'],
            'avg_profit_per_trade': self.performance_metrics['avg_profit_per_trade'],
            'total_trades': self.performance_metrics['win_count'] + self.performance_metrics['loss_count'],
            'volume_traded': self.performance_metrics['total_volume_traded']
        }
    
    def _calculate_win_rate(self):
        """Calculate win rate as percentage"""
        total_trades = self.performance_metrics['win_count'] + self.performance_metrics['loss_count']
        if total_trades > 0:
            return (self.performance_metrics['win_count'] / total_trades) * 100
        return 0
        
    def _save_data(self):
        """Save all data to respective files"""
        try:
            # Save transactions
            with open(self.transactions_log_file, 'w') as f:
                json.dump(self.transactions, f, indent=2)
                
            # Save balance history
            with open(self.balance_log_file, 'w') as f:
                json.dump(self.balance_history, f, indent=2)
                
            # Save performance metrics
            with open(self.performance_log_file, 'w') as f:
                json.dump(self.performance_metrics, f, indent=2)
                
            # Save price data separately
            self._save_price_data()
                
        except Exception as e:
            logger.error(f"Error saving analytics data: {e}")
    
    def _save_price_data(self):
        """Save price data to CSV file"""
        try:
            pd.DataFrame(self.price_history).to_csv(self.price_log_file, index=False)
        except Exception as e:
            logger.error(f"Error saving price data: {e}")
    
    def generate_daily_report(self):
        """Generate a daily summary report"""
        today = datetime.datetime.now().date().isoformat()
        yesterday = (datetime.datetime.now() - datetime.timedelta(days=1)).date().isoformat()
        
        # Get today's and yesterday's profit
        today_profit = self.performance_metrics['daily_profits'].get(today, 0)
        yesterday_profit = self.performance_metrics['daily_profits'].get(yesterday, 0)
        
        # Count today's trades
        today_trades = sum(1 for t in self.transactions 
                          if t.get('time', '').startswith(today))
        
        # Get current balance if available
        current_balance = self.balance_history[-1] if self.balance_history else {}
        
        report = {
            'date': today,
            'total_profit_to_date': self.performance_metrics['cumulative_profit'],
            'today_profit': today_profit,
            'yesterday_profit': yesterday_profit,
            'today_trades': today_trades,
            'win_rate': self._calculate_win_rate(),
            'current_base_balance': current_balance.get('base_free', 0) + current_balance.get('base_locked', 0),
            'current_quote_balance': current_balance.get('quote_free', 0) + current_balance.get('quote_locked', 0),
            'roi': self.performance_metrics['roi']
        }
        
        # Log the report
        logger.info(f"[DAILY REPORT] Date: {report['date']}")
        logger.info(f"[DAILY REPORT] Today's profit: {report['today_profit']:.4f} USDT")
        logger.info(f"[DAILY REPORT] Yesterday's profit: {report['yesterday_profit']:.4f} USDT")
        logger.info(f"[DAILY REPORT] Total profit to date: {report['total_profit_to_date']:.4f} USDT")
        logger.info(f"[DAILY REPORT] Today's trades: {report['today_trades']}")
        logger.info(f"[DAILY REPORT] Overall win rate: {report['win_rate']:.2f}%")
        logger.info(f"[DAILY REPORT] Current ROI: {report['roi']:.2f}%")
        
        return report

# Create a singleton instance for global access
_instances = {}

def get_analytics(symbol):
    """Get or create an analytics instance for the given symbol"""
    if symbol not in _instances:
        _instances[symbol] = TradingAnalytics(symbol)
    return _instances[symbol] 