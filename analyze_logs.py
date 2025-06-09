import os
import json
import pandas as pd
import matplotlib.pyplot as plt
import datetime
import argparse
from pathlib import Path
import numpy as np

def load_transaction_data(symbol="ADAUSDT"):
    """Load transaction data from log files"""
    transactions_file = f"trading_logs/transactions_{symbol}.json"
    
    if not os.path.exists(transactions_file):
        print(f"Transactions file {transactions_file} not found!")
        return None
    
    with open(transactions_file, 'r') as f:
        transactions = json.load(f)
    
    print(f"Loaded {len(transactions)} transactions for {symbol}")
    return transactions

def load_price_data(symbol="ADAUSDT"):
    """Load price history data from log files"""
    price_file = f"trading_logs/price_history_{symbol}.csv"
    
    if not os.path.exists(price_file):
        print(f"Price history file {price_file} not found!")
        return None
    
    price_data = pd.read_csv(price_file)
    print(f"Loaded {len(price_data)} price data points for {symbol}")
    return price_data

def load_performance_metrics(symbol="ADAUSDT"):
    """Load performance metrics from log files"""
    metrics_file = f"trading_logs/performance_metrics_{symbol}.json"
    
    if not os.path.exists(metrics_file):
        print(f"Performance metrics file {metrics_file} not found!")
        return None
    
    with open(metrics_file, 'r') as f:
        metrics = json.load(f)
    
    return metrics

def load_balance_history():
    """Load balance history data from log files"""
    balance_file = "trading_logs/balance_history.json"
    
    if not os.path.exists(balance_file):
        print(f"Balance history file {balance_file} not found!")
        return None
    
    with open(balance_file, 'r') as f:
        balance_history = json.load(f)
    
    print(f"Loaded {len(balance_history)} balance data points")
    return balance_history

def analyze_transactions(transactions):
    """Analyze transaction data to generate insights"""
    if not transactions:
        return
    
    # Convert to DataFrame for easier analysis
    df = pd.DataFrame(transactions)
    
    # Convert time strings to datetime
    if 'time' in df.columns:
        df['time'] = pd.to_datetime(df['time'])
    elif 'timestamp' in df.columns:
        df['time'] = pd.to_datetime(df['timestamp'])
        
    # Group by type to analyze buy and sell operations
    by_type = df.groupby('type')
    
    print("\n=== TRANSACTION ANALYSIS ===")
    
    # Print transaction counts
    type_counts = by_type.size()
    print(f"Total transactions: {len(df)}")
    print(f"Transaction types: {dict(type_counts)}")
    
    # Analyze profit information for SELL transactions
    if 'SELL' in type_counts and 'profit' in df.columns:
        sell_df = df[df['type'] == 'SELL']
        total_profit = sell_df['profit'].sum()
        avg_profit = sell_df['profit'].mean()
        max_profit = sell_df['profit'].max()
        
        print(f"Total profit from SELL transactions: {total_profit:.4f} USDT")
        print(f"Average profit per SELL transaction: {avg_profit:.4f} USDT")
        print(f"Maximum profit in a single transaction: {max_profit:.4f} USDT")
        
        # Calculate win rate
        profitable_trades = len(sell_df[sell_df['profit'] > 0])
        losing_trades = len(sell_df[sell_df['profit'] <= 0])
        win_rate = profitable_trades / (profitable_trades + losing_trades) * 100 if (profitable_trades + losing_trades) > 0 else 0
        print(f"Win rate: {win_rate:.2f}% ({profitable_trades} profitable, {losing_trades} losing)")
        
    # Analyze time patterns
    print("\n=== TIME PATTERN ANALYSIS ===")
    if 'time' in df.columns:
        df['hour'] = df['time'].dt.hour
        hourly_counts = df.groupby('hour').size()
        
        print("Transactions by hour of day:")
        for hour, count in hourly_counts.items():
            print(f"  Hour {hour}: {count} transactions")
        
        # Find most active hour
        most_active_hour = hourly_counts.idxmax()
        print(f"Most active hour: {most_active_hour} with {hourly_counts[most_active_hour]} transactions")
    
    # Analyze grid levels if available
    if 'grid_level' in df.columns:
        print("\n=== GRID LEVEL ANALYSIS ===")
        grid_level_counts = df.groupby(['type', 'grid_level']).size()
        
        # Find most profitable grid levels
        if 'SELL' in type_counts and 'profit' in df.columns:
            sell_df = df[df['type'] == 'SELL']
            grid_profits = sell_df.groupby('grid_level')['profit'].sum()
            
            print("Profit by grid level:")
            for level, profit in grid_profits.items():
                if level != -1:  # Skip unknown grid levels
                    print(f"  Level {level}: {profit:.4f} USDT")
            
            # Find most profitable grid level
            if not grid_profits.empty and -1 not in grid_profits:
                most_profitable_level = grid_profits.idxmax()
                print(f"Most profitable grid level: {most_profitable_level} with {grid_profits[most_profitable_level]:.4f} USDT")
    
    return df

