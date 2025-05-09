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

# Konfigurasi security
DASHBOARD_USERNAME = os.getenv('DASHBOARD_USERNAME', 'admin')
DASHBOARD_PASSWORD = os.getenv('DASHBOARD_PASSWORD', 'Grid@Trading123')  # Default password
DASHBOARD_SECRET_KEY = os.getenv('DASHBOARD_SECRET_KEY', secrets.token_hex(32))

app = Flask(__name__)
app.secret_key = DASHBOARD_SECRET_KEY
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SECURE'] = True  # Aktifkan jika menggunakan HTTPS
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

# Tambahkan fallback price jika tidak ada data
FALLBACK_PRICE = 0.7800  # Harga ADA fallback jika tidak bisa mendapatkan data terkini

# Session tracking untuk keamanan
active_sessions = {}
MAX_FAILED_ATTEMPTS = 5
blocked_ips = {}

# Lock untuk thread safety
data_lock = Lock()

# SSE clients
sse_clients = set()

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
    """Decorator untuk halaman yang memerlukan login"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        
        # Verifikasi session ID
        user_id = session.get('user_id')
        if user_id not in active_sessions:
            session.clear()
            return redirect(url_for('login'))
        
        # Refresh session timestamp
        active_sessions[user_id]['last_activity'] = datetime.datetime.now()
        return f(*args, **kwargs)
    return decorated_function

def check_for_session_timeout():
    """Periksa session yang tidak aktif dan hapus"""
    while True:
        try:
            now = datetime.datetime.now()
            for user_id in list(active_sessions.keys()):
                last_activity = active_sessions[user_id]['last_activity']
                if (now - last_activity).total_seconds() > 3600:  # 1 jam timeout
                    del active_sessions[user_id]
                    logger.info(f"Session {user_id} expired due to inactivity")
        except Exception as e:
            logger.error(f"Error in session cleanup: {e}")
        time.sleep(300)  # Periksa setiap 5 menit

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        # Check if IP is blocked
        client_ip = request.remote_addr
        if client_ip in blocked_ips and blocked_ips[client_ip]['until'] > datetime.datetime.now():
            return render_template('login.html', error="IP blocked due to too many failed attempts")
        
        # Authenticate
        if username == DASHBOARD_USERNAME and password == DASHBOARD_PASSWORD:
            # Reset failed attempts
            if client_ip in blocked_ips:
                del blocked_ips[client_ip]
            
            # Create new session
            user_id = str(uuid.uuid4())
            session['user_id'] = user_id
            active_sessions[user_id] = {
                'username': username,
                'last_activity': datetime.datetime.now()
            }
            return redirect(url_for('index'))
        else:
            # Track failed attempts
            if client_ip not in blocked_ips:
                blocked_ips[client_ip] = {'attempts': 1, 'until': None}
            else:
                blocked_ips[client_ip]['attempts'] += 1
            
            # Block IP if too many failed attempts
            if blocked_ips[client_ip]['attempts'] >= MAX_FAILED_ATTEMPTS:
                blocked_ips[client_ip]['until'] = datetime.datetime.now() + datetime.timedelta(minutes=30)
                logger.warning(f"IP {client_ip} blocked for 30 minutes due to too many failed login attempts")
                error = "Too many failed attempts. IP blocked for 30 minutes."
            else:
                error = "Invalid username or password"
    
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    user_id = session.get('user_id')
    if user_id and user_id in active_sessions:
        del active_sessions[user_id]
    session.clear()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    """Halaman utama dashboard"""
    return render_template('index.html', 
                           bot_status=bot_status,
                           latest_price=latest_price,
                           bot_profit=bot_profit)

@app.route('/api/price_chart')
@login_required
def price_chart():
    """API endpoint untuk data grafik harga"""
    global price_history, latest_price
    
    # Jika tidak ada data price history, buat data dummy
    if not price_history and latest_price is not None:
        current_time = datetime.datetime.now()
        # Buat 5 titik data dummy untuk satu jam terakhir
        for i in range(5):
            # Variasi kecil untuk harga (±0.5%)
            price_var = latest_price * (1 + (random.random() - 0.5) * 0.01)
            time_point = current_time - datetime.timedelta(minutes=i*15)
            price_history.insert(0, {
                "time": time_point.strftime("%Y-%m-%d %H:%M:%S"),
                "price": price_var
            })
        logger.info("Created dummy price history for chart")
    
    # Jika masih tidak ada data history, gunakan fallback
    if not price_history:
        current_time = datetime.datetime.now()
        for i in range(5):
            time_point = current_time - datetime.timedelta(minutes=i*15)
            price_var = FALLBACK_PRICE * (1 + (random.random() - 0.5) * 0.01)
            price_history.insert(0, {
                "time": time_point.strftime("%Y-%m-%d %H:%M:%S"),
                "price": price_var
            })
        logger.warning("Using fallback price history for chart")
    
    # Membuat grafik harga menggunakan plotly
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
    
    # Konversi plotly figure ke JSON untuk dirender di browser
    graphJSON = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
    return jsonify(chart=graphJSON)

@app.route('/api/trades')
@login_required
def get_trades():
    """API endpoint untuk data history trading"""
    return jsonify(trades=trades_history)

@app.route('/api/status')
@login_required
def get_status():
    """API endpoint untuk status bot"""
    global latest_price
    
    # Reload data untuk mendapatkan harga terbaru
    load_bot_data()
    
    # Pastikan selalu ada nilai harga, gunakan fallback jika perlu
    if latest_price is None:
        latest_price = FALLBACK_PRICE
        logger.warning(f"Using fallback price: {FALLBACK_PRICE}")
    
    status_data = {
        "status": safe_emoji(bot_status),
        "latest_price": latest_price,
        "profit": bot_profit,
        "grid_levels": grid_levels
    }
    return jsonify(status_data)

@app.route('/stream')
@login_required
def stream():
    """Server-Sent Events endpoint untuk update realtime"""
    def event_stream():
        client_id = uuid.uuid4()
        client = {'id': client_id, 'queue': []}
        
        with data_lock:
            sse_clients.add(client)
        
        try:
            # Kirim data awal
            yield f"data: {json.dumps(get_initial_data())}\n\n"
            
            while True:
                # Cek jika koneksi masih ada
                if request.environ.get('werkzeug.server.shutdown'):
                    break
                
                # Periksa antrian pesan
                if client['queue']:
                    with data_lock:
                        while client['queue']:
                            yield client['queue'].pop(0)
                
                # Sleep untuk mencegah CPU usage tinggi
                time.sleep(0.5)
                
                # Kirim heartbeat setiap 15 detik untuk keep-alive
                yield f": heartbeat\n\n"
                
        except Exception as e:
            logger.error(f"SSE error: {e}")
        finally:
            with data_lock:
                if client in sse_clients:
                    sse_clients.remove(client)
    
    return Response(event_stream(), mimetype="text/event-stream")

def get_initial_data():
    """Dapatkan data awal untuk stream"""
    global latest_price
    
    # Pastikan selalu ada nilai harga
    if latest_price is None:
        latest_price = FALLBACK_PRICE
    
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
        "grid_levels": grid_levels
    }

def broadcast_update():
    """Broadcast update ke semua klien SSE"""
    with data_lock:
        if not sse_clients:
            return
            
        # Dapatkan data terbaru
        data = get_initial_data()
        
        # Buat pesan SSE
        message = f"data: {json.dumps(data)}\n\n"
        
        # Kirim pesan ke semua klien
        for client in list(sse_clients):
            try:
                client['queue'].append(message)
                logger.debug(f"Queued update for client {client['id']}")
            except Exception as e:
                logger.error(f"Error queuing message for client {client['id']}: {e}")
                if client in sse_clients:
                    sse_clients.remove(client)

def load_bot_data():
    """Load data dari file state bot"""
    global bot_status, latest_price, bot_profit, trades_history, grid_levels, price_history
    
    try:
        # Update price history dari log
        try:
            with open("bot.log", "r") as log_file:
                lines = log_file.readlines()
                price_data = []
                
                # Cari 100 entri harga terbaru
                for line in reversed(lines):
                    if "[PRICE UPDATE]" in line:
                        try:
                            parts = line.split("[PRICE UPDATE]")[1].strip().split("|")
                            if len(parts) >= 3:
                                symbol_price = parts[0].strip().split(":")
                                if len(symbol_price) == 2:
                                    symbol = symbol_price[0].strip()
                                    price = float(symbol_price[1].strip())
                                    timestamp = line.split(" - ")[0].strip()
                                    
                                    price_data.append({
                                        "time": timestamp,
                                        "price": price
                                    })
                                    
                                    # Hentikan jika sudah mendapatkan 100 data harga
                                    if len(price_data) >= 100:
                                        break
                        except Exception as e:
                            logger.debug(f"Gagal parsing baris log: {e}")
                            continue
                
                # Balik kembali urutan data untuk kronologis
                price_data.reverse()
                
                # Simpan data harga
                if price_data:
                    price_history = price_data
                    latest_price = price_data[-1]["price"]
                    logger.info(f"Loaded latest price from log: {latest_price}")
        except Exception as e:
            logger.error(f"Error reading log file: {e}")
        
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
                    # Tambahkan ke history
                    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    price_history.append({
                        "time": current_time,
                        "price": current_price
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
        
        # Load state bot
        state_files = [f for f in os.listdir(".") if f.startswith("grid_state_") and f.endswith(".json")]
        if state_files:
            latest_state_file = state_files[0]  # Ambil file pertama jika ada beberapa
            
            with open(latest_state_file, "r") as f:
                state = json.load(f)
                bot_profit = state.get("total_profit", 0)
                trades_history = state.get("trades", [])
                grid_levels = state.get("price_range", [])
                last_update = state.get("last_update")
                
                # Update bot status
                if last_update:
                    try:
                        last_update_time = datetime.datetime.fromisoformat(last_update)
                        time_diff = (datetime.datetime.now() - last_update_time).total_seconds()
                        if time_diff > 300:  # 5 menit
                            bot_status = "Tidak Aktif (5+ menit tanpa update)"
                        else:
                            bot_status = "Aktif"
                    except:
                        bot_status = "Status Tidak Diketahui"
                else:
                    bot_status = "Tidak Aktif"
                    
                # Update latest price jika ada di state dan lebih baru
                if "last_price" in state and state["last_price"] is not None:
                    state_price = float(state["last_price"])
                    state_time = last_update if last_update else datetime.datetime.now().isoformat()
                    
                    if latest_price is None:
                        latest_price = state_price
                        logger.info(f"Using price from state file: {latest_price}")
                        
                        # Tambahkan ke history jika kosong
                        if not price_history:
                            price_history.append({
                                "time": state_time,
                                "price": state_price
                            })
    except Exception as e:
        logger.error(f"Error loading bot data: {e}")

def update_data_thread():
    """Thread untuk update data secara periodik"""
    last_fetch_time = 0
    while True:
        current_time = time.time()
        
        # Batasi pembaruan menjadi maksimal setiap 3 detik
        if current_time - last_fetch_time >= 3:
            with data_lock:
                # Simpan waktu fetch
                last_fetch_time = current_time
                
                # Load data
                load_bot_data()
                
                # Jika masih tidak ada harga terkini, coba dapatkan langsung
                global latest_price
                if latest_price is None:
                    try:
                        # Coba dari instansi bot terlebih dahulu
                        try:
                            from grid_bot import GridTradingBot
                            if GridTradingBot.instance and hasattr(GridTradingBot.instance, 'last_price'):
                                latest_price = GridTradingBot.instance.last_price
                                logger.info(f"Got price directly from bot instance: {latest_price}")
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
                                if not price_history:
                                    price_history.append({
                                        "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                        "price": current_price
                                    })
                    except Exception as e:
                        logger.error(f"Thread update failed to get price: {e}")
            
            # Broadcast update ke semua klien setiap kali data diperbarui
            if sse_clients:
                broadcast_update()
                
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
            <a href="/logout" class="btn btn-outline-danger">Logout</a>
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
                // Redirect to login if authentication fails
                window.location.href = '/login';
            });
            
            // Update grafik harga
            $.getJSON('/api/price_chart', function(data) {
                Plotly.react('priceChart', JSON.parse(data.chart));
            }).fail(function() {
                // Redirect to login if authentication fails
                window.location.href = '/login';
            });
            
            // Update riwayat trading
            $.getJSON('/api/trades', function(data) {
                updateTradesTable(data.trades);
            }).fail(function() {
                // Redirect to login if authentication fails
                window.location.href = '/login';
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
                    
                    // Buat grid level estimasi
                    let gridCount = 5; // Asumsi 5 level grid
                    let gridSize = (upperPrice - lowerPrice) / gridCount;
                    
                    for (let i = 0; i <= gridCount; i++) {
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
                gridContainer.append('<div class="col-12 text-center">Belum ada level grid yang tersedia</div>');
            }
        }
    </script>
</body>
</html>
        """)

def run_dashboard():
    """Jalankan dashboard web"""
    # Buat templates jika belum ada
    create_templates()
    
    # Muat data bot
    load_bot_data()
    
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