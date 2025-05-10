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
        
        return jsonify(trades=trades_data)
    except Exception as e:
        logger.error(f"Error in trades API: {e}")
        return jsonify(trades=[])

def parse_trades_from_log():
    """Parse riwayat transaksi dari file log"""
    trades = []
    try:
        with open("bot.log", "r", encoding="utf-8") as log_file:
            lines = log_file.readlines()
            
            for line in lines:
                # Cari baris log yang berisi informasi transaksi
                if "TRADE FILLED" in line or "Order filled" in line:
                    try:
                        # Contoh format: "BUY order filled at 0.7850"
                        parts = line.split(" - ")
                        if len(parts) >= 2:
                            timestamp = parts[0].strip()
                            message = parts[1]
                            
                            # Ekstrak informasi
                            if "BUY" in message:
                                type_order = "BUY"
                            elif "SELL" in message:
                                type_order = "SELL"
                            else:
                                continue
                            
                            # Coba ekstrak harga
                            price_match = re.search(r'at\s+(\d+\.\d+)', message)
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
                            profit = float(profit_match.group(1)) if profit_match else 0.0
                            
                            trade = {
                                "time": timestamp,
                                "type": type_order,
                                "price": price,
                                "quantity": quantity,
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
    global latest_price, usdt_idr_rate, balance_info
    
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
    
    status_data = {
        "status": safe_emoji(bot_status),
        "latest_price": latest_price,
        "profit": bot_profit,
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
        for process in psutil.process_iter():
            try:
                if process.name() == "python.exe" and len(process.cmdline()) > 1:
                    cmd = ' '.join(process.cmdline())
                    if "run.py" in cmd and "bot" in cmd and "--dashboard" not in cmd:
                        bot_is_running = True
                        break
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
                
        # Force status to Aktif if grid_bot is actively logging
        try:
            log_modified_time = os.path.getmtime("bot.log")
            current_time = time.time()
            time_diff = current_time - log_modified_time
            
            if time_diff < 30:  # Log modified in last 30 seconds
                bot_status = "Aktif"
            elif time_diff < 300:  # Log modified in last 5 minutes
                bot_status = "Mungkin Aktif"
            else:
                bot_status = "Tidak Aktif (Tidak ada update log)" 
        except:
            if bot_is_running:
                bot_status = "Proses Berjalan"
            else:
                bot_status = "Tidak Aktif"
        
        # Variabel untuk menyimpan informasi saldo dari log
        usdt_free = 0
        usdt_locked = 0
        ada_free = 0
        ada_locked = 0
        last_balance_update = None
        
        # Update price history dan balance dari log
        try:
            with open("bot.log", "r", encoding="utf-8") as log_file:
                lines = log_file.readlines()
                price_data = []
                
                # Cari 100 entri harga terbaru
                for line in reversed(lines):
                    # Cek informasi saldo terbaru
                    if "[BALANCE]" in line:
                        try:
                            # Contoh format: "[BALANCE] USDT: 2.9447 (Free) + 10.2050 (Locked) | ADA: 4.9790 (Free) + 13.0000 (Locked)"
                            balance_parts = line.split("[BALANCE]")[1].strip().split("|")
                            if len(balance_parts) >= 2:
                                # Parse USDT balance
                                usdt_part = balance_parts[0].strip()
                                if "USDT:" in usdt_part:
                                    usdt_values = usdt_part.split(":")
                                    if len(usdt_values) >= 2:
                                        usdt_amounts = usdt_values[1].strip().split("+")
                                        if len(usdt_amounts) >= 2:
                                            usdt_free = float(usdt_amounts[0].split("(")[0].strip())
                                            usdt_locked = float(usdt_amounts[1].split("(")[0].strip())
                                
                                # Parse ADA balance
                                ada_part = balance_parts[1].strip()
                                if "ADA:" in ada_part:
                                    ada_values = ada_part.split(":")
                                    if len(ada_values) >= 2:
                                        ada_amounts = ada_values[1].strip().split("+")
                                        if len(ada_amounts) >= 2:
                                            ada_free = float(ada_amounts[0].split("(")[0].strip())
                                            ada_locked = float(ada_amounts[1].split("(")[0].strip())
                                
                                # Update global balance info
                                balance_info["usdt_free"] = usdt_free
                                balance_info["usdt_locked"] = usdt_locked
                                balance_info["ada_free"] = ada_free
                                balance_info["ada_locked"] = ada_locked
                                balance_info["last_update"] = line.split(" - ")[0].strip()
                                
                                # Set bot status to active if we found a recent balance update
                                time_str = line.split(" - ")[0].strip()
                                try:
                                    log_time = datetime.datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S,%f")
                                    time_diff = (datetime.datetime.now() - log_time).total_seconds()
                                    if time_diff < 60:  # Less than 1 minute
                                        bot_status = "Aktif"
                                except:
                                    pass
                                
                                break  # Only need the most recent balance info
                        except Exception as e:
                            logger.debug(f"Gagal parsing info saldo: {e}")
                    
                    # Cek informasi harga
                    if "[PRICE UPDATE]" in line:
                        try:
                            # Contoh format: "[PRICE UPDATE] ADAUSDT: 0.7973 | USDT/IDR: 16527.00 | ADA/IDR: 13176.98 | Change: 0.01% | Profit: 0.0000 USDT | Time: 18:27:37"
                            parts = line.split("[PRICE UPDATE]")[1].strip().split("|")
                            
                            if len(parts) >= 1:  # Minimal price part
                                symbol_price = parts[0].strip().split(":")
                                if len(symbol_price) == 2:
                                    symbol = symbol_price[0].strip()
                                    price = float(symbol_price[1].strip())
                                    timestamp = line.split(" - ")[0].strip()
                                    
                                    # Update latest_price immediately
                                    latest_price = price
                                    logger.info(f"Found price in log: {price}")
                                    
                                    # Update bot status based on price update timeliness
                                    try:
                                        log_time = datetime.datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S,%f")
                                        time_diff = (datetime.datetime.now() - log_time).total_seconds()
                                        if time_diff < 60:  # Less than 1 minute
                                            bot_status = "Aktif"
                                    except:
                                        pass
                                    
                                    # Cek apakah ada info USDT/IDR dalam log
                                    usdt_idr_info = None
                                    for part in parts:
                                        if "USDT/IDR:" in part:
                                            usdt_idr_rate_str = part.split(":")[1].strip()
                                            usdt_idr_info = float(usdt_idr_rate_str)
                                            break
                                    
                                    # Cek jika ada informasi profit
                                    profit_info = None
                                    for part in parts:
                                        if "Profit:" in part:
                                            profit_str = part.split(":")[1].strip().split()[0]  # Get value before USDT
                                            try:
                                                profit_info = float(profit_str)
                                                bot_profit = profit_info  # Update global profit
                                            except:
                                                pass
                                            break
                                    
                                    price_data.append({
                                        "time": timestamp,
                                        "price": price,
                                        "usdt_idr": usdt_idr_info,
                                        "profit": profit_info
                                    })
                                    
                                    # Ambil nilai USDT/IDR dari entri terbaru
                                    if usdt_idr_info and usdt_idr_rate is None:
                                        usdt_idr_rate = usdt_idr_info
                                    
                                    # Hentikan jika sudah mendapatkan 100 data harga
                                    if len(price_data) >= 100:
                                        break
                        except Exception as e:
                            logger.debug(f"Gagal parsing baris log price update: {e}")
                            continue
                
                # Balik kembali urutan data untuk kronologis
                price_data.reverse()
                
                # Simpan data harga
                if price_data:
                    price_history = price_data
                    latest_price = price_data[-1]["price"]
                    logger.info(f"Loaded latest price from log: {latest_price}")
                    
                    # Update profit if available in the latest price data
                    if "profit" in price_data[-1] and price_data[-1]["profit"] is not None:
                        bot_profit = price_data[-1]["profit"]
        except Exception as e:
            logger.error(f"Error reading log file: {e}")
        
        # Cari grid info dari log juga
        try:
            with open("bot.log", "r", encoding="utf-8") as log_file:
                lines = log_file.readlines()
                
                # Look for grid setup information
                for line in reversed(lines):
                    if "Price range:" in line:
                        try:
                            # Format: "Price range: 0.785 - 0.815"
                            range_info = line.split("Price range:")[1].strip()
                            range_parts = range_info.split("-")
                            if len(range_parts) == 2:
                                lower_price = float(range_parts[0].strip())
                                upper_price = float(range_parts[1].strip())
                                grid_levels = [lower_price, upper_price]
                                logger.info(f"Found grid levels in log: {lower_price} - {upper_price}")
                                break
                        except Exception as e:
                            logger.debug(f"Failed to parse grid range info: {e}")
        except Exception as e:
            logger.error(f"Error reading log file for grid info: {e}")
        
        # Jika masih tidak ada grid levels, coba dari state file
        if not grid_levels:
            # Load state bot
            state_files = [f for f in os.listdir(".") if f.startswith("grid_state_") and f.endswith(".json")]
            if state_files:
                latest_state_file = state_files[0]  # Ambil file pertama jika ada beberapa
                
                with open(latest_state_file, "r") as f:
                    state = json.load(f)
                    # Get grid levels from state file if not already found
                    if "price_range" in state:
                        grid_levels = state.get("price_range", [])
                        logger.info(f"Found grid levels in state file: {grid_levels}")
        
        # Jika tidak ada harga dari log, coba dapatkan harga terkini dari API
        if latest_price is None:
            try:
                # Coba dapatkan dari API Binance
                from binance_client import BinanceClient
                client = BinanceClient()
                current_price = client.get_symbol_price(config.SYMBOL)
                if current_price:
                    latest_price = current_price
                    logger.info(f"Got current price from API: {latest_price}")
                    
                    # Dapatkan nilai USDT/IDR
                    if usdt_idr_rate is None:
                        usdt_idr_rate = client.get_usdt_idr_rate()
                        logger.info(f"Got USDT/IDR rate from API: {usdt_idr_rate}")
                    
                    # Tambahkan ke history
                    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    price_history.append({
                        "time": current_time,
                        "price": current_price,
                        "usdt_idr": usdt_idr_rate
                    })
            except Exception as e:
                logger.error(f"Error getting current price from API: {e}")
                
                # Jika masih tidak berhasil, coba mungkin ada instance bot yang berjalan
                try:
                    from grid_bot import GridTradingBot
                    if hasattr(GridTradingBot, 'instance') and GridTradingBot.instance is not None:
                        bot_instance = GridTradingBot.instance
                        if hasattr(bot_instance, 'last_price') and bot_instance.last_price is not None:
                            latest_price = bot_instance.last_price
                            logger.info(f"Got current price from bot instance: {latest_price}")
                            
                            current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            price_history.append({
                                "time": current_time,
                                "price": latest_price
                            })
                except Exception as e:
                    logger.error(f"Error getting price from bot instance: {e}")
        
        # Jika masih belum ada nilai USDT/IDR, gunakan fallback
        if usdt_idr_rate is None:
            usdt_idr_rate = 16350.0  # Nilai fallback terbaru
        
        # Load state file for trades history if not already loaded
        state_files = [f for f in os.listdir(".") if f.startswith("grid_state_") and f.endswith(".json")]
        if state_files and not trades_history:
            latest_state_file = state_files[0]  # Ambil file pertama jika ada beberapa
            
            with open(latest_state_file, "r") as f:
                state = json.load(f)
                bot_profit = state.get("total_profit", 0)
                trades_history = state.get("trades", [])
                last_update = state.get("last_update")
                
                # Update latest price jika ada di state dan lebih baru
                if "last_price" in state and state["last_price"] is not None:
                    state_price = float(state["last_price"])
                    
                    if latest_price is None:
                        latest_price = state_price
                        logger.info(f"Using price from state file: {latest_price}")
                        
                        # Tambahkan ke history jika kosong
                        if not price_history:
                            price_history.append({
                                "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                "price": state_price
                            })
    except Exception as e:
        logger.error(f"Error loading bot data: {e}")
        
    # Make sure we never use fallback unless necessary
    if latest_price is None:
        latest_price = FALLBACK_PRICE
        logger.warning(f"Using fallback price as last resort: {FALLBACK_PRICE}")
        
    # Log final state of data
    logger.info(f"Final data state - Status: {bot_status}, Price: {latest_price}, Grid Levels: {grid_levels}")

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
    
    # Buat file template HTML utama (dashboard)
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
        .profit {
            color: #4caf50;
            font-weight: bold;
        }
        .loss {
            color: #f44336;
            font-weight: bold;
        }
        .table {
            color: #e0e0e0;
        }
        .table thead th {
            border-color: #333;
        }
        .table tbody td {
            border-color: #333;
        }
        .badge-success {
            background-color: #4caf50;
        }
        .badge-danger {
            background-color: #f44336;
        }
        .badge-warning {
            background-color: #ff9800;
        }
        #priceChart {
            width: 100%;
            height: 400px;
        }
        .status-card {
            text-align: center;
            padding: 15px;
        }
        .status-icon {
            font-size: 3rem;
            margin-bottom: 10px;
        }
        .refresh-btn {
            position: fixed;
            bottom: 20px;
            right: 20px;
            z-index: 999;
        }
        .header-actions {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
        }
        /* Indikator realtime */
        .realtime-indicator {
            position: fixed;
            top: 10px;
            right: 20px;
            z-index: 999;
            background-color: rgba(33, 37, 41, 0.7);
            padding: 5px 10px;
            border-radius: 20px;
            font-size: 0.8rem;
            display: flex;
            align-items: center;
        }
        .realtime-indicator .status-dot {
            height: 8px;
            width: 8px;
            border-radius: 50%;
            margin-right: 8px;
            background-color: #f44336;
        }
        .realtime-indicator .status-dot.connected {
            background-color: #4caf50;
        }
        .realtime-indicator .status-dot.reconnecting {
            background-color: #ff9800;
            animation: blink 1s infinite;
        }
        @keyframes blink {
            0% { opacity: 0.4; }
            50% { opacity: 1; }
            100% { opacity: 0.4; }
        }
        .last-updated {
            margin-top: 3px;
            font-size: 0.7rem;
            color: #aaa;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header-actions">
            <h1>Dashboard Bot Trading Grid</h1>
        </div>
        
        <!-- Indikator realtime -->
        <div class="realtime-indicator">
            <div id="status-dot" class="status-dot"></div>
            <div>
                <span id="connection-status">Menghubungkan...</span>
                <div id="last-updated" class="last-updated"></div>
            </div>
        </div>
        
        <div class="row">
            <div class="col-md-4">
                <div class="card status-card">
                    <div class="card-body">
                        <div class="status-icon">
                            <span id="statusIcon">BOT</span>
                        </div>
                        <h5>Status Bot</h5>
                        <h3><span id="botStatus" class="badge"></span></h3>
                    </div>
                </div>
            </div>
            <div class="col-md-4">
                <div class="card status-card">
                    <div class="card-body">
                        <div class="status-icon">IDR</div>
                        <h5>Total Profit</h5>
                        <h3><span id="totalProfit"></span> USDT</h3>
                    </div>
                </div>
            </div>
            <div class="col-md-4">
                <div class="card status-card">
                    <div class="card-body">
                        <div class="status-icon">ADA</div>
                        <h5>Harga ADA Terkini</h5>
                        <h3><span id="currentPrice"></span> USDT</h3>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="card mt-4">
            <div class="card-header">
                Grafik Harga (Update Real-time)
            </div>
            <div class="card-body">
                <div id="priceChart"></div>
            </div>
        </div>
        
        <div class="card">
            <div class="card-header">
                Riwayat Trading Terakhir
            </div>
            <div class="card-body">
                <div class="table-responsive">
                    <table class="table table-hover" id="tradesTable">
                        <thead>
                            <tr>
                                <th>Waktu</th>
                                <th>Tipe</th>
                                <th>Harga</th>
                                <th>Jumlah</th>
                                <th>Profit</th>
                            </tr>
                        </thead>
                        <tbody id="tradesBody">
                            <!-- Data akan diisi melalui JavaScript -->
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
        
        <div class="card">
            <div class="card-header">
                Level Grid
            </div>
            <div class="card-body">
                <div class="row" id="gridLevels">
                    <!-- Grid levels akan diisi melalui JavaScript -->
                </div>
            </div>
        </div>
    </div>
    
    <button class="btn btn-primary refresh-btn" onclick="refreshData()">
        Refresh Data
    </button>

    <script>
        // Koneksi SSE untuk update realtime
        let eventSource;
        
        function connectSSE() {
            if (!!window.EventSource) {
                eventSource = new EventSource('/stream');
                
                eventSource.addEventListener('open', function() {
                    console.log('SSE connection opened');
                    updateConnectionStatus('connected');
                });
                
                eventSource.addEventListener('error', function(e) {
                    if (e.readyState == EventSource.CLOSED) {
                        console.log('SSE connection closed');
                        updateConnectionStatus('disconnected');
                    } else {
                        console.error('SSE connection error:', e);
                        updateConnectionStatus('reconnecting');
                        // Reconnect after error
                        setTimeout(connectSSE, 5000);
                    }
                });
                
                eventSource.addEventListener('message', function(e) {
                    try {
                        const data = JSON.parse(e.data);
                        updateDashboard(data);
                        updateLastUpdated();
                    } catch (err) {
                        console.error('Error parsing SSE data:', err);
                    }
                });
            } else {
                console.warn('SSE not supported, using polling');
                updateConnectionStatus('polling');
                // Fallback to polling if SSE not supported
                setInterval(refreshData, 5000);
            }
        }
        
        function updateConnectionStatus(status) {
            const dot = $('#status-dot');
            const statusText = $('#connection-status');
            
            dot.removeClass('connected reconnecting');
            
            switch(status) {
                case 'connected':
                    dot.addClass('connected');
                    statusText.text('Realtime: Terhubung');
                    break;
                case 'reconnecting':
                    dot.addClass('reconnecting');
                    statusText.text('Realtime: Menghubungkan Kembali');
                    break;
                case 'disconnected':
                    statusText.text('Realtime: Terputus');
                    break;
                case 'polling':
                    statusText.text('Polling: 5 detik');
                    break;
            }
        }
        
        function updateLastUpdated() {
            const now = new Date();
            const timeStr = now.toLocaleTimeString();
            $('#last-updated').text(`Update: ${timeStr}`);
        }
        
        function updateDashboard(data) {
            // Update status
            if (data.status) {
                $('#botStatus').text(data.status);
                if (data.status.includes('Aktif')) {
                    $('#botStatus').removeClass('badge-danger badge-warning').addClass('badge-success');
                    $('#statusIcon').text('AKTIF');
                } else {
                    $('#botStatus').removeClass('badge-success badge-warning').addClass('badge-danger');
                    $('#statusIcon').text('NONAKTIF');
                }
            }
            
            // Update price
            if (data.latest_price) {
                $('#currentPrice').text(data.latest_price.toFixed(4));
            }
            
            // Update profit
            if (data.profit !== undefined) {
                $('#totalProfit').text(data.profit.toFixed(4));
                if (data.profit > 0) {
                    $('#totalProfit').addClass('profit').removeClass('loss');
                } else if (data.profit < 0) {
                    $('#totalProfit').addClass('loss').removeClass('profit');
                }
            }
            
            // Update chart if available
            if (data.chart) {
                Plotly.react('priceChart', JSON.parse(data.chart));
            }
            
            // Update trades table
            if (data.trades) {
                updateTradesTable(data.trades);
            }
            
            // Update grid levels
            if (data.grid_levels) {
                updateGridLevels(data.grid_levels);
            }
        }
        
        // Update data secara periodik (fallback jika SSE tidak berfungsi)
        $(document).ready(function() {
            // Coba koneksi SSE
            connectSSE();
            
            // Tetap jalankan refresh data secara periodik sebagai fallback
            setInterval(function() {
                if (!eventSource || eventSource.readyState !== 1) {
                    refreshData();
                }
            }, 15000); // Cek setiap 15 detik
            
            // Set session keepalive
            setInterval(function() {
                $.get('/api/status');
            }, 300000); // 5 minutes
        });
        
        function refreshData() {
            // Update status bot
            $.getJSON('/api/status', function(data) {
                $('#botStatus').text(data.status);
                if (data.status.includes('Aktif')) {
                    $('#botStatus').removeClass('badge-danger badge-warning').addClass('badge-success');
                    $('#statusIcon').text('AKTIF');
                } else {
                    $('#botStatus').removeClass('badge-success badge-warning').addClass('badge-danger');
                    $('#statusIcon').text('NONAKTIF');
                }
                
                $('#currentPrice').text(data.latest_price ? data.latest_price.toFixed(4) : 'N/A');
                $('#totalProfit').text(data.profit ? data.profit.toFixed(4) : '0.0000');
                if (data.profit > 0) {
                    $('#totalProfit').addClass('profit').removeClass('loss');
                } else if (data.profit < 0) {
                    $('#totalProfit').addClass('loss').removeClass('profit');
                }
                
                // Update grid levels
                updateGridLevels(data.grid_levels);
                
                // Update last updated time
                updateLastUpdated();
                
            }).fail(function() {
                // Just try again later without redirecting
                console.error('Failed to fetch status data');
            });
            
            // Update grafik harga
            $.getJSON('/api/price_chart', function(data) {
                Plotly.react('priceChart', JSON.parse(data.chart));
            }).fail(function() {
                console.error('Failed to fetch chart data');
            });
            
            // Update riwayat trading
            $.getJSON('/api/trades', function(data) {
                updateTradesTable(data.trades);
            }).fail(function() {
                console.error('Failed to fetch trades data');
            });
        }
        
        function updateTradesTable(trades) {
            let tableBody = $('#tradesBody');
            tableBody.empty();
            
            if (trades && trades.length > 0) {
                // Ambil 10 trades terakhir
                const recentTrades = trades.slice(-10).reverse();
                
                recentTrades.forEach(function(trade) {
                    let time = new Date(trade.time).toLocaleString();
                    let profitClass = trade.profit > 0 ? 'profit' : (trade.profit < 0 ? 'loss' : '');
                    let profitText = trade.profit ? trade.profit.toFixed(4) + ' USDT' : '-';
                    
                    let row = `<tr>
                        <td>${time}</td>
                        <td>${trade.type}</td>
                        <td>${trade.price.toFixed(4)}</td>
                        <td>${trade.quantity}</td>
                        <td class="${profitClass}">${profitText}</td>
                    </tr>`;
                    
                    tableBody.append(row);
                });
            } else {
                tableBody.append('<tr><td colspan="5" class="text-center">Belum ada riwayat trading</td></tr>');
            }
        }
        
        function updateGridLevels(levels) {
            let gridContainer = $('#gridLevels');
            gridContainer.empty();
            
            if (levels && levels.length > 0) {
                // Jika hanya batas atas dan bawah yang tersedia
                if (levels.length === 2) {
                    let lowerPrice = levels[0];
                    let upperPrice = levels[1];
                    
                    // Buat grid level berdasarkan config di server
                    let gridConfig = 3; // Default 3 grid sesuai config.py
                    let gridSize = (upperPrice - lowerPrice) / gridConfig;
                    
                    for (let i = 0; i <= gridConfig; i++) {
                        let level = lowerPrice + (i * gridSize);
                        let card = `
                            <div class="col-md-2 mb-2">
                                <div class="card">
                                    <div class="card-body text-center">
                                        <h5>${level.toFixed(4)}</h5>
                                        <small>Level ${i+1}</small>
                                    </div>
                                </div>
                            </div>
                        `;
                        gridContainer.append(card);
                    }
                } else {
                    // Jika semua level grid tersedia
                    levels.forEach((level, index) => {
                        let card = `
                            <div class="col-md-2 mb-2">
                                <div class="card">
                                    <div class="card-body text-center">
                                        <h5>${level.toFixed(4)}</h5>
                                        <small>Level ${index+1}</small>
                                    </div>
                                </div>
                            </div>
                        `;
                        gridContainer.append(card);
                    });
                }
            } else {
                // Tampilkan pesan jika tidak ada grid levels
                // Selain itu, coba dapatkan dari file log secara manual
                $.getJSON('/api/status', function(data) {
                    if (data.grid_levels && data.grid_levels.length > 0) {
                        updateGridLevels(data.grid_levels);
                    } else {
                        gridContainer.append('<div class="col-12 text-center">Belum ada level grid yang tersedia. Periksa log bot untuk informasi.</div>');
                    }
                }).fail(function() {
                    gridContainer.append('<div class="col-12 text-center">Gagal mendapatkan informasi grid.</div>');
                });
            }
        }
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