def analyze_price_data(price_data):
    """Analyze price history data to generate insights"""
    if not price_data or price_data.empty:
        return
    
    print("\n=== PRICE ANALYSIS ===")
    
    # Convert time strings to datetime
    if 'timestamp' in price_data.columns:
        price_data['timestamp'] = pd.to_datetime(price_data['timestamp'])
    elif 'time' in price_data.columns:
        price_data['timestamp'] = pd.to_datetime(price_data['time'])
    
    # Basic statistics
    if 'price' in price_data.columns:
        min_price = price_data['price'].min()
        max_price = price_data['price'].max()
        avg_price = price_data['price'].mean()
        std_dev = price_data['price'].std()
        
        print(f"Price range: {min_price:.4f} - {max_price:.4f} USDT")
        print(f"Average price: {avg_price:.4f} USDT")
        print(f"Price standard deviation: {std_dev:.4f} USDT")
        print(f"Volatility (StdDev/Avg): {(std_dev/avg_price)*100:.2f}%")
    
    # USDT/IDR rate analysis
    if 'usdt_idr' in price_data.columns:
        min_rate = price_data['usdt_idr'].min()
        max_rate = price_data['usdt_idr'].max()
        avg_rate = price_data['usdt_idr'].mean()
        
        print(f"USDT/IDR rate range: {min_rate:.2f} - {max_rate:.2f} IDR")
        print(f"Average USDT/IDR rate: {avg_rate:.2f} IDR")
    
    return price_data

def analyze_balance_history(balance_data):
    """Analyze balance history data to generate insights"""
    if not balance_data:
        return
    
    print("\n=== BALANCE HISTORY ANALYSIS ===")
    
    # Convert to DataFrame
    df = pd.DataFrame(balance_data)
    
    # Convert time strings to datetime
    if 'timestamp' in df.columns:
        df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    if len(df) >= 2:
        # Get first and last records
        first_balance = df.iloc[0]
        last_balance = df.iloc[-1]
        
        # Calculate changes in balances
        if 'total_value_usdt' in df.columns:
            initial_value = first_balance.get('total_value_usdt', 0)
            final_value = last_balance.get('total_value_usdt', 0)
            value_change = final_value - initial_value
            percent_change = (value_change / initial_value) * 100 if initial_value > 0 else 0
            
            print(f"Initial portfolio value: {initial_value:.4f} USDT")
            print(f"Current portfolio value: {final_value:.4f} USDT")
            print(f"Change: {value_change:.4f} USDT ({percent_change:.2f}%)")
        
        # Check base and quote asset changes
        if 'base_free' in df.columns and 'base_locked' in df.columns:
            initial_base = first_balance.get('base_free', 0) + first_balance.get('base_locked', 0)
            final_base = last_balance.get('base_free', 0) + last_balance.get('base_locked', 0)
            base_change = final_base - initial_base
            
            print(f"Base asset change: {base_change:.4f}")
        
        if 'quote_free' in df.columns and 'quote_locked' in df.columns:
            initial_quote = first_balance.get('quote_free', 0) + first_balance.get('quote_locked', 0)
            final_quote = last_balance.get('quote_free', 0) + last_balance.get('quote_locked', 0)
            quote_change = final_quote - initial_quote
            
            print(f"Quote asset change: {quote_change:.4f}")
    
    return df

