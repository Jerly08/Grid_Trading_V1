import logging
import time
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
            
    def execute_auto_balance(self, safe_mode=True):
        """
        Mengeksekusi auto-balancing portfolio untuk grid trading.
        
        Args:
            safe_mode (bool): Jika True, hanya gunakan sebagian aset untuk transaksi
                             Jika False, gunakan lebih banyak aset yang tersedia
        
        Return:
            bool: True jika berhasil, False jika gagal
        """
        try:
            # Cek apakah kita perlu penyeimbangan
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
                
                # PERBAIKAN: Gunakan format_quantity untuk memastikan jumlah sesuai dengan aturan LOT_SIZE Binance
                base_to_sell_raw = base_to_sell
                base_to_sell = self.client.format_quantity(self.symbol, base_to_sell)
                
                # Konversi kembali ke float untuk perbandingan
                base_to_sell_float = float(base_to_sell)
                
                if base_to_sell_float < 5:  # Terlalu kecil, kemungkinan di bawah minimum
                    logger.warning(f"Quantity untuk dijual terlalu kecil ({base_to_sell} {self.base_asset})")
                    return False
                
                # Log rencana aksi
                logger.info(f"--- AUTO BALANCER ACTIVE (SELLING) ---")
                logger.info(f"Free {self.base_asset}: {free_base}, Free USDT: {free_usdt}")
                logger.info(f"Needed USDT: {needed_usdt}, Shortfall: {usdt_shortfall}")
                logger.info(f"Selling {base_to_sell} {self.base_asset} at price {current_price} (expected: {base_to_sell_float * current_price} USDT)")
                logger.info(f"Original quantity before LOT_SIZE adjustment: {base_to_sell_raw}, after adjustment: {base_to_sell}")
                
                # Eksekusi penjualan Market
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
                    # Tambahkan informasi lebih detail untuk debugging
                    if "LOT_SIZE" in str(e):
                        # Coba dapatkan informasi LOT_SIZE yang benar dari exchange info
                        lot_size_info = None
                        if self.symbol in self.client.exchange_info:
                            for filter_data in self.client.exchange_info[self.symbol]['filters']:
                                if filter_data['filterType'] == 'LOT_SIZE':
                                    lot_size_info = filter_data
                                    break
                        
                        logger.error(f"LOT_SIZE error details - Symbol: {self.symbol}, Quantity: {base_to_sell}")
                        if lot_size_info:
                            logger.error(f"LOT_SIZE filter: minQty={lot_size_info['minQty']}, maxQty={lot_size_info['maxQty']}, stepSize={lot_size_info['stepSize']}")
                            
                            # Coba lagi dengan quantity yang disesuaikan dengan stepSize
                            try:
                                step_size = float(lot_size_info['stepSize'])
                                min_qty = float(lot_size_info['minQty'])
                                
                                # Bulatkan ke bawah ke kelipatan stepSize terdekat
                                adjusted_qty = int(base_to_sell_float / step_size) * step_size
                                adjusted_qty = max(adjusted_qty, min_qty)  # Pastikan minimal minQty
                                
                                # Format dengan precision yang benar
                                adjusted_qty_str = self.client.format_quantity(self.symbol, adjusted_qty)
                                
                                logger.info(f"Mencoba lagi dengan quantity yang disesuaikan: {adjusted_qty_str}")
                                
                                result = self.client.client.create_order(
                                    symbol=self.symbol,
                                    side="SELL",
                                    type="MARKET",
                                    quantity=adjusted_qty_str
                                )
                                
                                logger.info(f"AUTO BALANCER - Market sell berhasil dengan quantity yang disesuaikan: {result}")
                                logger.info(f"Tunggu 5 detik untuk memastikan order terekam di sistem...")
                                time.sleep(5)
                                
                                # Cek balance setelah penjualan
                                new_usdt_balance = self.client.get_account_balance(self.quote_asset)
                                logger.info(f"Balance USDT sekarang: {new_usdt_balance['free']} (free) + {new_usdt_balance['locked']} (locked)")
                                
                                return True
                                
                            except BinanceAPIException as retry_e:
                                logger.error(f"Percobaan kedua juga gagal: {retry_e}")
                                return False
                    return False
                
        except Exception as e:
            logger.error(f"Error dalam auto balancing: {e}")
            return False

# Untuk testing standalone
if __name__ == "__main__":
    balancer = AutoBalancer()
    balancer.execute_auto_balance(safe_mode=False) 