from flask import Flask, render_template, jsonify, request, redirect, url_for, session, Response
import os
import json
import datetime
import plotly
import plotly.graph_objs as go
import numpy as np
import pandas as pd
from threading import Thread, Lock
import time
import logging
import hashlib
import uuid
import secrets
from functools import wraps
import config
import random
import psutil
import re

# Konfigurasi security
DASHBOARD_USERNAME = os.getenv('DASHBOARD_USERNAME', 'admin')
DASHBOARD_PASSWORD = os.getenv('DASHBOARD_PASSWORD', 'Grid@Trading123')  # Default password
DASHBOARD_SECRET_KEY = os.getenv('DASHBOARD_SECRET_KEY', secrets.token_hex(32))

app = Flask(__name__)
app.secret_key = DASHBOARD_SECRET_KEY
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SECURE'] = False  # Nonaktifkan karena menggunakan HTTP, bukan HTTPS
app.config['PERMANENT_SESSION_LIFETIME'] = datetime.timedelta(hours=8)
app.config['JSON_AS_ASCII'] = False  # Allow non-ASCII characters in JSON response

# Konfigurasi logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Data global untuk dashboard
bot_status = "Tidak Aktif"
latest_price = None
price_history = []
bot_profit = 0
trades_history = []
grid_levels = []
usdt_idr_rate = None  # Nilai tukar USDT/IDR
balance_info = {       # Informasi saldo
    "usdt_free": 0,
    "usdt_locked": 0,
    "ada_free": 0,
    "ada_locked": 0,
    "last_update": None
}

# Tambahkan fallback price jika tidak ada data
FALLBACK_PRICE = 0.7800  # Harga ADA fallback jika tidak bisa mendapatkan data terkini

# Session tracking untuk keamanan
active_sessions = {}
MAX_FAILED_ATTEMPTS = 5
blocked_ips = {}

# Lock untuk thread safety
data_lock = Lock()

# Cek jika SSE dinonaktifkan
SSE_DISABLED = os.getenv('DISABLE_SSE', 'false').lower() == 'true'

# SSE clients
sse_clients = [] if not SSE_DISABLED else None  # Gunakan None jika SSE dinonaktifkan

# Helper function for emoji handling
def safe_emoji(text):
    """Replace emoji characters with their text representation if emoji support is disabled"""
    if hasattr(config, 'EMOJI_SUPPORT') and not config.EMOJI_SUPPORT:
        # Replace common emojis with text
        emoji_map = {
            '📈': '[UP]',
            '📉': '[DOWN]',
            '💰': '[PROFIT]',
            '⚠️': '[WARNING]',
            '✅': '[SUCCESS]',
            '❌': '[FAIL]',
            '🔄': '[SYNC]',
            '⏱️': '[TIME]'
        }
        for emoji, replacement in emoji_map.items():
            if emoji in text:
                text = text.replace(emoji, replacement)
    return text

def hash_password(password):
    """Hash password dengan salt"""
    salt = uuid.uuid4().hex
    return hashlib.sha256(salt.encode() + password.encode()).hexdigest() + ':' + salt

def check_password(hashed_password, user_password):
    """Verifikasi password"""
    password, salt = hashed_password.split(':')
    return password == hashlib.sha256(salt.encode() + user_password.encode()).hexdigest()

