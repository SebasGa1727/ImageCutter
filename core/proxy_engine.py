import os
import gc
import cv2
import time
try:
    import rawpy
    RAWPY_AVAILABLE = True
except ImportError:
    RAWPY_AVAILABLE = False
import tempfile
from PyQt6 import QtCore
from PIL import Image
from utils.logger import setup_logger

logger = setup_logger(__name__)

class ProxyWorkerSignals(QtCore.QObject):
    finished = QtCore.pyqtSignal(int, str)
    error = QtCore.pyqtSignal(int, str, str)

class ProxyWorker(QtCore.QRunnable):
    def __init__(self, original_path: str, temp_dir: str, index: int, check_cancel_func):
        super().__init__()
        self.original_path = original_path
        self.temp_dir = temp_dir
        self.index = index
        self.check_cancel = check_cancel_func
        self.signals = ProxyWorkerSignals()

    @QtCore.pyqtSlot()
    def run(self):
        #Verificamos si el proceso ha sido cancelado o no
        if self.check_cancel:
            return

        try:
            ext = os.path.splitext(self.original_path)[1].lower()
            base_name = os.path.basename(self.original_path)
            name_no_ext = os.path.splitext(base_name)[0]
            
            proxy_path = os.path.join(self.temp_dir, f"{name_no_ext}.jpg")

            # PROCESO CR2   
            if ext == '.cr2':
                if not RAWPY_AVAILABLE:
                    raise ImportError("Librería rawpy no instalada.")
                
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        # verificacion de cancelacion por si tardo o volvio a verificar una segunda ocacion
                        if self.check_cancel:
                            return
                        
                        with rawpy.imread(self.original_path) as raw:
                            # Configuración de Revelado de Grado Profesional
                            rgb = raw.postprocess(
                                use_camera_wb=True,                                 # Respeta el balance de blancos de la cámara
                                no_auto_bright=True,                                # APAGA el auto-brillo (Evita que el papel se queme o se lave)
                                exp_shift=7.0,                                      # "Perilla" para subir la luz de forma limpia 
                                noise_thr=450.0,                                    # Destructor de "confeti"- Valores altos (ej. 500) eliminan el confeti de colores sin borrar las letras.
                                highlight_mode=rawpy.HighlightMode.Blend,           # Mezcla canales para recuperar texto en zonas brillantes
                                output_color=rawpy.ColorSpace.sRGB,                 # Fuerza el estándar web/pantalla
                                gamma=(2.222, 4.5),                                 # Aplica curva gamma humana natural
                                demosaic_algorithm=rawpy.DemosaicAlgorithm.AAHD     # Elimina las "Escaleras" que se generan en las letras
                            ) 
                            pil_img = Image.fromarray(rgb)
                            
                            # Calidad 90% 
                            pil_img.save(proxy_path, 'JPEG', quality=90)
                            
                            del pil_img
                            del rgb
                            gc.collect()
                        break
                    
                    except Exception as e:
                        if attempt < max_retries - 1:
                            logger.warning(f"Bloqueo I/O en {base_name}. Reintentando en 0.5s...")
                            time.sleep(0.5)
                        else:
                            raise e

            # PROCESO TIFF (Calidad Premium 100% Resolución)
            elif ext in ['.tif', '.tiff']:
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        # Verificacion de cancelamiento
                        if self.check_cancel():
                            return
                        
                        img = cv2.imread(self.original_path)
                        if img is None:
                            raise ValueError("OpenCV devolvió una matriz nula al leer el TIFF")
                        
                        if img.ndim == 3 and img.shape[2] == 3:
                            rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                        elif img.ndim == 4:
                            rgb_img = cv2.cvtColor(img, cv2.COLOR_BGRA2RGB)
                        else:
                            rgb_img = img
                        
                        pil_img = Image.fromarray(rgb_img)
                        
                        # Guardamos calidad al 95%
                        pil_img.save(proxy_path, 'JPEG', quality=90)
                        
                        del pil_img
                        del rgb_img
                        del img
                        gc.collect()
                        break
                    
                    except Exception as e:
                        if attempt < max_retries - 1:
                            logger.warning(f"Bloqueo I/O en {base_name}. Reintentando en 0.5s...")
                            time.sleep(0.5)
                        else:
                            raise e
            # Solo avisa que terminó si nadie lo canceló
            if not self.check_cancel():
                self.signals.finished.emit(self.index, proxy_path)

        except Exception as e:
            logger.error(f"Fallo definitivo en proxy para {self.original_path}", exc_info=True)
            self.signals.error.emit(self.index, self.original_path, str(e))

