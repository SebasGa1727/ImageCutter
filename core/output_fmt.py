import os
import cv2
import numpy as np
from PIL import Image
from utils.fmt_config import config_manager
from utils.logger import setup_logger

logger = setup_logger(__name__)

def _calculate_proportional_size(orig_w: int, orig_h: int, target_size: int, anchor: str) -> tuple[int, int]:
    """
    Calcula las nuevas dimensiones manteniendo la proporción (Aspect Ratio).
    
    Args:
        orig_w: Ancho original.
        orig_h: Alto original.
        target_size: El tamaño en píxeles que queremos alcanzar.
        anchor: 'longest_edge' (lado mayor) o 'shortest_edge' (lado menor).
    """
    '''Calculamos el ratio para transformar la imagen de forma correcta 
    con respecto al lado corto o lado largo'''
    if anchor == "longest_edge":
        max_side = max(orig_w, orig_h)
        if max_side == 0:
            return orig_w, orig_h
        ratio = target_size / float(max_side)
    
    elif anchor == "shortest_edge":
        min_side = min(orig_w, orig_h)
        if min_side == 0:
            return orig_w, orig_h
        ratio = target_size / float(min_side)
    
    else:
        raise ValueError("El ancla (anchor) tiene que ser 'longest_edge' o 'shortest_edge'")
    
    new_w = int(round(orig_w * ratio))
    new_h = int(round(orig_h * ratio))

    return new_w, new_h


def _cv2_to_pil(cv_img: np.ndarray) -> Image.Image:
    """Convierte una matriz BGR de OpenCV a un objeto Image de Pillow (RGB)."""
    if cv_img.ndim == 3 and cv_img.shape[2] == 3:
        # OpenCV usa BGR, Pillow usa RGB. Debemos invertir los canales de color.
        rgb_img = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
    else:
        rgb_img = cv_img
    
    return Image.fromarray(rgb_img)

def export_image(cv_image: np.ndarray, base_filename: str, parent_folder_name: str = "") -> str:
    """Exporta la imagen recortada según la configuración."""
    try:
        #Leemos la configuracion de nuestro archivo
        fmt = str(config_manager.get("export_image", "format"))
        quality = config_manager.get("export_image", "quality")
        dpi = config_manager.get("export_image", "dpi")
        target_size = config_manager.get("export_image", "longest_edge")
        base_dir = config_manager.get("paths", "last_dir")
        sub_folder = config_manager.get("export_image", "output_dir")

        if not base_dir:
            base_dir = os.path.join(os.path.expanduser("~"), "Documents", "HICutter_Exports")
        
        #insertamos el nombre de la carpeta de donde se extrajeron las imagenes
        if parent_folder_name:
            base_dir = os.path.join(base_dir, parent_folder_name)

        out_dir = os.path.join(base_dir, sub_folder)
        os.makedirs(out_dir, exist_ok=True)

        # Convertimos a pillow y calculamos el tamaño
        pil_img = _cv2_to_pil(cv_image)
        orig_w , orig_h = pil_img.size

        new_w , new_h = _calculate_proportional_size(orig_w, orig_h, target_size, "longest_edge")

        # Redimensionamos usando un filtro de alta calidad (LANCZOS)
        # Solo redimensionamos si la imagen original es más grande que el target
        if orig_w > target_size or orig_h > target_size:
            pil_img = pil_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        else:
            logger.warning(f"Archivo no reescalado, la imagen es mas pequeña que el 'target_size':{base_filename}")

        # Construimos la salida
        name, _ = os.path.splitext(os.path.basename(base_filename))
        out_path = os.path.join(out_dir, f"{name}.{fmt}")

        #Guardamos variable "JPEG" para que pillow no crashee
        pil_format = fmt.upper()
        if pil_format == "JPG":
            pil_format = "JPEG"

        # Guardamos inyectando los metadatos (DPI y Calidad)
        pil_img.save(out_path, format=pil_format, quality=quality, dpi=(dpi, dpi))

        logger.info(f"Imagen exportada con exito: {out_path} ({new_w} x {new_h} a {dpi} DPI)")

        return out_path
    
    except Exception as e:
        logger.error(f"Error critico al intentar exportar imagen recortada: {base_filename}", exc_info=True)
        raise e
    
def export_th(cv_image: np.ndarray, base_filename: str, parent_folder_name: str = "") -> str:
    """Exporta la imagen en formato Thumbnail, según la configuración."""
    try:
        #Leemos la configuracion de nuestro archivo
        fmt = str(config_manager.get("export_th", "format"))
        quality = config_manager.get("export_th", "quality")
        dpi = config_manager.get("export_th", "dpi")
        target_size = config_manager.get("export_th", "shortest_edge")
        base_dir = config_manager.get("paths", "last_dir")

        if not base_dir:
            base_dir = os.path.join(os.path.expanduser("~"), "Documents", "HICutter_Exports")
        
        #insertamos el nombre de la carpeta de donde se extrajeron las imagenes
        if parent_folder_name:
            base_dir = os.path.join(base_dir, parent_folder_name)
        os.makedirs(base_dir, exist_ok=True)

        # Convertimos a pillow y calculamos el tamaño
        pil_img = _cv2_to_pil(cv_image)
        orig_w , orig_h = pil_img.size

        new_w , new_h = _calculate_proportional_size(orig_w, orig_h, target_size, "shortest_edge")

        # Redimensionamos usando un filtro de alta calidad (LANCZOS)
        # Solo redimensionamos si la imagen original es más grande que el target
        if orig_w > target_size or orig_h > target_size:
            pil_img = pil_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        else:
            logger.warning(f"Archivo no reescalado, la imagen es mas pequeña que el 'target_size' (th):{base_filename}")

        # Construimos la salida
        name, _ = os.path.splitext(os.path.basename(base_filename))
        out_path = os.path.join(base_dir, f"{name}_TH.{fmt}")
        
        #Guardamos variable "JPEG" para que pillow no crashee
        pil_format = fmt.upper()
        if pil_format == "JPG":
            pil_format = "JPEG"                

        # Guardamos inyectando los metadatos (DPI y Calidad)
        pil_img.save(out_path, format=pil_format, quality=quality, dpi=(dpi, dpi))

        logger.info(f"TH Exportado con exito: {out_path} ({new_w} x {new_h} a {dpi} DPI)")

        return out_path
    
    except Exception as e:
        logger.error(f"Error critico al intentar exportar TH: {base_filename}", exc_info=True)
        raise e
   