def login_required(f):
    """Decorator untuk halaman yang memerlukan login (dinonaktifkan)"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Bypass authentication - langsung berikan akses
        return f(*args, **kwargs)
    return decorated_function

def check_for_session_timeout():
    """Fungsi ini tidak lagi diperlukan karena autentikasi dihapus, tapi tetap ada untuk kompatibilitas."""
    while True:
        time.sleep(300)  # Tidur saja, tidak perlu melakukan apa-apa

@app.route('/login', methods=['GET', 'POST'])
def login():
    # Bypass login, langsung redirect ke index
    return redirect(url_for('index'))

@app.route('/logout')
def logout():
    # Tetap ada untuk kompatibilitas, tapi tidak melakukan apa-apa
    return redirect(url_for('index'))

@app.route('/')
# @login_required (tidak perlu lagi)
def index():
    """Halaman utama dashboard"""
    return render_template('index.html', 
                           bot_status=bot_status,
                           latest_price=latest_price,
                           bot_profit=bot_profit)

@app.route('/api/price_chart')
# @login_required (dinonaktifkan)
def price_chart():
    """API endpoint untuk data grafik harga"""
    global price_history, latest_price, grid_levels
    
    # Refresh data to ensure we have the latest
    load_bot_data()
    
    # Jika tidak ada data price history, buat data dummy
    if not price_history and latest_price is not None:
        # Create dummy data point based on latest price
        now = datetime.datetime.now()
        five_min_ago = now - datetime.timedelta(minutes=5)
        price_history = [
            {"time": five_min_ago.strftime("%Y-%m-%d %H:%M:%S"), "price": latest_price},
            {"time": now.strftime("%Y-%m-%d %H:%M:%S"), "price": latest_price}
        ]
    
    if price_history:
        # Limited to last 100 data points to improve performance
        timestamps = [entry['time'] for entry in price_history[-100:]]
        prices = [entry['price'] for entry in price_history[-100:]]
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=timestamps, y=prices, mode='lines', name='Harga ADA'))
        
        # Tambahkan garis grid
        if grid_levels and len(grid_levels) >= 2:
            for level in grid_levels:
                fig.add_shape(
                    type="line",
                    x0=timestamps[0] if timestamps else 0,
                    y0=level,
                    x1=timestamps[-1] if timestamps else 1,
                    y1=level,
                    line=dict(color="Red", width=1, dash="dash"),
                )
        
        fig.update_layout(
            title='Pergerakan Harga ADA/USDT',
            xaxis_title='Waktu',
            yaxis_title='Harga (USDT)',
            template='plotly_dark',
            autosize=True,
            height=500,
            margin=dict(l=50, r=50, t=50, b=50),
        )
        
        chart_json = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
        return jsonify({"status": "success", "chart": chart_json})
    else:
        # Return empty chart if no data
        fig = go.Figure()
        fig.update_layout(
            title='Tidak Ada Data Harga',
            xaxis_title='Waktu',
            yaxis_title='Harga (USDT)',
            template='plotly_dark',
            autosize=True,
            height=500,
            annotations=[dict(
                text="Belum ada data harga tersedia",
                xref="paper",
                yref="paper",
                x=0.5,
                y=0.5,
                showarrow=False,
                font=dict(size=20)
            )],
        )
        chart_json = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
        return jsonify({"status": "no_data", "chart": chart_json})

@app.route('/api/trades')
# @login_required (dinonaktifkan)
def get_trades():
    """API endpoint untuk data history trading"""
    try:
        trades_data = []
        
        # Coba dapatkan dari instance bot aktif
        try:
            from grid_bot import GridTradingBot
            if hasattr(GridTradingBot, 'instance') and GridTradingBot.instance is not None:
                bot = GridTradingBot.instance
                if hasattr(bot, 'trades'):
                    trades_data = bot.trades
        except Exception as e:
            logger.error(f"Error getting trades from bot instance: {e}")
        
        # Jika tidak dapat dari instance bot, coba load dari file state
        if not trades_data:
            state_files = [f for f in os.listdir(".") if f.startswith("grid_state_") and f.endswith(".json")]
            if state_files:
                latest_state_file = state_files[0]
                try:
                    with open(latest_state_file, "r") as f:
                        state = json.load(f)
                        trades_data = state.get("trades", [])
                        logger.info(f"Loaded {len(trades_data)} trades from state file {latest_state_file}")
                except Exception as e:
                    logger.error(f"Error reading trades from state file: {e}")
        
        # Jika masih belum ada data, coba parse dari log
        if not trades_data:
            try:
                trades_data = parse_trades_from_log()
            except Exception as e:
                logger.error(f"Error parsing trades from log: {e}")
        
        # Normalisasi format data perdagangan
        for trade in trades_data:
            # Pastikan semua trade memiliki field 'side' untuk dashboard baru
            if 'side' not in trade and 'type' in trade:
                trade['side'] = trade['type']
            elif 'side' not in trade:
                # Default side jika tidak ada
                trade['side'] = 'BUY'
            
            # Pastikan format nilai konsisten
            if 'price' in trade and trade['price'] is not None:
                trade['price'] = float(trade['price'])
            
            if 'quantity' in trade and trade['quantity'] is not None:
                trade['quantity'] = float(trade['quantity'])
            
            # Hitung nilai total jika belum ada
            if 'value' not in trade and 'price' in trade and 'quantity' in trade:
                trade['value'] = trade['price'] * trade['quantity']
            
            # --- PROFIT HANDLING ---
            # Pastikan informasi fee tersedia
            if 'fee' not in trade:
                # Estimasi fee sebagai 0.1% dari nilai transaksi (default Binance)
                if 'value' in trade:
                    trade['fee'] = round(trade['value'] * 0.001, 4)
                else:
                    trade['fee'] = 0.0
            
            # Pastikan informasi gross_profit tersedia (profit sebelum fee)
            if 'gross_profit' not in trade and 'side' in trade and trade['side'] == 'SELL':
                if 'actual_profit' in trade and 'fee' in trade:
                    # Hitung mundur dari profit bersih jika sudah ada
                    trade['gross_profit'] = trade['actual_profit'] + trade['fee']
                elif 'profit' in trade:
                    # Gunakan nilai profit yang ada sebagai gross_profit (untuk kompatibilitas dengan data lama)
                    # dan hitung profit bersih
                    trade['gross_profit'] = trade['profit']
                    trade['net_profit'] = trade['profit'] - trade['fee']
                    
                    # Update nilai profit untuk menunjukkan nilai bersih
                    trade['profit'] = trade['net_profit']
            
            # Pastikan keseragaman nama field untuk profit bersih
            if 'net_profit' not in trade and 'actual_profit' in trade:
                trade['net_profit'] = trade['actual_profit']
            elif 'net_profit' not in trade and 'profit' in trade and trade['side'] == 'SELL':
                # Untuk data lama yang tidak memperhitungkan fee
                trade['net_profit'] = trade['profit'] - trade['fee']
            
            # Untuk BUY order, profit selalu 0
            if trade['side'] == 'BUY':
                trade['profit'] = 0
                trade['net_profit'] = 0
                trade['gross_profit'] = 0
            
        return jsonify({"status": "success", "trades": trades_data})
    except Exception as e:
        logger.error(f"Error in trades API: {e}")
        return jsonify({"status": "error", "trades": [], "message": str(e)})

def parse_trades_from_log():
    """Parse riwayat transaksi dari file log"""
    trades = []
    try:
        with open("bot.log", "r", encoding="utf-8") as log_file:
            lines = log_file.readlines()
            
            for line in lines:
                # Cari baris log yang berisi informasi transaksi
                if "TRADE FILLED" in line or "Order filled" in line or "Buy order at" in line or "Sell order at" in line:
                    try:
                        # Contoh format: "BUY order filled at 0.7850"
                        parts = line.split(" - ")
                        if len(parts) >= 2:
                            timestamp = parts[0].strip()
                            message = parts[1]
                            
                            # Ekstrak informasi
                            if "BUY" in message or "Buy order at" in message:
                                type_order = "BUY"
                            elif "SELL" in message or "Sell order at" in message:
                                type_order = "SELL"
                            else:
                                continue
                            
                            # Coba ekstrak harga
                            price_match = re.search(r'at\s+(\d+\.\d+)', message)
                            if not price_match:
                                price_match = re.search(r'order at (\d+\.\d+)', message)
                            
                            if price_match:
                                price = float(price_match.group(1))
                            else:
                                continue
                            
                            # Parse quantity (jumlah)
                            # Contoh: "Order filled: BUY 13.0 ADA at 0.7850"
                            qty_match = re.search(r'(\d+\.?\d*)\s+ADA', message)
                            quantity = float(qty_match.group(1)) if qty_match else config.QUANTITY
                            
                            # Coba ekstrak profit jika ada
                            profit_match = re.search(r'Profit:\s+(\-?\d+\.?\d*)', message)
                            if not profit_match:
                                profit_match = re.search(r'profit:\s+(\-?\d+\.?\d*)', message)
                            
                            profit = float(profit_match.group(1)) if profit_match else 0.0
                            
                            # Nilai transaksi
                            value = price * quantity
                            
                            trade = {
                                "time": timestamp,
                                "side": type_order,
                                "type": type_order,  # Untuk kompatibilitas dengan format lama
                                "price": price,
                                "quantity": quantity,
                                "value": value,
                                "profit": profit
                            }
                            trades.append(trade)
                    except Exception as e:
                        logger.debug(f"Failed to parse trade from log line: {e}")
    
    except Exception as e:
        logger.error(f"Error reading log file for trades: {e}")
    
    return trades

@app.route('/api/status')
# @login_required (dinonaktifkan)
def get_status():
    """API endpoint untuk status bot"""
    global latest_price, usdt_idr_rate, balance_info, grid_levels, bot_profit, bot_status, price_history
    
    # Reload data untuk mendapatkan harga terbaru
    load_bot_data()
    
    # Pastikan selalu ada nilai harga, gunakan fallback jika perlu
    if latest_price is None:
        latest_price = FALLBACK_PRICE
        logger.warning(f"Using fallback price: {FALLBACK_PRICE}")
    
    # Pastikan selalu ada nilai USDT/IDR
    if usdt_idr_rate is None:
        usdt_idr_rate = 16350.0
    
    # Hitung nilai ADA dalam IDR
    ada_idr_value = latest_price * usdt_idr_rate
    
    # Hitung total nilai aset dalam USDT dan IDR
    total_ada = balance_info["ada_free"] + balance_info["ada_locked"]
    total_usdt = balance_info["usdt_free"] + balance_info["usdt_locked"]
    total_usdt_value = total_usdt + (total_ada * latest_price)
    total_idr_value = total_usdt_value * usdt_idr_rate
    
    # Dapatkan data grid
    grid_info = {
        "upper_price": None,
        "lower_price": None,
        "grid_number": config.GRID_NUMBER,
        "quantity": config.QUANTITY
    }
    
    # Coba dapatkan data grid dari instance bot
    try:
        from grid_bot import GridTradingBot
        if GridTradingBot.instance:
            grid_info["upper_price"] = GridTradingBot.instance.upper_price
            grid_info["lower_price"] = GridTradingBot.instance.lower_price
            grid_info["grid_number"] = GridTradingBot.instance.grid_number
            grid_info["quantity"] = GridTradingBot.instance.quantity
    except Exception as e:
        logger.warning(f"Failed to get grid info from bot instance: {e}")
    
    # Jika data grid masih kosong, ambil dari konfigurasi
    if grid_info["upper_price"] is None:
        grid_info["upper_price"] = config.UPPER_PRICE
        grid_info["lower_price"] = config.LOWER_PRICE
    
    status_data = {
        "status": "success",
        "bot_status": safe_emoji(bot_status),
        "latest_price": latest_price,
        "bot_profit": bot_profit,
        "grid_levels": grid_levels,
        "usdt_idr_rate": usdt_idr_rate,
        "ada_idr_value": ada_idr_value,
        "grid_info": grid_info,
        "balance_info": {
            "usdt_free": balance_info["usdt_free"],
            "usdt_locked": balance_info["usdt_locked"],
            "ada_free": balance_info["ada_free"],
            "ada_locked": balance_info["ada_locked"],
            "total_usdt_value": total_usdt_value,
            "total_idr_value": total_idr_value,
            "last_update": balance_info["last_update"]
        },
        "price_history": price_history[-100:] if price_history else []
    }
    return jsonify(status_data)

@app.route('/stream')
# @login_required (dinonaktifkan)
def stream():
    """Server-Sent Events endpoint untuk update realtime"""
    # Return empty response if SSE is disabled
    if SSE_DISABLED:
        return Response("SSE disabled", status=503)
        
    def event_stream():
        client_id = str(uuid.uuid4())
        client = {'id': client_id, 'queue': [], 'request_context': request}
        
        with data_lock:
            sse_clients.append(client)
        
        try:
            # Send initial data
            initial_data = get_initial_data()
            if initial_data:
                yield f"data: {json.dumps(initial_data)}\n\n"
            
            while True:
                # Check message queue
                with data_lock:
                    if client['queue']:
                        while client['queue']:
                            yield client['queue'].pop(0)
                
                # Heartbeat to keep connection alive
                yield f": heartbeat\n\n"
                
                # Sleep to reduce CPU usage
                time.sleep(1)
                
        except Exception as e:
            logger.error(f"SSE error: {e}")
        finally:
            with data_lock:
                if client in sse_clients:
                    sse_clients.remove(client)
                    logger.info(f"Removed SSE client {client_id}")
    
    response = Response(event_stream(), mimetype="text/event-stream")
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['X-Accel-Buffering'] = 'no'  # For NGINX
    return response

def get_initial_data():
    """Dapatkan data awal untuk stream"""
    global latest_price, usdt_idr_rate, balance_info
    
    # Pastikan selalu ada nilai harga
    if latest_price is None:
        latest_price = FALLBACK_PRICE
    
    # Pastikan selalu ada nilai USDT/IDR
    if usdt_idr_rate is None:
        usdt_idr_rate = 16350.0
    
    # Hitung nilai ADA dalam IDR
    ada_idr_value = latest_price * usdt_idr_rate
    
    # Hitung total nilai aset dalam USDT dan IDR
    total_ada = balance_info["ada_free"] + balance_info["ada_locked"]
    total_usdt = balance_info["usdt_free"] + balance_info["usdt_locked"]
    total_usdt_value = total_usdt + (total_ada * latest_price)
    total_idr_value = total_usdt_value * usdt_idr_rate
    
    # Dapatkan data grafik
    chart_data = None
    if price_history:
        timestamps = [entry['time'] for entry in price_history[-100:]]
        prices = [entry['price'] for entry in price_history[-100:]]
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=timestamps, y=prices, mode='lines', name='Harga ADA'))
        
        # Tambahkan garis grid jika tersedia
        if grid_levels:
            for level in grid_levels:
                fig.add_shape(
                    type="line",
                    x0=timestamps[0] if timestamps else 0,
                    y0=level,
                    x1=timestamps[-1] if timestamps else 1,
                    y1=level,
                    line=dict(color="Red", width=1, dash="dash"),
                )
        
        fig.update_layout(
            title='Pergerakan Harga ADA',
            xaxis_title='Waktu',
            yaxis_title='Harga (USDT)',
            template='plotly_dark'
        )
        
        chart_data = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
    
    # Siapkan data untuk dikirim
    return {
        "status": safe_emoji(bot_status),
        "latest_price": latest_price,
        "profit": bot_profit,
        "chart": chart_data,
        "trades": trades_history[-10:] if trades_history else [],
        "grid_levels": grid_levels,
        "usdt_idr_rate": usdt_idr_rate,
        "ada_idr_value": ada_idr_value,
        "balance": {
            "usdt_free": balance_info["usdt_free"],
            "usdt_locked": balance_info["usdt_locked"],
            "ada_free": balance_info["ada_free"],
            "ada_locked": balance_info["ada_locked"],
            "total_usdt_value": total_usdt_value,
            "total_idr_value": total_idr_value,
            "last_update": balance_info["last_update"]
        }
    }

def broadcast_update():
    """Broadcast update ke semua klien SSE"""
    # Skip if SSE is disabled
    if SSE_DISABLED or not sse_clients:
        return
        
    try:
        # Get current data
        data = get_initial_data()
        if not data:
            return
            
        # Create SSE message
        message = f"data: {json.dumps(data)}\n\n"
        
        # Send to all clients
        with data_lock:
            for client in list(sse_clients):
                try:
                    client['queue'].append(message)
                except Exception as e:
                    logger.error(f"Error queuing message: {e}")
                    if client in sse_clients:
                        sse_clients.remove(client)
    except Exception as e:
        logger.error(f"Error in broadcast_update: {e}")

def load_bot_data():
    """Load data dari file state bot"""
    global bot_status, latest_price, bot_profit, trades_history, grid_levels, price_history, usdt_idr_rate, balance_info
    
    try:
        # Check if bot process is running
        bot_is_running = False
        
        try:
            from grid_bot import GridTradingBot
            if hasattr(GridTradingBot, 'instance') and GridTradingBot.instance:
                bot_is_running = True
                bot_status = "Aktif"
                
                # Get data directly from bot instance
                if hasattr(GridTradingBot.instance, 'last_price'):
                    latest_price = GridTradingBot.instance.last_price
                
                if hasattr(GridTradingBot.instance, 'total_profit'):
                    # total_profit dalam bot sudah memperhitungkan fee
                    bot_profit = GridTradingBot.instance.total_profit
                    logger.debug(f"Loaded profit from bot instance: {bot_profit}")
                
                if hasattr(GridTradingBot.instance, 'trades'):
                    trades_history = GridTradingBot.instance.trades
                
                if hasattr(GridTradingBot.instance, 'grid_prices'):
                    grid_levels = GridTradingBot.instance.grid_prices.tolist()
                
                if hasattr(GridTradingBot.instance, 'price_history'):
                    price_history = GridTradingBot.instance.price_history
                
                # Get balance info
                try:
                    # Coba dapatkan saldo langsung dari client
                    if hasattr(GridTradingBot.instance, 'client'):
                        quote_asset = 'USDT'
                        base_asset = 'ADA'
                        
                        usdt_balance = GridTradingBot.instance.client.get_account_balance(quote_asset)
                        ada_balance = GridTradingBot.instance.client.get_account_balance(base_asset)
                        
                        if usdt_balance:
                            balance_info["usdt_free"] = usdt_balance['free']
                            balance_info["usdt_locked"] = usdt_balance['locked']
                        
                        if ada_balance:
                            balance_info["ada_free"] = ada_balance['free']
                            balance_info["ada_locked"] = ada_balance['locked']
                        
                        balance_info["last_update"] = datetime.datetime.now().isoformat()
                        
                        # Dapatkan kurs USDT/IDR
                        usdt_idr_rate = GridTradingBot.instance.client.get_usdt_idr_rate()
                except Exception as e:
                    logger.warning(f"Failed to get balance info from bot instance: {e}")
        except Exception as e:
            logger.warning(f"Failed to get data from bot instance: {e}")
        
        # If bot is not running, load data from state file
        if not bot_is_running:
            bot_status = "Tidak Aktif"
            state_file = f"grid_state_{config.SYMBOL}.json"
            
            if os.path.exists(state_file):
                try:
                    with open(state_file, 'r') as f:
                        state = json.load(f)
                        
                        if 'total_profit' in state:
                            bot_profit = state['total_profit']
                        
                        if 'trades' in state:
                            trades_history = state['trades']
                        
                        if 'last_price' in state:
                            latest_price = state['last_price']
                        
                        if 'price_range' in state and len(state['price_range']) == 2:
                            lower_price = state['price_range'][0]
                            upper_price = state['price_range'][1]
                            grid_number = state.get('grid_number', config.GRID_NUMBER)
                            
                            # Calculate grid levels
                            grid_levels = np.linspace(lower_price, upper_price, grid_number + 1).tolist()
                except Exception as e:
                    logger.error(f"Failed to load grid state: {e}")
            
            # Fallback for grid levels if none available
            if not grid_levels:
                grid_levels = np.linspace(config.LOWER_PRICE, config.UPPER_PRICE, config.GRID_NUMBER + 1).tolist()
        
        # Fallback for price history if none available
        if not price_history and latest_price:
            now = datetime.datetime.now().isoformat()
            five_min_ago = (datetime.datetime.now() - datetime.timedelta(minutes=5)).isoformat()
            price_history = [
                {"time": five_min_ago, "price": latest_price, "usdt_idr": usdt_idr_rate or 16350.0},
                {"time": now, "price": latest_price, "usdt_idr": usdt_idr_rate or 16350.0}
            ]
        
        # Parse trades from log if no trades available
        if not trades_history:
            trades_history = parse_trades_from_log()
    
    except Exception as e:
        logger.error(f"Error loading bot data: {e}")

def update_data_thread():
    """Thread untuk update data secara periodik"""
    last_fetch_time = 0
    
    # Create application context for this thread
    with app.app_context():
        while True:
            current_time = time.time()
            
            # Batasi pembaruan menjadi maksimal setiap 2 detik
            if current_time - last_fetch_time >= 2:
                with data_lock:
                    # Simpan waktu fetch
                    last_fetch_time = current_time
                    
                    # Load data
                    load_bot_data()
                    
                    # Jika masih tidak ada harga terkini, coba dapatkan langsung
                    global latest_price, bot_status
                    if latest_price is None:
                        try:
                            # Coba dari instansi bot terlebih dahulu
                            try:
                                from grid_bot import GridTradingBot
                                if hasattr(GridTradingBot, 'instance') and GridTradingBot.instance:
                                    if hasattr(GridTradingBot.instance, 'last_price'):
                                        latest_price = GridTradingBot.instance.last_price
                                        logger.info(f"Got price directly from bot instance: {latest_price}")
                                    
                                    # Set bot status to active since we have a running bot instance
                                    bot_status = "Aktif"
                            except:
                                pass
                                
                            # Jika masih None, coba dari API
                            if latest_price is None:
                                from binance_client import BinanceClient
                                client = BinanceClient()
                                current_price = client.get_symbol_price(config.SYMBOL)
                                if current_price:
                                    latest_price = current_price
                                    logger.info(f"Thread update got price from API: {latest_price}")
                                    # Tambahkan ke history jika belum ada
                                    current_time_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                    if not price_history:
                                        price_history.append({
                                            "time": current_time_str,
                                            "price": current_price,
                                            "usdt_idr": client.get_usdt_idr_rate()
                                        })
                                    else:
                                        # Only add if more than 5 seconds from last entry to avoid too many entries
                                        last_entry_time = datetime.datetime.strptime(price_history[-1]["time"], "%Y-%m-%d %H:%M:%S,%f" if "," in price_history[-1]["time"] else "%Y-%m-%d %H:%M:%S")
                                        current_dt = datetime.datetime.strptime(current_time_str, "%Y-%m-%d %H:%M:%S")
                                        if (current_dt - last_entry_time).total_seconds() > 5:
                                            price_history.append({
                                                "time": current_time_str,
                                                "price": current_price,
                                                "usdt_idr": client.get_usdt_idr_rate()
                                            })
                        except Exception as e:
                            logger.error(f"Thread update failed to get price: {e}")
                
                # Broadcast update ke semua klien setiap kali data diperbarui
                if sse_clients and not SSE_DISABLED:
                    try:
                        broadcast_update()
                    except Exception as e:
                        logger.error(f"Error broadcasting update: {e}")
                    
            # Jangan sleep terlalu lama untuk menghindari delay dalam respon
            time.sleep(0.5)

def create_templates():
    """Buat folder templates dan file template HTML jika belum ada"""
    if not os.path.exists("templates"):
        os.makedirs("templates")
    
    # Buat file template login.html
    with open("templates/login.html", "w", encoding="utf-8") as f:
        f.write("""
<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Login - Bot Trading Grid</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha1/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body {
            background-color: #121212;
            color: #e0e0e0;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .login-container {
            background-color: #1e1e1e;
            border-radius: 8px;
            padding: 30px;
            width: 100%;
            max-width: 400px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }
        .login-title {
            text-align: center;
            margin-bottom: 30px;
            color: #e0e0e0;
        }
        .form-control {
            background-color: #333;
            border-color: #444;
            color: #e0e0e0;
        }
        .form-control:focus {
            background-color: #444;
            color: #fff;
            border-color: #0d6efd;
            box-shadow: 0 0 0 0.25rem rgba(13, 110, 253, 0.25);
        }
        .btn-primary {
            width: 100%;
            margin-top: 20px;
        }
        .alert {
            margin-top: 20px;
        }
    </style>
</head>
<body>
    <div class="login-container">
        <h2 class="login-title">Grid Trading Bot</h2>
        
        {% if error %}
        <div class="alert alert-danger" role="alert">
            {{ error }}
        </div>
        {% endif %}
        
        <form method="post">
            <div class="mb-3">
                <label for="username" class="form-label">Username</label>
                <input type="text" class="form-control" id="username" name="username" required>
            </div>
            <div class="mb-3">
                <label for="password" class="form-label">Password</label>
                <input type="password" class="form-control" id="password" name="password" required>
            </div>
            <button type="submit" class="btn btn-primary">Login</button>
        </form>
    </div>
