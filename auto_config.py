import logging
import time
import math
import os
from binance_client import BinanceClient
import config

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

class AutoConfig:
    """
    Kelas yang menangani konfigurasi otomatis bot grid trading
    berdasarkan modal yang tersedia dan kondisi pasar terkini.
    """
    
    def __init__(self, binance_client=None):
        """Inisialisasi dengan klien Binance"""
        self.client = binance_client if binance_client else BinanceClient()
        self.symbol = config.SYMBOL
        self.base_asset = self.symbol.replace('USDT', '')
        self.quote_asset = 'USDT'
        
        # Parameter default
        self.default_grid_width_percentage = 7.5  # Lebar grid default dalam persentase
        self.min_grid_number = 3                  # Minimal jumlah grid
        self.max_grid_number = 8                  # Maksimal jumlah grid
        self.volatility_factor = 1.5              # Faktor pengali untuk volatilitas
        
    def analyze_market_conditions(self):
        """
        Menganalisis kondisi pasar saat ini (harga, volatilitas)
        
        Return:
            dict: Informasi pasar termasuk harga saat ini dan volatilitas
        """
        market_info = {
            'current_price': 0,
            'volatility_24h': 0,
            'market_trend': 'sideways',  # sideways, bullish, bearish
            'suggested_grid_width': self.default_grid_width_percentage
        }
        
        try:
            # Dapatkan harga terkini
            current_price = self.client.get_symbol_price(self.symbol)
            if not current_price:
                logger.error("Gagal mendapatkan harga terkini")
                return market_info
                
            market_info['current_price'] = current_price
            
            # Dapatkan data klines untuk analisis volatilitas (24 jam terakhir)
            end_time = int(time.time() * 1000)  # Waktu saat ini dalam miliseconds
            start_time = end_time - (24 * 60 * 60 * 1000)  # 24 jam sebelumnya
            
            klines = self.client.client.get_klines(
                symbol=self.symbol,
                interval="1h",
                startTime=start_time,
                endTime=end_time
            )
            
            if not klines or len(klines) < 24:
                logger.warning("Data klines tidak cukup untuk analisis volatilitas")
                return market_info
            
            # Hitung volatilitas sebagai persentase pergerakan harga
            high_prices = [float(kline[2]) for kline in klines]  # High price
            low_prices = [float(kline[3]) for kline in klines]   # Low price
            close_prices = [float(kline[4]) for kline in klines] # Close price
            
            max_price = max(high_prices)
            min_price = min(low_prices)
            
            # Volatilitas dihitung sebagai (max-min)/min dalam persentase
            volatility = ((max_price - min_price) / min_price) * 100
            market_info['volatility_24h'] = volatility
            
            # Tentukan tren pasar berdasarkan perbandingan harga
            first_price = float(klines[0][4])  # Harga close 24 jam lalu
            last_price = float(klines[-1][4])  # Harga close terkini
            
            price_change = ((last_price - first_price) / first_price) * 100
            if price_change > 3:
                market_info['market_trend'] = 'bullish'
            elif price_change < -3:
                market_info['market_trend'] = 'bearish'
            
            # Sesuaikan lebar grid berdasarkan volatilitas
            # Semakin volatil pasar, semakin lebar grid sebaiknya
            suggested_width = max(5, min(15, volatility * self.volatility_factor))
            market_info['suggested_grid_width'] = suggested_width
            
            logger.info(f"Analisis pasar: Harga {current_price}, Volatilitas {volatility:.2f}%, Tren {market_info['market_trend']}")
            logger.info(f"Lebar grid yang disarankan: {suggested_width:.2f}%")
            
            return market_info
            
        except Exception as e:
            logger.error(f"Error saat menganalisis kondisi pasar: {e}")
            return market_info
    
    def analyze_available_capital(self):
        """
        Menganalisis modal yang tersedia untuk trading
        
        Return:
            dict: Informasi modal tersedia dan rekomendasi
        """
        capital_info = {
            'usdt_free': 0,
            'usdt_locked': 0,
            'base_free': 0,
            'base_locked': 0,
            'usdt_value': 0,
            'base_value_in_usdt': 0,
            'total_value': 0,
            'max_buy_orders': 0,
            'max_sell_orders': 0,
            'suggested_quantity': config.QUANTITY
        }
        
        try:
            # Dapatkan saldo saat ini
            quote_balance = self.client.get_account_balance(self.quote_asset)
            base_balance = self.client.get_account_balance(self.base_asset)
            current_price = self.client.get_symbol_price(self.symbol)
            
            if not quote_balance or not base_balance or not current_price:
                logger.error("Gagal mendapatkan informasi saldo atau harga")
                return capital_info
            
            # Isi informasi saldo
            capital_info['usdt_free'] = quote_balance['free']
            capital_info['usdt_locked'] = quote_balance['locked']
            capital_info['base_free'] = base_balance['free']
            capital_info['base_locked'] = base_balance['locked']
            
            # Hitung nilai dalam USDT
            capital_info['usdt_value'] = quote_balance['free'] + quote_balance['locked']
            capital_info['base_value_in_usdt'] = (base_balance['free'] + base_balance['locked']) * current_price
            capital_info['total_value'] = capital_info['usdt_value'] + capital_info['base_value_in_usdt']
            
            # Hitung maksimum order yang dapat ditempatkan
            # Misalnya, untuk order jual, kita perlu base asset (ADA)
            # Untuk order beli, kita perlu quote asset (USDT)
            
            # Berapa banyak order beli yang dapat ditempatkan
            # Asumsikan setiap order membutuhkan QUANTITY * current_price USDT
            order_cost = config.QUANTITY * current_price
            safety_factor = 0.95  # Gunakan 95% dari saldo tersedia untuk keamanan
            
            max_buy_orders = math.floor((quote_balance['free'] * safety_factor) / order_cost)
            capital_info['max_buy_orders'] = max_buy_orders
            
            # Berapa banyak order jual yang dapat ditempatkan
            max_sell_orders = math.floor((base_balance['free'] * safety_factor) / config.QUANTITY)
            capital_info['max_sell_orders'] = max_sell_orders
            
            # Sarankan quantity berdasarkan modal
            # Jika modal terlalu kecil, kurangi quantity
            # Jika modal cukup besar, pertahankan atau tingkatkan
            
            ideal_grid_count = 6  # Jumlah grid ideal (3 buy + 3 sell)
            min_order_value = 10  # Minimal nilai order dalam USDT
            
            if capital_info['total_value'] < 100:
                # Modal kecil, kurangi quantity
                suggested_quantity = max(
                    math.floor(min_order_value / current_price),  # Minimal order value
                    math.floor((capital_info['total_value'] * 0.8) / (ideal_grid_count * current_price))  # 80% modal dibagi ideal_grid_count
                )
            elif capital_info['total_value'] > 500:
                # Modal besar, bisa meningkatkan quantity
                suggested_quantity = min(
                    50,  # Cap pada 50 ADA per order
                    math.floor((capital_info['total_value'] * 0.7) / (ideal_grid_count * current_price))
                )
            else:
                # Modal sedang, pertahankan atau sesuaikan sedikit
                suggested_quantity = config.QUANTITY
            
            # Pastikan quantity adalah bilangan bulat untuk ADAUSDT
            suggested_quantity = int(suggested_quantity)
            if suggested_quantity < 1:
                suggested_quantity = 1
                
            capital_info['suggested_quantity'] = suggested_quantity
            
            logger.info(f"Analisis modal: USDT {capital_info['usdt_value']:.2f}, " +
                       f"{self.base_asset} senilai {capital_info['base_value_in_usdt']:.2f} USDT")
            logger.info(f"Max buy orders: {max_buy_orders}, Max sell orders: {max_sell_orders}")
            logger.info(f"Quantity yang disarankan: {suggested_quantity} {self.base_asset}")
            
            return capital_info
            
        except Exception as e:
            logger.error(f"Error saat menganalisis modal tersedia: {e}")
            return capital_info
    
    def generate_optimal_config(self):
        """
        Menghasilkan konfigurasi optimal berdasarkan analisis pasar dan modal
        
        Return:
            dict: Konfigurasi optimal untuk bot trading
        """
        try:
            # Analisis kondisi pasar dan modal
            market_info = self.analyze_market_conditions()
            capital_info = self.analyze_available_capital()
            
            current_price = market_info['current_price']
            volatility = market_info['volatility_24h']
            
            # Tentukan parameter grid berdasarkan analisis
            
            # 1. Tentukan rentang harga berdasarkan volatilitas dan tren
            grid_width_percentage = market_info['suggested_grid_width']
            
            # Sesuaikan rentang berdasarkan tren pasar
            if market_info['market_trend'] == 'bullish':
                # Untuk pasar bullish, buat grid dengan bias ke atas
                lower_percentage = grid_width_percentage * 0.4  # 40% di bawah harga saat ini
                upper_percentage = grid_width_percentage * 0.6  # 60% di atas harga saat ini
            elif market_info['market_trend'] == 'bearish':
                # Untuk pasar bearish, buat grid dengan bias ke bawah
                lower_percentage = grid_width_percentage * 0.6  # 60% di bawah harga saat ini
                upper_percentage = grid_width_percentage * 0.4  # 40% di atas harga saat ini
            else:
                # Untuk pasar sideways, buat grid seimbang
                lower_percentage = grid_width_percentage * 0.5  # 50% di bawah harga saat ini
                upper_percentage = grid_width_percentage * 0.5  # 50% di atas harga saat ini
            
            # Hitung batas atas dan bawah grid
            lower_price = current_price * (1 - (lower_percentage / 100))
            upper_price = current_price * (1 + (upper_percentage / 100))
            
            # Bulatkan ke presisi harga yang sesuai
            price_precision = 4  # Untuk ADAUSDT
            lower_price = round(lower_price, price_precision)
            upper_price = round(upper_price, price_precision)
            
            # 2. Tentukan jumlah grid berdasarkan volatilitas dan modal
            # Semakin volatil pasar, semakin banyak grid yang diperlukan
            # Tapi jumlah grid juga dibatasi oleh modal yang tersedia
            
            volatility_factor = min(1.5, max(0.5, volatility / 10))  # Skala volatilitas ke 0.5-1.5
            base_grid_number = int(5 * volatility_factor)  # 5 grid sebagai dasar
            
            # Sesuaikan berdasarkan modal tersedia
            max_possible_grid = min(
                capital_info['max_buy_orders'],
                capital_info['max_sell_orders'],
                self.max_grid_number
            )
            
            # Tentukan jumlah grid final
            grid_number = min(max(base_grid_number, self.min_grid_number), max_possible_grid)
            if grid_number < 1:
                grid_number = self.min_grid_number  # Fallback ke minimum
            
            # 3. Tentukan quantity berdasarkan modal tersedia
            quantity = capital_info['suggested_quantity']
            
            # Buat konfigurasi optimal
            optimal_config = {
                'symbol': self.symbol,
                'upper_price': upper_price,
                'lower_price': lower_price,
                'grid_number': grid_number,
                'quantity': quantity,
                'max_investment': config.MAX_INVESTMENT,  # Gunakan nilai yang sudah ada
                'stop_loss_percentage': config.STOP_LOSS_PERCENTAGE  # Gunakan nilai yang sudah ada
            }
            
            # Tampilkan hasil konfigurasi optimal
            logger.info(f"==== KONFIGURASI OPTIMAL ====")
            logger.info(f"Symbol: {optimal_config['symbol']}")
            logger.info(f"Rentang harga: {optimal_config['lower_price']} - {optimal_config['upper_price']}")
            logger.info(f"Jumlah grid: {optimal_config['grid_number']}")
            logger.info(f"Quantity per order: {optimal_config['quantity']} {self.base_asset}")
            logger.info(f"Total modal yang dibutuhkan (approx): " +
                       f"{optimal_config['quantity'] * optimal_config['grid_number'] * current_price:.2f} USDT")
            logger.info(f"=============================")
            
            return optimal_config
            
        except Exception as e:
            logger.error(f"Error saat menghasilkan konfigurasi optimal: {e}")
            # Fallback ke konfigurasi default jika terjadi error
            return {
                'symbol': self.symbol,
                'upper_price': config.UPPER_PRICE,
                'lower_price': config.LOWER_PRICE,
                'grid_number': config.GRID_NUMBER,
                'quantity': config.QUANTITY,
                'max_investment': config.MAX_INVESTMENT,
                'stop_loss_percentage': config.STOP_LOSS_PERCENTAGE
            }
    
    def apply_configuration(self, optimal_config):
        """
        Menerapkan konfigurasi optimal ke file config.py
        
        Args:
            optimal_config (dict): Konfigurasi optimal dari generate_optimal_config()
            
        Return:
            bool: True jika berhasil, False jika gagal
        """
        try:
            # Baca file config.py saat ini
            with open('config.py', 'r') as file:
                config_content = file.readlines()
            
            # Perbarui nilai-nilai konfigurasi
            new_config_content = []
            for line in config_content:
                if line.strip().startswith('UPPER_PRICE ='):
                    new_config_content.append(f"UPPER_PRICE = {optimal_config['upper_price']}      # Auto-configured: Upper price boundary\n")
                elif line.strip().startswith('LOWER_PRICE ='):
                    new_config_content.append(f"LOWER_PRICE = {optimal_config['lower_price']}      # Auto-configured: Lower price boundary\n")
                elif line.strip().startswith('GRID_NUMBER ='):
                    new_config_content.append(f"GRID_NUMBER = {optimal_config['grid_number']}         # Auto-configured: Optimized grid number\n")
                elif line.strip().startswith('QUANTITY ='):
                    new_config_content.append(f"QUANTITY = {optimal_config['quantity']}           # Auto-configured: Optimized quantity\n")
                else:
                    new_config_content.append(line)
            
            # Simpan ke file baru terlebih dahulu untuk berjaga-jaga
            with open('config.py.new', 'w') as file:
                file.writelines(new_config_content)
            
            # Ganti file config.py yang asli
            os.replace('config.py.new', 'config.py')
            
            logger.info("Konfigurasi optimal berhasil diterapkan ke config.py")
            return True
            
        except Exception as e:
            logger.error(f"Error saat menerapkan konfigurasi: {e}")
            return False

