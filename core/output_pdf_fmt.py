import os
import io
import img2pdf
from PIL import Image
from utils.fmt_config import config_manager
from utils.logger import setup_logger

logger = setup_logger(__name__)

def _img_stream_generator(image_paths: list[str], quality: int, dpi: int):
    '''Generador de flujo continuo'''
    for path in image_paths:
        try:
            with Image.open(path) as img: #<- Abrimos la imagen individualmente
                #Convertimos a RGB por si tiene canal alpha o BGR
                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")
                #preparamos el espacio de memoria exclusivo para esa imagen
                img_byte_arr = io.BytesIO()
                #Guardamos la imagen en ese espacio de memoria con la calidad y DPI previamente configurados
                img.save(img_byte_arr, format="JPEG", quality = quality, dpi = (dpi, dpi))

                #LE damos los  puros bytes para que img2pdf inyecte al disco duro
                yield img_byte_arr.getvalue()
        #Al estar en un bucle, la memoria borra los datos de esta imagen, liberando memoria sin saturarla
        except Exception as e:
            logger.error(f"Error al procesar la imagen {path} en PDF: {e}", exc_info=True)

def export_to_pdf(ordered_paths: list[str], output_filename: str) -> str:
    '''Toma la lista de imagenes, las compila y crea el pdf utilizando I/O Streming'''
    try:
        dpi = int(config_manager.get("export_pdf", "dpi")) or 150
        quality = int(config_manager.get("export_pdf", "quality")) or 75
        base_dir = config_manager.get("paths", "last_dir")
        
        if not base_dir:
            base_dir = os.path.join(os.path.expanduser("~"), "Documents", "ImageCutter_Exports")

        if output_filename:
            base_dir = os.path.join(base_dir, output_filename)

        os.makedirs(base_dir, exist_ok=True)

        out_path = os.path.join(base_dir, f"{output_filename}.pdf")
        #Evaluamos el generador en una lista
        compressed_images = list(_img_stream_generator(ordered_paths, quality, dpi))
        #Medida de seguridad y debuger
        if not compressed_images:
            raise ValueError("No se pudo procesar ninguna imagen a PDF")

        # ABRIMOS EL CANAL DIRECTO AL DISCO DURO (Modo wb = Write Binary)
        # Esto crea el archivo PDF vacío.
        logger.info(f"Iniciando escritura de PDF")
        with open(out_path, "wb") as pdf_file:
            #img2pdf procesa el generador e inyecta directamente al disco.
            pdf_bytes = img2pdf.convert(compressed_images)
            pdf_file.write(pdf_bytes)

        logger.info(f"PDF Generado exitosamente con: {len(ordered_paths)} paginas")
        return out_path
    except Exception as e:
        logger.error("Error critico al exportar PDF", exc_info=True)
        raise e
    
def export_individual_pdfs(image_paths: list[str], output_foldername: str) -> str:
    '''
    Genera un PDF independiente por cada imagen. 
    Altamente optimizado para RAM usando I/O streaming por archivo.
    '''
    dpi = int(config_manager.get("export_pdf", "dpi")) or 150
    quality = int(config_manager.get("export_pdf", "quality")) or 75
    base_dir = config_manager.get("paths", "last_dir")
    
    if not base_dir:
        base_dir = os.path.join(os.path.expanduser("~"), "Documents", "HICutter_PDF_Exports")

    # Creamos una subcarpeta para agrupar los PDFs individuales y no desordenar el equipo del usuario
    target_dir = os.path.join(base_dir, f"{output_foldername}_PDFs")
    os.makedirs(target_dir, exist_ok=True)

    for path in image_paths:
        try:
            # Extraemos el nombre original sin la extensión
            base_name = os.path.splitext(os.path.basename(path))[0]
            out_path = os.path.join(target_dir, f"{base_name}.pdf")
            
            with Image.open(path) as img:
                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")
                
                # Preparamos el buffer en RAM
                img_byte_arr = io.BytesIO()
                img.save(img_byte_arr, format="JPEG", quality=quality, dpi=(dpi, dpi))
                
                # img2pdf procesa el flujo en memoria
                pdf_bytes = img2pdf.convert(img_byte_arr.getvalue())
                
                # Escribimos el PDF en el disco
                with open(out_path, "wb") as pdf_file:
                    pdf_file.write(pdf_bytes)
                    
        except Exception as e:
            logger.error(f"Error al procesar la imagen {path} en PDF individual: {e}", exc_info=True)
            
    # Retornamos la carpeta contenedora para mostrársela al usuario en el mensaje de éxito
    return target_dir