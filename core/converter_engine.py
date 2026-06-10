import os
import gc
import cv2
import time
import multiprocessing
import psutil
import math
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

def calculate_optimal_threads(ram_per_worker_mb: int = 350) -> int:
    """Calcula cuántos hilos podemos usar de forma segura basándose en 
    la Memoria RAM libre en este milisegundo y los núcleos físicos del CPU."""
    # Obtenermos la cantidad de nucleos fisicos
    total_cores = multiprocessing.cpu_count()

    # Obtenemos la ram disponible en MB 
    available_ram_mb = psutil.virtual_memory().available / (1024 * 1024)

    # Dejamos 1 GB disponible para windos y la UI
    safe_ram_mb = available_ram_mb - 1024
    
    if safe_ram_mb <= 0: # <- Si solo queda 1 GB de ram
        return 1 # <- Retornamos un worker unicamente (la ram esta saturada)
    
    # Calculamos cuantas fotos teoricas caben en la ram disponible
    max_threads_by_ram =int(math.floor(safe_ram_mb / ram_per_worker_mb))

    # Obtenemos el numero minimo viable, ya sea que lo limite la ram o los nucleos
    optimal_threads = min(total_cores, max_threads_by_ram)

    # Dejamos libre 1 procesador si es que ya tenemos mas de 4 nucleos asignados (con 4 va super bien la conversion)
    if optimal_threads > 4:
        optimal_threads -= 1

    return max(1, optimal_threads)

def wait_for_resources(check_cancel_func, process_resume, alert_func, safe_margin_mb: int = 500, timeout_secs: int =120) -> None:
    """Pausa el hilo actual si la RAM de la PC cae por debajo del margen seguro, actua como un semáforo dinámico"""
    waited_time = 0
    alert_triggered = False

    while True:
        if check_cancel_func():
            return False

        # Condicion ideal - la memoria ram es suficiente para procesar y convertir datos
        available_mb = psutil.virtual_memory().available / (1024 * 1024)
        if available_mb > safe_margin_mb:
            if alert_triggered:
                process_resume(True)
                logger.info("Recursos liberados. Reanuando proceso.")
            return True
        
        if waited_time >= timeout_secs and not alert_triggered:
            error_msg = "MEMORIA RAM SATURADA.\nCIERRE OTRAS APLICACIONES PARA LIBERAR RECURSOS Y REANUDAR EL PROCESO."
            logger.warning(error_msg)
            alert_func(error_msg)
            alert_triggered = True
        
        # Si la RAM es crítica, el hilo se duerme 1 segundo.
        time.sleep(1.0)

        if not alert_triggered:
            waited_time += 1