def analyze_performance_metrics(metrics):
    """Analyze performance metrics to generate insights"""
    if not metrics:
        return
    
    print("\n=== PERFORMANCE METRICS ANALYSIS ===")
    
    # Cumulative profit
    cum_profit = metrics.get('cumulative_profit', 0)
    print(f"Cumulative profit: {cum_profit:.4f} USDT")
    
    # Win/loss metrics
    win_count = metrics.get('win_count', 0)
    loss_count = metrics.get('loss_count', 0)
    win_rate = win_count / (win_count + loss_count) * 100 if (win_count + loss_count) > 0 else 0
    print(f"Win rate: {win_rate:.2f}% ({win_count} wins, {loss_count} losses)")
    
    # Profit metrics
    avg_profit = metrics.get('avg_profit_per_trade', 0)
    largest_profit = metrics.get('largest_profit', 0)
    largest_loss = metrics.get('largest_loss', 0)
    print(f"Average profit per trade: {avg_profit:.4f} USDT")
    print(f"Largest profit: {largest_profit:.4f} USDT")
    print(f"Largest loss: {largest_loss:.4f} USDT")
    
    # ROI
    roi = metrics.get('roi', 0)
    print(f"Return on Investment (ROI): {roi:.2f}%")
    
    # Daily profits analysis
    daily_profits = metrics.get('daily_profits', {})
    if daily_profits:
        print("\n== Daily Profits ==")
        
        # Convert to DataFrame
        daily_df = pd.DataFrame([
            {'date': date, 'profit': profit} 
            for date, profit in daily_profits.items()
        ])
        
        if not daily_df.empty:
            daily_df['date'] = pd.to_datetime(daily_df['date'])
            daily_df = daily_df.sort_values('date')
            
            # Calculate statistics
            total_days = len(daily_df)
            profitable_days = len(daily_df[daily_df['profit'] > 0])
            losing_days = len(daily_df[daily_df['profit'] < 0])
            zero_days = len(daily_df[daily_df['profit'] == 0])
            
            print(f"Trading days: {total_days}")
            print(f"Profitable days: {profitable_days} ({profitable_days/total_days*100:.2f}%)")
            print(f"Losing days: {losing_days} ({losing_days/total_days*100:.2f}%)")
            print(f"Zero profit days: {zero_days}")
            
            if not daily_df.empty:
                best_day = daily_df.loc[daily_df['profit'].idxmax()]
                worst_day = daily_df.loc[daily_df['profit'].idxmin()]
                
                print(f"Best day: {best_day['date'].strftime('%Y-%m-%d')} with {best_day['profit']:.4f} USDT")
                print(f"Worst day: {worst_day['date'].strftime('%Y-%m-%d')} with {worst_day['profit']:.4f} USDT")
    
    return metrics

