import os
import sys
import threading
import time
import logging
from grid_bot import GridTradingBot
from dashboard import run_dashboard
import config

# Force simulation mode
os.environ['BINANCE_TESTNET'] = 'True'
config.SIMULATION_MODE = True

# Enhanced logging for simulation
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("simulation.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def run_simulation():
    """Jalankan bot trading grid dalam mode simulasi"""
    try:
        logger.info("=" * 50)
        logger.info("STARTING GRID TRADING BOT IN SIMULATION MODE")
        logger.info("=" * 50)
        logger.info(f"Symbol: {config.SYMBOL}")
        logger.info(f"Price Range: {config.LOWER_PRICE} - {config.UPPER_PRICE}")
        logger.info(f"Grid Levels: {config.GRID_NUMBER}")
        logger.info(f"Quantity: {config.QUANTITY}")
        logger.info("No real orders will be placed.")
        logger.info("=" * 50)
        
        bot = GridTradingBot()
        bot.run()
    except Exception as e:
        logger.error(f"Error dalam simulasi trading: {e}")

def run_dashboard_thread():
    """Jalankan dashboard web dalam thread terpisah"""
    try:
        run_dashboard()
    except Exception as e:
        logger.error(f"Error dalam dashboard: {e}")

def main():
    """Fungsi utama untuk menjalankan simulasi dan dashboard"""
    # Jalankan dashboard dalam thread terpisah
    dashboard_thread = threading.Thread(target=run_dashboard_thread)
    dashboard_thread.daemon = True
    dashboard_thread.start()
    
    logger.info("Dashboard berhasil dimulai di http://localhost:5000")
    logger.info("Username: admin")
    logger.info("Password: Grid@Trading123")
    
    # Jalankan bot dalam thread utama
    time.sleep(2)  # Tunggu dashboard dimulai
    run_simulation()

if __name__ == "__main__":
    main() 