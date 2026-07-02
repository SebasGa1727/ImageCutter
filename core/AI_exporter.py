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
    Extrae la imagen optimizada (1024px) y calcula el Bounding Box Orientado normalizado (YOLO-OBB).
    Guarda ambos archivos (.jpg y .txt) en la bóveda oculta.
    """
    try:
        images_dataset_dir = os.path.join(_get_hidden_dataset_dir(), "images")
        if not os.path.exists(images_dataset_dir):
            os.makedirs(images_dataset_dir, exist_ok=True)

        txt_dataset_dir = os.path.join(_get_hidden_dataset_dir(), "labels")
        if not os.path.exists(txt_dataset_dir):
            os.makedirs(txt_dataset_dir, exist_ok=True)
        
        # Limpiamos el nombre base para generar los archivos emparejados
        name_no_ext = os.path.splitext(os.path.basename(base_filename))[0]
        txt_path = os.path.join(txt_dataset_dir, f"{name_no_ext}.txt")
        img_path = os.path.join(images_dataset_dir, f"{name_no_ext}.jpg")

        img_h, img_w = cv_image.shape[:2]
        
        # --- 1. MATEMÁTICA YOLO (Cajas Orientadas)---
        # points es una matriz (4, 2). Creamos una copia en float64 para evitar truncamientos
        norm_points = points.copy().astype(np.float64)
        
        # Normalizamos dividiendo las X (columna 0) entre el ancho y las Y (columna 1) entre el alto
        norm_points[:, 0] = norm_points[:, 0] / img_w
        norm_points[:, 1] = norm_points[:, 1] / img_h
        
        # Aplanamos la matriz a un vector de 1 dimensión: [x1, y1, x2, y2, x3, y3, x4, y4]
        flat_coords = norm_points.flatten()
        
        # Formateamos a 6 decimales separados por espacios
        coords_str = " ".join([f"{val:.6f}" for val in flat_coords])
        yolo_line = f"{class_id} {coords_str}\n"
        
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write(yolo_line)
            
        # --- 2. EXTRACCIÓN DE LA FOTO (manteniendo proporcion) ---
        # Se calcula la propocion  para que el lado mas largo sea 1024px
        max_edge = 1024
        if max(img_w, img_h) > max_edge:
            ratio = max_edge / float(max(img_w, img_h))
            new_w = int(round(img_w * ratio))
            new_h = int(round(img_h * ratio))
            img_optimized = cv2.resize(cv_image, (new_w, new_h), interpolation=cv2.INTER_AREA)
        else:
            # Si la imagen ya es pequeña, no la escalamos para no pixelarla
            img_optimized = cv_image
        cv2.imwrite(img_path, img_optimized, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
            
        logger.info(f"IA info Generado exitosamente: {name_no_ext}")
        return True
        
    except Exception:
        logger.error("Error al generar los datos de IA", exc_info=True)
        return False