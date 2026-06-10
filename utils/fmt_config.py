import json
import os
from typing import Dict, Any
from utils.logger import setup_logger

'''Gestor para leer y guardar configuraciones y preferencias de formato del usuario'''
logger = setup_logger(__name__)

class UserConfigManager:
    #Creamos el nombre del archivo
    CONFIG_FILE = "fmt_settings.json"

    #Creamos una configuracion default por si el usuario no los configura
    DEFAULT_CONFIG = {
        "export_image":{
            "format": "jpg",
            "quality": 80,
            "dpi": 96,
            "longest_edge": 3000,
            "output_dir": "Recortadas"
        },
        "export_th":{
            "format": "jpg",
            "quality": 60,
            "dpi": 72,
            "shortest_edge": 500,
        },
        "export_pdf":{
            "enabled": False,
            "dpi": 150,
            "quality": 75
        },
        "ai_export":{
            "yolo_enabled": False
        },
        "paths":{
            "use_preset_dir": False,
            "pre_set_output_dir": "",
            "last_dir": "",
            "input_last_dir": ""
        }
       
    }

    def __init__(self) -> None:
        
        self.config: Dict[str, Any] = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        #Carga el archivo JSON, si no existe, lo crea con la configuracion base
        if not os.path.exists(self.CONFIG_FILE):
            return self._create_default_config()
        
        #intentamos leer y decodificar el json
        try:
            with open(self.CONFIG_FILE, 'r', encoding='UTF-8') as file:
                data = json.load(file)
                data_backup = self.DEFAULT_CONFIG.copy()
                data_backup.update(data)
                return data_backup
        except Exception:
            logger.warning("Error al codificar json", exc_info=True)
            return self.DEFAULT_CONFIG.copy()
        
    def _create_default_config(self) -> Dict[str, Any]:
        '''Crea el archivo fisico en el disco con la configuracion predeterminada'''
        default_data = self.DEFAULT_CONFIG.copy()
        self._save_to_disk(default_data)
        return default_data
    
    def _save_to_disk(self, data:Dict[str, Any]) -> None:
        '''Escribe el diccionario actual en el archivo json'''
        try:
            with open(self.CONFIG_FILE, 'w', encoding='utf-8') as file:
                json.dump(data, file, indent=4, ensure_ascii=False)
        except Exception:
            logger.error("Error al guardar la configuracion", exc_info=True)
        
    def get(self, category:str, key:str) -> Any:
        '''Define control para poder obtener un metodo especifico'''
        return self.config.get(category, {}).get(key, self.DEFAULT_CONFIG.get(category, {}).get(key))
    
    def set(self, category:str, key:str, value:Any) -> None:
        '''Actualiza un valor y lo guarda directamente en el disco'''
        if category not in self.config:
            self.config[category] = {}
        
        self.config[category][key] = value
        self._save_to_disk(self.config)

config_manager = UserConfigManager()