# Fungsi utama untuk dijalankan langsung
def auto_configure():
    """
    Fungsi utama untuk melakukan konfigurasi otomatis
    
    Return:
        bool: True jika berhasil, False jika gagal
    """
    try:
        logger.info("Memulai proses Auto-Configure...")
        
        auto_config = AutoConfig()
        optimal_config = auto_config.generate_optimal_config()
        
        # Tanyakan konfirmasi ke pengguna
        print("\n==== KONFIGURASI OPTIMAL YANG DIHASILKAN ====")
        print(f"Symbol: {optimal_config['symbol']}")
        print(f"Rentang harga: {optimal_config['lower_price']} - {optimal_config['upper_price']}")
        print(f"Jumlah grid: {optimal_config['grid_number']}")
        print(f"Quantity per order: {optimal_config['quantity']} {optimal_config['symbol'].replace('USDT', '')}")
        print("==========================================\n")
        
        confirm = input("Terapkan konfigurasi ini? (y/n): ")
        
        if confirm.lower() == 'y':
            result = auto_config.apply_configuration(optimal_config)
            if result:
                print("Konfigurasi berhasil diterapkan. Silahkan restart bot Anda.")
                return True
            else:
                print("Gagal menerapkan konfigurasi.")
                return False
        else:
            print("Konfigurasi dibatalkan oleh pengguna.")
            return False
            
    except Exception as e:
        logger.error(f"Error dalam auto_configure: {e}")
        return False

# Jalankan jika dipanggil langsung
if __name__ == "__main__":
    auto_configure() 