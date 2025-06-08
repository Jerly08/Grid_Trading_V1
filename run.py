import sys
import threading
import time
import logging
import subprocess
import os
from grid_bot import GridTradingBot
from dashboard import run_dashboard
from auto_balancer import AutoBalancer
from auto_config import auto_configure  # Import fungsi auto_configure

# Konfigurasi logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def run_auto_balancer(safe_mode=True):
    """Jalankan auto balancer untuk menyeimbangkan aset"""
    try:
        logger.info("Menjalankan Auto Balancer untuk menyeimbangkan portfolio...")
        balancer = AutoBalancer()
        result = balancer.execute_auto_balance(safe_mode=safe_mode)
        if result:
            logger.info("Auto Balancer selesai dijalankan")
        else:
            logger.warning("Auto Balancer tidak melakukan perubahan")
        return result
    except Exception as e:
        logger.error(f"Error dalam Auto Balancer: {e}")
        return False

def run_bot(with_auto_balance=False):
    """Jalankan bot trading grid"""
    try:
        # Jalankan auto balancer hanya jika with_auto_balance=True
        if with_auto_balance:
            run_auto_balancer(safe_mode=False)
            # Tunggu sebentar agar saldo terupdate di sistem
            time.sleep(5)
        
        # Jalankan bot trading
        bot = GridTradingBot()
        bot.run()
    except Exception as e:
        logger.error(f"Error dalam bot trading: {e}")

def run_dashboard_thread():
    """Jalankan dashboard web dalam thread terpisah"""
    try:
        run_dashboard()
    except Exception as e:
        logger.error(f"Error dalam dashboard: {e}")

def run_dashboard_production():
    """Jalankan dashboard web menggunakan production server (Gunicorn atau Waitress)"""
    try:
        # Cek operating system
        is_windows = os.name == 'nt'
        
        if is_windows:
            # Gunakan Waitress di Windows
            try:
                import waitress
                logger.info("Menggunakan Waitress production server (kompatibel dengan Windows)")
                
                # Import app dari wsgi
                from wsgi import app
                
                # Mulai waitress dengan function langsung
                import threading
                waitress_thread = threading.Thread(
                    target=waitress.serve,
                    args=(app,),
                    kwargs={'host': '0.0.0.0', 'port': 5000, '_quiet': True}
                )
                waitress_thread.daemon = True
                waitress_thread.start()
                
                logger.info("Dashboard production server berhasil dimulai di http://localhost:5000")
                logger.info("Username: admin")
                logger.info("Password: Grid@Trading123")
                return True
                
            except ImportError:
                logger.warning("Waitress tidak ditemukan, jalankan 'pip install waitress' terlebih dahulu")
                return False
                
        else:
            # Gunakan Gunicorn di Linux/Mac
            try:
                import gunicorn
                logger.info("Menggunakan Gunicorn production server")
            except ImportError:
                logger.warning("Gunicorn tidak ditemukan, jalankan 'pip install gunicorn' terlebih dahulu")
                return False
                
            # Jalankan Gunicorn sebagai subprocess
            cmd = [
                "gunicorn", 
                "--bind", "0.0.0.0:5000", 
                "--workers", "4", 
                "--timeout", "120",
                "wsgi:app"
            ]
                
            logger.info(f"Menjalankan dashboard dengan command: {' '.join(cmd)}")
            process = subprocess.Popen(cmd)
            
            logger.info("Dashboard production server berhasil dimulai di http://localhost:5000")
            logger.info("Username: admin")
            logger.info("Password: Grid@Trading123")
            return True
            
    except Exception as e:
        logger.error(f"Error menjalankan dashboard production: {e}")
        return False

def main():
    """Fungsi utama untuk menjalankan bot dan dashboard"""
    # Parse command line arguments
    mode = "both"
    production = False
    disable_sse = False
    auto_config = False  # Tambahkan flag untuk auto-config
    with_auto_balance = False  # Tambahkan flag untuk Auto Balancer
    
    # Parse arguments
    for arg in sys.argv[1:]:
        if arg.lower() in ["bot", "dashboard", "both", "auto-config", "balance"]:  # Tambahkan opsi balance
            mode = arg.lower()
        elif arg.lower() in ["--production", "-p"]:
            production = True
        elif arg.lower() == "--disable-sse":
            disable_sse = True
        elif arg.lower() in ["--with-balance", "--balancer"]:  # Support kedua flag
            with_auto_balance = True
    
    # Set environment variable untuk disable SSE jika diminta
    if disable_sse:
        os.environ["DISABLE_SSE"] = "true"
        logger.info("Server-Sent Events (SSE) dinonaktifkan, menggunakan polling")
    
    if mode == "auto-config":  # Tambahkan handler untuk mode auto-config
        # Jalankan proses auto-config
        logger.info("Menjalankan Auto-Configure untuk menyesuaikan konfigurasi bot...")
        result = auto_configure()
        if result:
            logger.info("Auto-Configure berhasil. Konfigurasi bot telah diperbarui.")
        else:
            logger.warning("Auto-Configure tidak selesai atau dibatalkan.")
        return
    
    if mode == "balance":  # Mode khusus untuk Auto Balancer
        logger.info("Menjalankan Auto Balancer sebagai mode independen")
        run_auto_balancer(safe_mode=False)
        return
    
    # Jika flag --balancer diaktifkan dan mode tidak "balance",
    # kita akan menjalankan auto balancer terlebih dahulu
    if with_auto_balance and mode != "balance":
        logger.info("Menjalankan Auto Balancer sebelum mode utama...")
        run_auto_balancer(safe_mode=False)
        # Tunggu sebentar agar balance terupdate
        time.sleep(5)
        # Reset flag karena kita sudah menjalankan auto balancer secara eksplisit
        with_auto_balance = False
    
    if mode == "bot":
        # Hanya jalankan bot
        logger.info("Menjalankan bot trading")
        run_bot(with_auto_balance)
    elif mode == "dashboard":
        # Hanya jalankan dashboard
        logger.info("Menjalankan dashboard tanpa bot trading")
        if production:
            run_dashboard_production()
        else:
            run_dashboard_thread()
    else:
        # Jalankan keduanya
        logger.info("Menjalankan bot trading dan dashboard")
        
        # Jalankan dashboard
        dashboard_success = False
        if production:
            dashboard_success = run_dashboard_production()
        
        # Jika production dashboard gagal atau mode dev, gunakan thread
        if not production or not dashboard_success:
            dashboard_thread = threading.Thread(target=run_dashboard_thread)
            dashboard_thread.daemon = True
            dashboard_thread.start()
            logger.info("Dashboard development server berhasil dimulai di http://localhost:5000")
            logger.info("Username: admin")
            logger.info("Password: Grid@Trading123")
        
        # Jalankan bot dalam thread utama
        time.sleep(2)  # Tunggu dashboard dimulai
        run_bot(with_auto_balance)

if __name__ == "__main__":
    main() 