def plot_data(transactions_df=None, price_df=None, balance_df=None, output_dir='analysis_charts'):
    """Generate plots from the analyzed data"""
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Set plot style
    plt.style.use('seaborn-v0_8-darkgrid')
    
    # Plot transaction data
    if transactions_df is not None and not transactions_df.empty and 'time' in transactions_df.columns:
        print("\nGenerating transaction charts...")
        
        # Plot transaction counts by day
        plt.figure(figsize=(12, 6))
        transactions_df['date'] = transactions_df['time'].dt.date
        daily_counts = transactions_df.groupby(['date', 'type']).size().unstack(fill_value=0)
        daily_counts.plot(kind='bar', stacked=True)
        plt.title('Daily Transaction Counts')
        plt.xlabel('Date')
        plt.ylabel('Number of Transactions')
        plt.tight_layout()
        plt.savefig(f"{output_dir}/daily_transactions.png")
        
        # Plot profits over time if available
        if 'profit' in transactions_df.columns:
            sell_df = transactions_df[transactions_df['type'] == 'SELL'].copy()
            if not sell_df.empty:
                plt.figure(figsize=(12, 6))
                sell_df['cumulative_profit'] = sell_df['profit'].cumsum()
                sell_df.plot(x='time', y='cumulative_profit', figsize=(12, 6))
                plt.title('Cumulative Profit Over Time')
                plt.xlabel('Date')
                plt.ylabel('Profit (USDT)')
                plt.grid(True)
                plt.tight_layout()
                plt.savefig(f"{output_dir}/cumulative_profit.png")
    
    # Plot price data
    if price_df is not None and not price_df.empty:
        print("Generating price charts...")
        
        # Ensure we have timestamp column
        time_column = 'timestamp' if 'timestamp' in price_df.columns else 'time'
        
        if time_column in price_df.columns and 'price' in price_df.columns:
            # Plot price over time
            plt.figure(figsize=(12, 6))
            price_df.plot(x=time_column, y='price', figsize=(12, 6))
            plt.title('Price Over Time')
            plt.xlabel('Date')
            plt.ylabel('Price (USDT)')
            plt.grid(True)
            plt.tight_layout()
            plt.savefig(f"{output_dir}/price_history.png")
            
            # If we have USDT/IDR rates, plot them too
            if 'usdt_idr' in price_df.columns:
                plt.figure(figsize=(12, 6))
                price_df.plot(x=time_column, y='usdt_idr', figsize=(12, 6))
                plt.title('USDT/IDR Rate Over Time')
                plt.xlabel('Date')
                plt.ylabel('Rate (IDR)')
                plt.grid(True)
                plt.tight_layout()
                plt.savefig(f"{output_dir}/usdt_idr_rate.png")
    
    # Plot balance data
    if balance_df is not None and not balance_df.empty:
        print("Generating balance charts...")
        
        if 'timestamp' in balance_df.columns and 'total_value_usdt' in balance_df.columns:
            plt.figure(figsize=(12, 6))
            balance_df.plot(x='timestamp', y='total_value_usdt', figsize=(12, 6))
            plt.title('Portfolio Value Over Time')
            plt.xlabel('Date')
            plt.ylabel('Value (USDT)')
            plt.grid(True)
            plt.tight_layout()
            plt.savefig(f"{output_dir}/portfolio_value.png")
            
            # Plot base and quote asset balance
            if all(col in balance_df.columns for col in ['base_free', 'base_locked', 'quote_free', 'quote_locked']):
                plt.figure(figsize=(12, 6))
                balance_df['total_base'] = balance_df['base_free'] + balance_df['base_locked']
                balance_df['total_quote'] = balance_df['quote_free'] + balance_df['quote_locked']
                balance_df.plot(x='timestamp', y=['total_base', 'total_quote'], figsize=(12, 6))
                plt.title('Asset Balances Over Time')
                plt.xlabel('Date')
                plt.ylabel('Amount')
                plt.grid(True)
                plt.tight_layout()
                plt.savefig(f"{output_dir}/asset_balances.png")
    
    print(f"Charts saved to {output_dir}/ directory")

def main():
    """Main function to run the analysis"""
    parser = argparse.ArgumentParser(description='Analyze trading bot logs')
    parser.add_argument('--symbol', default='ADAUSDT', help='Trading symbol to analyze (default: ADAUSDT)')
    parser.add_argument('--no-plots', action='store_true', help='Skip generating plots')
    args = parser.parse_args()
    
    symbol = args.symbol
    
    # Check if trading_logs directory exists
    if not os.path.exists('trading_logs'):
        print("Error: trading_logs directory not found! Make sure the bot has run and generated logs.")
        return
    
    # Print script header
    print("=" * 50)
    print(f"TRADING ANALYTICS REPORT FOR {symbol}")
    print(f"Generated at {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)
    
    # Load and analyze all data
    transactions = load_transaction_data(symbol)
    price_data = load_price_data(symbol)
    balance_data = load_balance_history()
    metrics = load_performance_metrics(symbol)
    
    # Run analysis
    transactions_df = analyze_transactions(transactions)
    price_df = analyze_price_data(price_data)
    balance_df = analyze_balance_history(balance_data)
    analyze_performance_metrics(metrics)
    
    # Generate plots if not disabled
    if not args.no_plots:
        plot_data(transactions_df, price_df, balance_df)
    
    print("\nAnalysis complete!")

if __name__ == "__main__":
    main() 