class ProxyWorkerSignals(QtCore.QObject):
    finished = QtCore.pyqtSignal(int, str)
    error = QtCore.pyqtSignal(int, str, str)
    resource_warning = QtCore.pyqtSignal(str)
    process_resume = QtCore.pyqtSignal(bool)

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
        if self.check_cancel():
            return

        try:
            ext = os.path.splitext(self.original_path)[1].lower()
            base_name = os.path.basename(self.original_path)
            name_no_ext = os.path.splitext(base_name)[0]
            
            proxy_path = os.path.join(self.temp_dir, f"{name_no_ext}.jpg")

            # PROCESO CR2 inspirado de xnconvert
            if ext == '.cr2':
                if not RAWPY_AVAILABLE:
                    raise ImportError("Librería rawpy no instalada.")
                
                alert_callback = lambda msg: self.signals.resource_warning.emit(msg)
                process_resume = lambda state: self.signals.process_resume.emit(state)
                if not wait_for_resources(self.check_cancel, alert_callback, process_resume, safe_margin_mb=500, timeout_secs=120): #<- Filtro de seguridad para calcular los recursos disponibles al moemnto
                    return
                
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        # verificacion de cancelacion por si tardo o volvio a verificar una segunda ocacion
                        if self.check_cancel():
                            return

                        with rawpy.imread(self.original_path) as raw:
                            # Configuración de Revelado 
                            rgb = raw.postprocess(
                                use_camera_wb=True,                                 # Respeta el balance de blancos de la cámara
                                half_size=False,                                    # Mantiene la resolusion completa
                                no_auto_bright=True,                                # APAGA el auto-brillo (Evita que el papel se queme o se lave)
                                demosaic_algorithm=rawpy.DemosaicAlgorithm.LINEAR,  # Elimina las "Escaleras" que se generan en las letras sin saturar la ram
                                output_color=rawpy.ColorSpace.sRGB                  # Espacio de color estandar
                            ) 
                            pil_img = Image.fromarray(rgb)
                            
                            # Maxima calidad posible para evitar perdidas
                            pil_img.save(proxy_path, 'JPEG', quality=100, subsampling=0)
                            
                            del pil_img
                            del rgb
                            gc.collect()
                        break
                    
                    except Exception as e:
                        if attempt < max_retries - 1:
                            logger.warning(f"Reintentando {base_name}...")
                            time.sleep(0.5)
                        else:
                            raise e

            # PROCESO TIFF (Calidad Premium 100% Resolución) solucion estilo XnConvert
            elif ext in ['.tif', '.tiff']:
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        # Verificacion de cancelamiento
                        if self.check_cancel():
                            return
                        
                        alert_callback = lambda msg: self.signals.resource_warning.emit(msg)
                        process_resume = lambda state: self.signals.process_resume.emit(state)
                        if not wait_for_resources(self.check_cancel, alert_callback, process_resume, safe_margin_mb=500, timeout_secs=120): #<- Filtro de seguridad para calcular los recursos disponibles al moemnto
                            return
                        
                        img = cv2.imread(self.original_path)
                        if img is None: 
                            raise ValueError("Matriz tiff nula o archivo corrupto")
                        
                        success = cv2.imwrite(proxy_path, img, [int(cv2.IMWRITE_JPEG_QUALITY), 100])
                        if not success:
                            raise IOError("Error de I/O al escribir JPG")
                        
                        del img
                        gc.collect()
                        break
                    
                    except Exception as e:
                        if attempt < max_retries - 1:
                            logger.warning(f"Reintentando {base_name}...")
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
    system_alert = QtCore.pyqtSignal(str)
    process_resume = QtCore.pyqtSignal(bool)
    
    def __init__(self):
        super().__init__()
        self.pool = QtCore.QThreadPool()
        self.pool.setMaxThreadCount(1)

        self._temp_vault = tempfile.TemporaryDirectory(prefix="ImageCutter_Proxies_")
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
        self.is_cancelled = False # Reiniciamos banderin por si cancelaron y luego empiezan un nuevo lote

        safe_threads = calculate_optimal_threads(ram_per_worker_mb=350)
        self.pool.setMaxThreadCount(safe_threads)
        logger.info(f"Nucleos asignados al convertidor: {safe_threads}")

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
                worker.signals.resource_warning.connect(self._show_os_notification)
                worker.signals.process_resume.connect(self._quit_os_notification)
                self.pool.start(worker)
            else:
                self._final_list[i] = file_path
                self._completed_files += 1

        if self._workers_dispatched == 0:
            self.finished.emit(self._final_list)
            return
        
        self.progress.emit(0, self._workers_dispatched, "Analizando imagenes...")

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
        
        msg = f"Convirtiendo imagen: {self._workers_finished}/{self._workers_dispatched}\n\nTiempo estimado restante: {eta_str}\n\n{os.path.basename(proxy_path)}"
        self.progress.emit(self._workers_finished, self._workers_dispatched, msg)
        
        self._check_if_done()

    def _on_worker_error(self, index: int, orig_path: str, error_msg: str):
        logger.warning(f"Omitiendo imagen para {orig_path} debido a un error: {error_msg}")
        self._final_list[index] = "" 
        self._workers_finished += 1
        self._completed_files += 1
        
        self.progress.emit(self._workers_finished, self._workers_dispatched, f"Error en {os.path.basename(orig_path)}")
        self._check_if_done()

    def _check_if_done(self):
        if self._completed_files == self._total_files:
            clean_list = [p for p in self._final_list if p != ""]
            self.finished.emit(clean_list)

    def _show_os_notification(self, msg: str):
        '''Le mandamos aviso a main de la saturacion en la memoria'''
        self.progress.emit(self._workers_finished, self._workers_dispatched, f"\t⚠️ PROCESO PAUSADO ⚠️\n\n{msg}")
        self.system_alert.emit(msg)

    def _quit_os_notification(self, state: bool):
        '''Mandamos notificacion de que el proceso ha sido restaurado'''
        self.process_resume.emit(state)