</body>
</html>
        """)
    
    # Buat file template HTML utama (dashboard sederhana)
    with open("templates/index.html", "w", encoding="utf-8") as f:
        f.write("""
<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dashboard Bot Trading Grid</title>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha1/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body {
            background-color: #121212;
            color: #e0e0e0;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }
        .container {
            padding-top: 20px;
            max-width: 1200px;
        }
        .card {
            background-color: #1e1e1e;
            border: 1px solid #333;
            margin-bottom: 20px;
            border-radius: 8px;
        }
        .card-header {
            background-color: #252525;
            color: #e0e0e0;
            font-weight: bold;
            border-bottom: 1px solid #333;
        }
        .price-card {
            text-align: center;
            padding: 20px;
        }
        .current-price {
            font-size: 2.5rem;
            font-weight: bold;
            margin-bottom: 0;
        }
        .price-change {
            font-size: 1.2rem;
            margin-top: 5px;
        }
        .profit {
            color: #4caf50;
            font-weight: bold;
        }
        .loss {
            color: #f44336;
            font-weight: bold;
        }
        .neutral {
            color: #bdbdbd;
        }
        .table {
            color: #e0e0e0;
        }
        .table thead th {
            border-color: #333;
            background-color: #252525;
        }
        .table td, .table th {
            border-color: #333;
        }
        .balance-item {
            display: flex;
            justify-content: space-between;
            margin-bottom: 10px;
            font-size: 1.1rem;
        }
        .status-badge {
            padding: 5px 10px;
            border-radius: 5px;
            font-weight: bold;
        }
        .status-active {
            background-color: #4caf50;
            color: #fff;
        }
        .status-inactive {
            background-color: #f44336;
            color: #fff;
        }
        .total-profit {
            font-size: 1.8rem;
            text-align: center;
            padding: 15px 0;
        }
        .grid-item {
            display: flex;
            justify-content: space-between;
            padding: 10px 0;
            border-bottom: 1px solid #333;
        }
        .grid-item:last-child {
            border-bottom: none;
        }
        .grid-price {
            font-weight: bold;
        }
        .refresh-btn {
            margin-bottom: 20px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="row mb-4">
            <div class="col-12">
                <h1 class="text-center mb-4">Bot Trading Grid Dashboard</h1>
                <button id="refresh-data" class="btn btn-primary refresh-btn">Refresh Data</button>
            </div>
        </div>

        <div class="row">
            <!-- Status & Harga ADA/USDT -->
            <div class="col-md-4">
                <div class="card">
                    <div class="card-header">Status Bot & ADA/USDT</div>
                    <div class="card-body">
                        <div class="d-flex justify-content-between align-items-center mb-4">
                            <span>Status Bot:</span>
                            <span id="bot-status" class="status-badge status-inactive">Tidak Aktif</span>
                        </div>
                        <div class="price-card">
                            <h5>Harga ADA/USDT</h5>
                            <p class="current-price" id="current-price">0.0000</p>
                            <p class="price-change" id="price-change"><span class="neutral">(0.00%)</span></p>
                            <small class="text-muted" id="price-time">Terakhir diperbarui: --:--:--</small>
                        </div>
                        <div class="total-profit mt-3">
                            <div>Total Profit:</div>
                            <span id="total-profit" class="profit">0.00 USDT</span>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Saldo Akun -->
            <div class="col-md-4">
                <div class="card">
                    <div class="card-header">Saldo Akun Binance</div>
                    <div class="card-body">
                        <div class="balance-item">
                            <span>ADA (Free):</span>
                            <span id="ada-free">0.00</span>
                        </div>
                        <div class="balance-item">
                            <span>ADA (Locked):</span>
                            <span id="ada-locked">0.00</span>
                        </div>
                        <div class="balance-item">
                            <span>USDT (Free):</span>
                            <span id="usdt-free">0.00</span>
                        </div>
                        <div class="balance-item">
                            <span>USDT (Locked):</span>
                            <span id="usdt-locked">0.00</span>
                        </div>
                        <div class="balance-item mt-3">
                            <span>ADA/IDR:</span>
                            <span id="ada-idr">0</span>
                        </div>
                        <div class="balance-item">
                            <span>USDT/IDR:</span>
                            <span id="usdt-idr">0</span>
                        </div>
                        <div class="mt-3 text-muted text-center">
                            <small id="balance-update-time">Terakhir diperbarui: --:--:--</small>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Data Grid -->
            <div class="col-md-4">
                <div class="card">
                    <div class="card-header">Data Grid</div>
                    <div class="card-body">
                        <div class="mb-3">
                            <div class="grid-item">
                                <span>Batas Atas:</span>
                                <span id="upper-price" class="grid-price">0.0000</span>
                            </div>
                            <div class="grid-item">
                                <span>Batas Bawah:</span>
                                <span id="lower-price" class="grid-price">0.0000</span>
                            </div>
                            <div class="grid-item">
                                <span>Jumlah Grid:</span>
                                <span id="grid-number">0</span>
                            </div>
                            <div class="grid-item">
                                <span>Ukuran Order:</span>
                                <span id="order-quantity">0 ADA</span>
                            </div>
                        </div>
                        <div id="grid-levels" class="mt-4">
                            <div class="text-center text-muted">Loading data grid...</div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Chart ADA/USDT -->
        <div class="row mt-4">
            <div class="col-12">
                <div class="card">
                    <div class="card-header">Grafik Harga ADA/USDT</div>
                    <div class="card-body">
                        <div id="price-chart" style="height: 400px;">
                            <div class="d-flex justify-content-center align-items-center h-100">
                                <div class="spinner-border text-primary" role="status">
                                    <span class="visually-hidden">Loading...</span>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Riwayat Transaksi -->
        <div class="row mt-4">
            <div class="col-12">
                <div class="card">
                    <div class="card-header">Riwayat Transaksi</div>
                    <div class="card-body">
                        <div class="table-responsive">
                            <table class="table">
                                <thead>
                                    <tr>
                                        <th>Waktu</th>
                                        <th>Tipe</th>
                                        <th>Harga</th>
                                        <th>Jumlah</th>
                                        <th>Nilai USDT</th>
                                        <th>Profit</th>
                                    </tr>
                                </thead>
                                <tbody id="trades-table">
                                    <tr>
                                        <td colspan="6" class="text-center">Belum ada riwayat transaksi</td>
                                    </tr>
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        // Fungsi untuk memformat angka dengan 4 desimal
        function formatNumber(num, decimals = 4) {
            return num ? parseFloat(num).toFixed(decimals) : "0.0000";
        }
        
        // Fungsi untuk memformat angka sebagai mata uang IDR
        function formatIDR(num) {
            return new Intl.NumberFormat('id-ID', { 
                style: 'currency', 
                currency: 'IDR',
                minimumFractionDigits: 0,
                maximumFractionDigits: 0
            }).format(num);
        }
        
        // Fungsi untuk memperbarui data dari server
        function updateDashboard() {
            // Ambil data status
            $.get('/api/status', function(data) {
                if(data.status === 'success') {
                    // Update status bot
                    $('#bot-status').text(data.bot_status);
                    if(data.bot_status === 'Aktif') {
                        $('#bot-status').removeClass('status-inactive').addClass('status-active');
                    } else {
                        $('#bot-status').removeClass('status-active').addClass('status-inactive');
                    }
                    
                    // Update harga
                    if(data.latest_price) {
                        $('#current-price').text(formatNumber(data.latest_price));
                        $('#price-time').text('Terakhir diperbarui: ' + new Date().toLocaleTimeString());
                        
                        // Hitung perubahan harga jika ada price history
                        if(data.price_history && data.price_history.length > 1) {
                            const oldPrice = data.price_history[0].price;
                            const newPrice = data.latest_price;
                            const change = ((newPrice - oldPrice) / oldPrice) * 100;
                            const changeClass = change > 0 ? 'profit' : (change < 0 ? 'loss' : 'neutral');
                            $('#price-change').html(`<span class="${changeClass}">(${change.toFixed(2)}%)</span>`);
                        }
                    }
                    
                    // Update data saldo
                    if(data.balance_info) {
                        $('#ada-free').text(formatNumber(data.balance_info.ada_free));
                        $('#ada-locked').text(formatNumber(data.balance_info.ada_locked));
                        $('#usdt-free').text(formatNumber(data.balance_info.usdt_free, 2));
                        $('#usdt-locked').text(formatNumber(data.balance_info.usdt_locked, 2));
                        
                        // Update kurs
                        if(data.usdt_idr_rate) {
                            $('#usdt-idr').text(formatIDR(data.usdt_idr_rate));
                            
                            // Hitung ADA/IDR
                            if(data.latest_price) {
                                const adaIdr = data.latest_price * data.usdt_idr_rate;
                                $('#ada-idr').text(formatIDR(adaIdr));
                            }
                        }
                        
                        if(data.balance_info.last_update) {
                            $('#balance-update-time').text('Terakhir diperbarui: ' + new Date(data.balance_info.last_update).toLocaleTimeString());
                        }
                    }
                    
                    // Update total profit
                    if(data.bot_profit) {
                        $('#total-profit').text(formatNumber(data.bot_profit, 2) + ' USDT');
                    }
                    
                    // Update grid data
                    if(data.grid_info) {
                        $('#upper-price').text(formatNumber(data.grid_info.upper_price));
                        $('#lower-price').text(formatNumber(data.grid_info.lower_price));
                        $('#grid-number').text(data.grid_info.grid_number);
                        $('#order-quantity').text(data.grid_info.quantity + ' ADA');
                        
                        // Update grid levels
                        if(data.grid_levels && data.grid_levels.length > 0) {
                            let gridHtml = '';
                            data.grid_levels.forEach(level => {
                                const levelClass = level > data.latest_price ? 'profit' : (level < data.latest_price ? 'loss' : 'neutral');
                                gridHtml += `<div class="grid-item">
                                    <span>Level:</span>
                                    <span class="${levelClass}">${formatNumber(level)}</span>
                                </div>`;
                            });
                            $('#grid-levels').html(gridHtml);
                        }
                    }
                }
            });
            
            // Update grafik harga
            $.get('/api/price_chart', function(data) {
                if(data.status === 'success' && data.chart) {
                    Plotly.newPlot('price-chart', JSON.parse(data.chart));
                }
            });
            
            // Update riwayat transaksi
            $.get('/api/trades', function(data) {
                if(data.status === 'success' && data.trades) {
                    if(data.trades.length > 0) {
                        let tradesHtml = '';
                        
                        // Tampilkan transaksi terbaru terlebih dahulu (reverse)
                        data.trades.reverse().forEach(trade => {
                            const tradeTime = new Date(trade.time).toLocaleString();
                            const tradeType = trade.side || trade.type;
                            const typeClass = tradeType === 'SELL' || tradeType === 'sell' ? 'profit' : 'neutral';
                            const profit = trade.actual_profit || trade.profit;
                            const profitClass = profit > 0 ? 'profit' : 'loss';
                            
                            tradesHtml += `<tr>
                                <td>${tradeTime}</td>
                                <td class="${typeClass}">${tradeType}</td>
                                <td>${formatNumber(trade.price)}</td>
                                <td>${trade.quantity}</td>
                                <td>${formatNumber(trade.value || (trade.price * trade.quantity), 2)}</td>
                                <td class="${profitClass}">${profit ? formatNumber(profit, 4) : '-'}</td>
                            </tr>`;
                        });
                        
                        $('#trades-table').html(tradesHtml);
                    }
                }
            });
        }
        
        // Perbarui data saat halaman dimuat
        $(document).ready(function() {
            updateDashboard();
            
            // Perbarui data secara berkala setiap 10 detik
            setInterval(updateDashboard, 10000);
            
            // Tombol refresh manual
            $('#refresh-data').click(function() {
                $(this).text('Memperbarui...');
                updateDashboard();
                setTimeout(() => {
                    $(this).text('Refresh Data');
                }, 1000);
            });
        });
    </script>
</body>
</html>
        """)

@app.route('/api/orders')
# @login_required (dinonaktifkan)
def get_orders():
    """API endpoint untuk mendapatkan data order spot aktif"""
    try:
        # Coba dapatkan dari instance bot aktif
        from grid_bot import GridTradingBot
        orders = []
        
        if hasattr(GridTradingBot, 'instance') and GridTradingBot.instance is not None:
            bot = GridTradingBot.instance
            
            # Dapatkan info order dari instance bot
            if hasattr(bot, 'buy_orders'):
                for price, order_id in bot.buy_orders.items():
                    orders.append({
                        'orderId': order_id,
                        'side': 'BUY',
                        'price': price,
                        'origQty': bot.quantity,
                        'status': 'NEW'
                    })
            
            if hasattr(bot, 'sell_orders'):
                for price, order_id in bot.sell_orders.items():
                    orders.append({
                        'orderId': order_id,
                        'side': 'SELL',
                        'price': price,
                        'origQty': bot.quantity,
                        'status': 'NEW'
                    })
        
        # Jika tidak ada data dari bot instance, coba dapatkan dari API
        if not orders:
            try:
                from binance_client import BinanceClient
                client = BinanceClient()
                open_orders = client.get_open_orders(config.SYMBOL)
                if open_orders:
                    orders = open_orders
            except Exception as e:
                logger.error(f"Error getting orders from Binance API: {e}")
        
        return jsonify({'orders': orders})
    except Exception as e:
        logger.error(f"Error getting order data: {e}")
        return jsonify({'orders': []})

def run_dashboard():
    """Jalankan dashboard web"""
    # Buat templates jika belum ada
    create_templates()
    
    # Muat data bot
    load_bot_data()
    
    # Initialize sse_clients if not disabled
    global sse_clients
    if sse_clients is None and not SSE_DISABLED:
        sse_clients = []
    
    # Jalankan thread untuk update data
    update_thread = Thread(target=update_data_thread)
    update_thread.daemon = True
    update_thread.start()
    
    # Jalankan thread untuk session cleanup
    session_cleanup_thread = Thread(target=check_for_session_timeout)
    session_cleanup_thread.daemon = True
    session_cleanup_thread.start()
    
    # Untuk production, gunakan Gunicorn untuk menjalankan aplikasi
    # Fungsi ini hanya untuk development
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)

if __name__ == "__main__":
    run_dashboard() 