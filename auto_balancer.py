import logging
import time
import math  # Tambahkan import math untuk pembulatan
from binance.exceptions import BinanceAPIException
import config
from binance_client import BinanceClient

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

class AutoBalancer:
    """
    Kelas untuk menyeimbangkan aset secara otomatis.
    Fungsi utama: 
    1. Membeli base asset (ADA) dengan USDT yang tersedia untuk memastikan bot grid trading bisa memasang sell orders.
    2. Menjual base asset (ADA) menjadi USDT untuk memastikan cukup USDT untuk buy orders.
    """
    def __init__(self):
        self.client = BinanceClient()
        self.symbol = config.SYMBOL
        self.base_asset = self.symbol.replace('USDT', '')
        self.quote_asset = 'USDT'
        
    def check_balance_needed(self):
        """
        Memeriksa kebutuhan balance untuk grid trading dan
        menentukan apakah perlu membeli base asset atau menjual base asset.
        
        Return:
            - dict dengan keys:
              - need_adjustment_type (str): 'buy_base', 'sell_base', atau 'none'
              - free_usdt (float): Jumlah USDT yang tersedia
              - free_base_asset (float): Jumlah base asset (ADA) yang tersedia
              - needed_base_asset (float): Jumlah base asset yang dibutuhkan (untuk sell orders)
              - needed_usdt (float): Jumlah USDT yang dibutuhkan (untuk buy orders)
              - base_asset_price (float): Harga base asset (ADA) saat ini
        """
        result = {
            'need_adjustment_type': 'none',  # bisa 'buy_base', 'sell_base', atau 'none'
            'free_usdt': 0,
            'free_base_asset': 0,
            'needed_base_asset': 0,
            'needed_usdt': 0,
            'base_asset_price': 0
        }
        
        try:
            # Dapatkan balance USDT dan ADA
            quote_balance = self.client.get_account_balance(self.quote_asset)
            base_balance = self.client.get_account_balance(self.base_asset)
            
            if not quote_balance or not base_balance:
                logger.error("Gagal mendapatkan data balance")
                return result
                
            free_usdt = float(quote_balance['free'])
            free_base = float(base_balance['free'])
            
            # Simpan ke result
            result['free_usdt'] = free_usdt
            result['free_base_asset'] = free_base
            
            # Dapatkan harga saat ini
            current_price = self.client.get_symbol_price(self.symbol)
            if not current_price:
                logger.error("Gagal mendapatkan harga saat ini")
                return result
                
            result['base_asset_price'] = current_price
                
            # Cek kebutuhan untuk grid trading
            # Bot perlu minimal 3x quantity untuk menempatkan 3 sell orders
            needed_base_asset = config.QUANTITY * 3
            result['needed_base_asset'] = needed_base_asset
            
            # Bot perlu minimal dana untuk 3x buy orders
            needed_usdt = config.QUANTITY * current_price * 3
            result['needed_usdt'] = needed_usdt
            
            # Tentukan apakah kita perlu buy atau sell
            # Case 1: ADA rendah tapi USDT cukup -> Buy ADA
            if free_base < needed_base_asset and free_usdt > 10:  # Minimal 10 USDT tersedia
                result['need_adjustment_type'] = 'buy_base'
                
            # Case 2: USDT rendah tapi ADA berlebih -> Sell ADA  
            elif free_usdt < needed_usdt and free_base > needed_base_asset + 10:  # Pastikan tetap ada ADA untuk sell orders + buffer
                result['need_adjustment_type'] = 'sell_base'
                
            return result
                
        except Exception as e:
            logger.error(f"Error saat memeriksa balance: {e}")
            return result
    
    def _sell_base_for_quote(self, quantity_to_sell, current_price=None):
        """
        Fungsi bantuan untuk menjual base asset (ADA) untuk mendapatkan USDT.
        
        Args:
            quantity_to_sell (float): Jumlah ADA yang akan dijual
            current_price (float, optional): Harga ADA saat ini
            
        Returns:
            bool: True jika berhasil, False jika gagal
        """
        if current_price is None:
            current_price = self.client.get_symbol_price(self.symbol)
            if not current_price:
                logger.error("Gagal mendapatkan harga saat ini")
                return False
        
        # Format quantity sesuai aturan LOT_SIZE
        base_to_sell_raw = quantity_to_sell
        base_to_sell = self.client.format_quantity(self.symbol, quantity_to_sell)
        
        # Konversi kembali ke float untuk perbandingan
        base_to_sell_float = float(base_to_sell)
        
        logger.info(f"--- AUTO BALANCER: SELLING {self.base_asset} ---")
        logger.info(f"Selling {base_to_sell} {self.base_asset} at price {current_price} (expected: {base_to_sell_float * current_price:.4f} USDT)")
        logger.info(f"Original quantity before LOT_SIZE adjustment: {base_to_sell_raw}, after adjustment: {base_to_sell}")
        
        try:
            result = self.client.client.create_order(
                symbol=self.symbol,
                side="SELL",
                type="MARKET",
                quantity=base_to_sell
            )
            
            logger.info(f"AUTO BALANCER - Market sell berhasil: {result}")
            logger.info(f"Tunggu 5 detik untuk memastikan order terekam di sistem...")
            time.sleep(5)  # Tunggu beberapa saat agar balance terbarukan
            
            # Cek balance setelah penjualan
            new_usdt_balance = self.client.get_account_balance(self.quote_asset)
            logger.info(f"Balance USDT sekarang: {new_usdt_balance['free']} (free) + {new_usdt_balance['locked']} (locked)")
            
            return True
            
        except BinanceAPIException as e:
            logger.error(f"ERROR AUTO BALANCER - Gagal menjual {self.base_asset}: {e}")
            # Penanganan error untuk LOT_SIZE seperti yang sudah ada
            if "LOT_SIZE" in str(e):
                # Kode penanganan LOT_SIZE error seperti yang sudah ada
                # ...
                pass
            return False
            
    def execute_auto_balance(self, safe_mode=True, required_for_grid=None):
        """
        Mengeksekusi auto-balancing portfolio untuk grid trading.
        
        Args:
            safe_mode (bool): Jika True, hanya gunakan sebagian aset untuk transaksi
                             Jika False, gunakan lebih banyak aset yang tersedia
            required_for_grid (dict, optional): Dictionary dengan kebutuhan grid trading:
                - required_usdt: Jumlah USDT yang dibutuhkan untuk grid trading
                - required_ada: Jumlah ADA yang dibutuhkan untuk grid trading
        
        Return:
            bool: True jika berhasil, False jika gagal
        """
        try:
            # Dapatkan saldo saat ini
            base_balance = self.client.get_account_balance(self.base_asset)
            quote_balance = self.client.get_account_balance(self.quote_asset)
            
            if not base_balance or not quote_balance:
                logger.error("Gagal mendapatkan informasi saldo")
                return False
            
            # Dapatkan harga terbaru
            current_price = self.client.get_symbol_price(self.symbol)
            if not current_price:
                logger.error("Gagal mendapatkan harga terkini")
                return False
            
            # Hitung saldo yang tersedia (free)
            ada_free = base_balance['free']
            usdt_free = quote_balance['free']
            
            logger.info(f"Free {self.base_asset}: {ada_free}, Free {self.quote_asset}: {usdt_free}")
            
            # Jika required_for_grid diberikan, cek kebutuhan USDT untuk grid
            if required_for_grid:
                required_usdt = required_for_grid.get('required_usdt', 0)
                required_ada = required_for_grid.get('required_ada', 0)
                
                logger.info(f"Kebutuhan untuk grid trading: {required_usdt:.4f} USDT dan {required_ada:.4f} ADA")
                
                # Cek apakah USDT cukup untuk grid trading
                usdt_shortfall = required_usdt - usdt_free
                
                if usdt_shortfall > 2.0:  # Minimal shortfall 2 USDT untuk menghindari konversi kecil
                    logger.info(f"Needed {self.quote_asset}: {required_usdt:.4f}, Shortfall: {usdt_shortfall:.4f}")
                    
                    # Hitung berapa ADA yang perlu dijual (tambahkan buffer 5%)
                    ada_to_sell = (usdt_shortfall / current_price) * 1.05
                    ada_to_sell = math.ceil(ada_to_sell)  # Bulatkan ke atas untuk memastikan cukup
                    
                    # Cek apakah ada cukup ADA untuk dijual dan tetap menyisakan untuk grid
                    if ada_free - ada_to_sell >= required_ada:
                        logger.info(f"Selling {ada_to_sell} {self.base_asset} at price {current_price} (expected: {ada_to_sell * current_price:.4f} {self.quote_asset})")
                        
                        if not safe_mode:
                            return self._sell_base_for_quote(ada_to_sell, current_price)
                        else:
                            logger.info(f"[SIMULASI] Menjual {ada_to_sell} {self.base_asset} untuk mendapatkan {ada_to_sell * current_price:.4f} {self.quote_asset}")
                            return True
                    else:
                        logger.warning(f"Tidak cukup {self.base_asset} untuk penyeimbangan dan kebutuhan grid")
                        return False
                elif usdt_shortfall > 0:
                    logger.info(f"USDT shortfall ({usdt_shortfall:.4f}) terlalu kecil untuk penyeimbangan")
                else:
                    logger.info(f"USDT sudah cukup untuk grid trading")
            
            # Jika tidak ada required_for_grid, gunakan check_balance_needed normal
            balance_check = self.check_balance_needed()
            
            if balance_check['need_adjustment_type'] == 'none':
                logger.info("Tidak perlu penyeimbangan aset")
                return True
                
            free_usdt = balance_check['free_usdt']
            free_base = balance_check['free_base_asset']
            needed_base_asset = balance_check['needed_base_asset']
            needed_usdt = balance_check['needed_usdt']
            current_price = balance_check['base_asset_price']
            
            # ------ CASE 1: PEMBELIAN BASE ASSET (ADA) -------
            if balance_check['need_adjustment_type'] == 'buy_base':
                # Hitung jumlah USDT yang akan digunakan
                usdt_needed = (needed_base_asset - free_base) * current_price * 1.01  # Tambah 1% untuk slippage
                
                # Dalam safe mode, maksimal gunakan 50% dari USDT free
                if safe_mode:
                    usdt_to_use = min(usdt_needed, free_usdt * 0.5) 
                else:
                    usdt_to_use = min(usdt_needed, free_usdt * 0.9)  # Sisakan 10% buffer
                    
                # PERBAIKAN: Pembulatan usdt_to_use ke 2 desimal untuk mengatasi error presisi
                usdt_to_use = round(usdt_to_use, 2)
                    
                # Hitungan final quantity yang akan dibeli
                final_quantity = int((usdt_to_use / current_price) * 100) / 100.0
                
                if final_quantity < 5:  # Terlalu kecil, kemungkinan di bawah minimum
                    logger.warning(f"Quantity terlalu kecil ({final_quantity} {self.base_asset})")
                    return False
                    
                # Log rencana aksi
                logger.info(f"--- AUTO BALANCER ACTIVE ---")
                logger.info(f"Free USDT: {free_usdt}, Needed {self.base_asset}: {needed_base_asset}")
                logger.info(f"Buying {final_quantity} {self.base_asset} at price {current_price} ({usdt_to_use} USDT)")
                
                # Eksekusi pembelian Market
                try:
                    # Coba dengan quoteOrderQty dulu (jumlah USDT yang digunakan)
                    try:
                        result = self.client.client.create_order(
                            symbol=self.symbol,
                            side="BUY",
                            type="MARKET",
                            quoteOrderQty=usdt_to_use
                        )
                    except BinanceAPIException as e:
                        if "too much precision" in str(e):
                            # Jika error presisi, gunakan quantity sebagai gantinya
                            # Bulatkan ke bawah untuk memastikan tidak melebihi saldo
                            # dan formatkan quantity sesuai aturan Binance
                            adjusted_quantity = self.client.format_quantity(self.symbol, final_quantity)
                            logger.info(f"Switching to quantity-based order: {adjusted_quantity} {self.base_asset}")
                            
                            result = self.client.client.create_order(
                                symbol=self.symbol,
                                side="BUY",
                                type="MARKET",
                                quantity=adjusted_quantity
                            )
                        else:
                            # Jika error lain, raise kembali
                            raise e
                    
                    logger.info(f"AUTO BALANCER - Market buy berhasil: {result}")
                    logger.info(f"Tunggu 5 detik untuk memastikan order terekam di sistem...")
                    time.sleep(5)  # Tunggu beberapa saat agar balance terbarukan
                    
                    # Cek balance setelah pembelian
                    new_balance = self.client.get_account_balance(self.base_asset)
                    logger.info(f"Balance {self.base_asset} sekarang: {new_balance['free']} (free) + {new_balance['locked']} (locked)")
                    
                    return True
                    
                except BinanceAPIException as e:
                    logger.error(f"ERROR AUTO BALANCER - Gagal membeli {self.base_asset}: {e}")
                    return False
            
            # ------ CASE 2: PENJUALAN BASE ASSET (ADA) -------
            elif balance_check['need_adjustment_type'] == 'sell_base':
                # Hitung berapa banyak base asset yang bisa dijual
                # Pastikan tetap menyisakan cukup untuk 3 sell orders + buffer (10)
                excess_base_asset = free_base - (needed_base_asset + 10)
                
                # Hitung berapa banyak USDT yang kita butuhkan
                usdt_shortfall = needed_usdt - free_usdt
                
                # Hitung berapa banyak base asset yang perlu dijual untuk mendapatkan USDT yang dibutuhkan
                # Tambah 1% untuk slippage
                base_to_sell_for_usdt = (usdt_shortfall * 1.01) / current_price
                
                # Dalam safe mode, jual lebih sedikit
                if safe_mode:
                    base_to_sell = min(excess_base_asset * 0.5, base_to_sell_for_usdt)
                else:
                    base_to_sell = min(excess_base_asset * 0.9, base_to_sell_for_usdt)
                
                return self._sell_base_for_quote(base_to_sell, current_price)
                
        except Exception as e:
            logger.error(f"Error dalam auto balancing: {e}")
            return False

# Untuk testing standalone
if __name__ == "__main__":
    balancer = AutoBalancer()
    balancer.execute_auto_balance(safe_mode=False) 