class ProxyManager(QtCore.QObject):
    progress = QtCore.pyqtSignal(int, int, str) 
    finished = QtCore.pyqtSignal(list)          
    error = QtCore.pyqtSignal(str)              
    
    def __init__(self):
        super().__init__()
        self.pool = QtCore.QThreadPool()
        self.pool.setMaxThreadCount(1) 
        self._temp_vault = tempfile.TemporaryDirectory(prefix="HICutter_Proxies_")
        self.is_cancelled = False
        
        self._total_files = 0
        self._completed_files = 0
        self._final_list: list[str] = []
        self._workers_dispatched = 0
        self._workers_finished = 0
        self.start_time = 0.0

    def cancel(self):
        '''Metodo publico para cancelar el proceso'''
        self.is_cancelled = True
        self.pool.clear() # Borra todos los "Workers" que esten en cola

    def process_directory(self, input_dir: str):
        self.is_cancelled = True # Reiniciamos banderin por si cancelaron y luego empiezan un nuevo lote
        valid_exts = {'.jpg', '.jpeg', '.png', '.bmp', '.tif', '.tiff', '.cr2'}
        heavy_exts = {'.tif', '.tiff', '.cr2'} 
        
        if not os.path.isdir(input_dir):
            self.error.emit("Carpeta no válida.")
            return

        all_files = []
        for file in os.listdir(input_dir):
            if os.path.splitext(file)[1].lower() in valid_exts:
                all_files.append(os.path.join(input_dir, file))
                
        self._total_files = len(all_files)
        if self._total_files == 0:
            self.finished.emit([]) 
            return
            
        self._final_list = ["" for _ in range(self._total_files)]
        self._completed_files = 0
        self._workers_dispatched = 0
        self._workers_finished = 0
        self.start_time = time.perf_counter()

        for i, file_path in enumerate(all_files):
            ext = os.path.splitext(file_path)[1].lower()
            if ext in heavy_exts:
                self._workers_dispatched += 1
                worker = ProxyWorker(file_path, self._temp_vault.name, i, lambda: self.is_cancelled)
                worker.signals.finished.connect(self._on_worker_finished)
                worker.signals.error.connect(self._on_worker_error)
                self.pool.start(worker)
            else:
                self._final_list[i] = file_path
                self._completed_files += 1

        if self._workers_dispatched == 0:
            self.finished.emit(self._final_list)
            return
        
        self.progress.emit(0, self._workers_dispatched, "Analizando bóveda de proxies...")

    def _on_worker_finished(self, index: int, proxy_path: str):
        self._final_list[index] = proxy_path
        self._workers_finished += 1
        self._completed_files += 1

        #Calculo de ETA (tiempo estimado)
        elapsed = time.perf_counter() - self.start_time
        avg_time_per_photo = elapsed / self._workers_finished
        remaining_photos = self._workers_dispatched - self._workers_finished
        eta_seconds = avg_time_per_photo * remaining_photos
        #Formato amigable de tiempo
        if eta_seconds > 60:
            mins = int(eta_seconds // 60)
            secs = int(eta_seconds % 60)
            eta_str = f"{mins}m {secs}s"
        else:
            eta_str = f"{int(eta_seconds)}s"
        
        msg = f"Generando proxy {self._workers_finished}/{self._workers_dispatched}: {os.path.basename(proxy_path)}\n\nTiempo estimado restante: {eta_str}"
        self.progress.emit(self._workers_finished, self._workers_dispatched, msg)
        
        self._check_if_done()

    def _on_worker_error(self, index: int, orig_path: str, error_msg: str):
        logger.warning(f"Omitiendo proxy para {orig_path} debido a un error: {error_msg}")
        self._final_list[index] = "" 
        self._workers_finished += 1
        self._completed_files += 1
        
        self.progress.emit(self._workers_finished, self._workers_dispatched, f"Error en {os.path.basename(orig_path)}")
        self._check_if_done()

    def _check_if_done(self):
        if self._completed_files == self._total_files:
            clean_list = [p for p in self._final_list if p != ""]
            self.finished.emit(clean_list)