import os
import cv2
import numpy as np
from PyQt6 import QtCore
from core.processor import process_perspective_crop
from core.output_fmt import export_image
from utils.logger import setup_logger

logger = setup_logger(__name__)


# SEÑALES DEL OBRERO

# Los QRunnable no pueden emitir señales directamente, 
# necesitan un objeto QObject intermedio que hable por ellos.
class WorkerSignals(QtCore.QObject):
    finished = QtCore.pyqtSignal(str)          # Devuelve la ruta donde se guardó
    error = QtCore.pyqtSignal(str, str)        # Devuelve (nombre_archivo, mensaje_error)

# EL OBRERO (Se ejecuta en 2do Plano)
class BatchWorker(QtCore.QRunnable):
    """
    Hilo trabajador que recorta y exporta la imagen en segundo plano.
    No toca la interfaz gráfica (GUI) en absoluto.
    """
    def __init__(self, cv_image: np.ndarray, points: np.ndarray, file_name: str):
        super().__init__()
        self.cv_image = cv_image
        self.points = points
        self.file_name = file_name
        self.signals = WorkerSignals()

    @QtCore.pyqtSlot()
    def run(self):
        """Este método se ejecuta en un núcleo distinto del procesador"""
        try:
            # 1. Hacemos el recorte matemático pesado
            warped = process_perspective_crop(self.cv_image, self.points)
            
            # 2. Guardamos en disco duro (I/O intensivo)
            # Nota: output_fmt ya sabe dónde guardar gracias a que actualizamos el JSON en el diálogo
            out_path = export_image(warped, self.file_name)
            
            '''3. (Futuro) Aquí agregaremos la exportación a IA'''
            
            # Avisamos que terminamos exitosamente
            self.signals.finished.emit(out_path)
            
        except Exception as e:
            logger.error(f"Error en BatchWorker procesando {self.file_name}", exc_info=True)
            self.signals.error.emit(self.file_name, str(e))


class BatchManager(QtCore.QObject):
    # EL BatchManager = Maneja la lista de memoria RAM
    """Gestiona el estado del lote: qué archivos hay, cuál sigue, y cuántos faltan."""
    batch_finished = QtCore.pyqtSignal(list, list) # Emite (lista_exitos, lista_errores) al terminar todo
    
    def __init__(self):
        super().__init__()
        self.image_files: list[str] = []
        self.current_index: int = 0
        
        # Estadísticas para el resumen final
        self.success_list: list[str] = []
        self.error_list: list[tuple[str, str]] = []
        
        # Extensiones válidas
        self.valid_extensions = {'.jpg', '.jpeg', '.png', '.tif', '.tiff', '.bmp', '.cr2'}

    def load_directory(self, input_dir: str) -> bool:
        """Escanea la carpeta de entrada y crea la lista de trabajo"""
        self.image_files = []
        self.current_index = 0
        self.success_list = []
        self.error_list = []

        if not os.path.isdir(input_dir):
            return False

        for file in os.listdir(input_dir):
            ext = os.path.splitext(file)[1].lower()
            if ext in self.valid_extensions:
                self.image_files.append(os.path.join(input_dir, file))
        
        # Retorna True si encontró al menos 1 foto válida
        return len(self.image_files) > 0

    def get_next_image(self) -> str | None:
        """Devuelve la ruta de la siguiente foto y avanza el puntero. Si no hay más, devuelve None."""
        if self.current_index < len(self.image_files):
            next_file = self.image_files[self.current_index]
            self.current_index += 1
            return next_file
        return None

    def has_more_images(self) -> bool:
        """¿Quedan fotos por procesar?"""
        return self.current_index < len(self.image_files)

    # --- Callbacks para el Obrero ---
    def record_success(self, out_path: str):
        self.success_list.append(out_path)
        self._check_if_done()

    def record_error(self, file_name: str, error_msg: str):
        self.error_list.append((file_name, error_msg))
        self._check_if_done()

    def _check_if_done(self):
        """Si todos los obreros terminaron y ya no hay fotos, emitimos el final"""
        total_processed = len(self.success_list) + len(self.error_list)
        if total_processed == len(self.image_files):
            self.batch_finished.emit(self.success_list, self.error_list)