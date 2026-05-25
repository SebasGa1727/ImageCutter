import os
import ctypes
import numpy as np
import cv2
from utils.logger import setup_logger

logger = setup_logger(__name__)

def _get_hidden_dataset_dir() -> str:
    """
    Calcula la raíz del programa, crea la carpeta y le inyecta el 
    atributo nativo de 'Carpeta Oculta' en Windows.
    """
    # 1. Obtenemos la raíz del programa (Subiendo un nivel desde la carpeta 'core')
    core_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(core_dir)
    
    # 2. Definimos el nombre de la bóveda (Con un punto para ocultar en Unix/Linux)
    dataset_dir = os.path.join(root_dir, ".ai_dataset")
    
    if not os.path.exists(dataset_dir):
        os.makedirs(dataset_dir)
        
        # 3. Magia de Windows: Modificamos los atributos del sistema de archivos
        if os.name == 'nt':
            FILE_ATTRIBUTE_HIDDEN = 0x02
            # Llamamos a la API del Kernel32 de Windows para ocultarla
            ret = ctypes.windll.kernel32.SetFileAttributesW(dataset_dir, FILE_ATTRIBUTE_HIDDEN)
            if not ret:
                logger.warning(f"No se pudo aplicar el atributo oculto a {dataset_dir}")
                
    return dataset_dir

def export_yolo_data(cv_image: np.ndarray, points: np.ndarray, base_filename: str, base_foldername:str, class_id: int = 0) -> bool:
    """
    Extrae la imagen ligera (640x640) y calcula el Bounding Box normalizado (YOLO).
    Guarda ambos archivos (.jpg y .txt) en la bóveda oculta.
    """
    try:
        dataset_dir = os.path.join(_get_hidden_dataset_dir(), base_foldername)
        if not os.path.exists(dataset_dir):
            os.makedirs(dataset_dir, exist_ok=True)
        
        # Limpiamos el nombre base para generar los archivos emparejados
        name_no_ext = os.path.splitext(os.path.basename(base_filename))[0]
        txt_path = os.path.join(dataset_dir, f"{name_no_ext}.txt")
        img_path = os.path.join(dataset_dir, f"{name_no_ext}.jpg")

        img_h, img_w = cv_image.shape[:2]
        
        # --- 1. MATEMÁTICA YOLO ---
        x_coords = points[:, 0]
        y_coords = points[:, 1]
        
        min_x, max_x = np.min(x_coords), np.max(x_coords)
        min_y, max_y = np.min(y_coords), np.max(y_coords)
        
        x_center = ((min_x + max_x) / 2.0) / img_w
        y_center = ((min_y + max_y) / 2.0) / img_h
        width = (max_x - min_x) / img_w
        height = (max_y - min_y) / img_h
        
        yolo_line = f"{class_id} {x_center:.6f} {y_center:.6f} {width:.6f} {height:.6f}\n"
        
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write(yolo_line)
            
        # --- 2. EXTRACCIÓN DE LA FOTO (manteniendo proporcion) ---
        # Se calcula la propocion  para que el lado mas largo dea 640px
        max_edge = 640
        ratio = max_edge / float(max(img_w, img_h))
        new_w = int(round(img_w * ratio))
        new_h = int(round(img_h * ratio))

        img_640 = cv2.resize(cv_image, (new_w, new_h), interpolation=cv2.INTER_AREA)
        cv2.imwrite(img_path, img_640, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
            
        logger.info(f"IA info Generado exitosamente: {name_no_ext}")
        return True
        
    except Exception:
        logger.error("Error al generar los datos ocultos para YOLO", exc_info=True)
        return False