import logging
import os
from logging.handlers import RotatingFileHandler

def setup_logger(name: str) -> logging.Logger:
    """
    Configura y devuelve una instancia de Logger estandarizada para ImageCutter.
    
    Se utiliza el patrón Singleton inherente del módulo logging de Python: 
    llamar a logging.getLogger(name) múltiples veces con el mismo nombre 
    devolverá la misma instancia.
    
    Args:
        name (str): El nombre del módulo que solicita el logger (usualmente __name__).
        
    Returns:
        logging.Logger: Instancia configurada lista para emitir eventos.
    """
    
    # 1. Creación del Logger
    logger = logging.getLogger(name)
    
    # Evitar que los mensajes se propaguen al logger raíz (evita duplicidad en consola)
    logger.propagate = False

    # Si el logger ya tiene manejadores configurados, lo retornamos directamente.
    # Esto previene que se añadan múltiples manejadores si la función se llama varias veces.
    if logger.handlers:
        return logger

    # Establecer el nivel base. DEBUG captura todo; se puede elevar a INFO en producción.
    logger.setLevel(logging.DEBUG)

    # 2. Creación de Formatters
    # Formato detallado: Fecha/Hora - Nombre del Logger - Nivel - Archivo:Línea - Mensaje
    file_formatter = logging.Formatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Formato simplificado para la consola para facilitar la lectura rápida durante el desarrollo
    console_formatter = logging.Formatter(
        fmt='%(levelname)s - %(name)s - %(message)s'
    )

    # 3. Creación y configuración de Handlers
    
    # a) Manejador de Consola (StreamHandler)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG) # Mostrará todo en consola durante el desarrollo
    console_handler.setFormatter(console_formatter)

    # b) Manejador de Archivo Rotativo (RotatingFileHandler)
    # Se asegura de que el directorio 'logs' exista en la raíz del proyecto
    log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')
    os.makedirs(log_dir, exist_ok=True)
    
    log_file_path = os.path.join(log_dir, 'ImageCutter_app.log')
    
    # maxBytes=5242880 (5 MB): Cuando el archivo alcance 5MB, se renombra a .log.1
    # backupCount=3: Mantiene un historial de los últimos 3 archivos (15MB en total máximo)
    # encoding='utf-8': Crucial para registrar caracteres especiales sin excepciones Unicode
    file_handler = RotatingFileHandler(
        filename=log_file_path, 
        maxBytes=5 * 1024 * 1024, 
        backupCount=3, 
        encoding='utf-8'
    )
    # Solo registrar advertencias, errores y fallos críticos en el archivo para no saturarlo
    file_handler.setLevel(logging.WARNING) 
    file_handler.setFormatter(file_formatter)

    # 4. Asignación de Handlers al Logger
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger