import os
from PyQt6 import QtWidgets, QtCore
from utils.fmt_config import config_manager
from utils.logger import setup_logger

logger = setup_logger(__name__)

#Panel de configuracion de formato de exportacion de imagen, TH, PDF y IA
class SettingsDialog(QtWidgets.QDialog):

    def __init__(self, parent = None):
        super().__init__(parent)
        
        self.setWindowTitle("Configuracion de exportacion")
        self.setMinimumSize(550, 350)

        #Obligamos al usuario a cerrar esta ventana antes de continuar usando la APP
        self.setModal(True)

        self._setup_ui()
        self._load_current_settings()

    def _setup_ui(self):
        '''Construimos la interfas basada en pestañas'''
        main_layout = QtWidgets.QVBoxLayout(self)

        #Creamos el contenedor de pestañas
        self.tabs = QtWidgets.QTabWidget()
        main_layout.addWidget(self.tabs)

        #Creamos cada pestaña por separado
        self.tabs.addTab(self._create_paths_tab(), "Carpeta guardado")
        self.tabs.addTab(self._create_image_tab(), "Formato Imagen")
        self.tabs.addTab(self._create_th_tab(), "Formato TH")
        self.tabs.addTab(self._create_pdf_tab(), "PDF")
        self.tabs.addTab(self._create_ai_tab(), "Entrenamiento IA")
        

        #Creamos la variable de boton para mas adelante poder definir su posicion y existencia
        btn_layout = QtWidgets.QHBoxLayout()

        #Creamos botones globales (Guarda cambios/Cancelar)
        self.btn_save = QtWidgets.QPushButton("Guardar Cambios")
        self.btn_save.setObjectName("btnAceptar") #<- Le asignamos un ID para despues agregarle CSS
        self.btn_save.clicked.connect(self.save_and_close)

        self.btn_cancel = QtWidgets.QPushButton("Cancelar")
        self.btn_cancel.setObjectName("btnCancel")
        self.btn_cancel.clicked.connect(self.reject) #<- Rechaza y cierra sin guardar

        btn_layout.addStretch() #Empuja los botones a la derecha por defecto
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_save)

        main_layout.addLayout(btn_layout)
    
    def _create_paths_tab(self) -> QtWidgets.QWidget:
        #Creamos el metodo de construccion de pestañas y su contenido de cada una
        '''Creamos el formulario para la ruta de guardado'''
        tab = QtWidgets.QWidget()
        layout = QtWidgets.QFormLayout(tab)

        self.check_ruta_definitiva = QtWidgets.QCheckBox("Guardar siempre en esta ruta sin preguntar")
        layout.addWidget(self.check_ruta_definitiva)

        ruta_layout = QtWidgets.QHBoxLayout()

        self.input_ruta = QtWidgets.QLineEdit()
        self.input_ruta.setPlaceholderText("Selecciona una carpeta de salida...")
        self.input_ruta.setReadOnly(True) #<- Evitamos que el usuario escriba basura y forzamos a usar el boton

        self.btn_explorar = QtWidgets.QPushButton("...")
        self.btn_explorar.setFixedWidth(40)
        self.btn_explorar.clicked.connect(self._abrir_explorador)

        ruta_layout.addWidget(self.input_ruta)
        ruta_layout.addWidget(self.btn_explorar)

        #Agrupamos visualmente
        grupo_ruta = QtWidgets.QGroupBox("Directorio de salida predeterminado")
        grupo_layout = QtWidgets.QVBoxLayout(grupo_ruta)
        grupo_layout.addLayout(ruta_layout)

        layout.addWidget(grupo_ruta)
        
        return tab

    def _abrir_explorador(self):
        '''Abre el explorador de Windows y guarda la selección en el QLineEdit'''
        last_dir = config_manager.get("paths", "last_dir") or os.path.expanduser("~")

        carpeta_seleccionada = QtWidgets.QFileDialog.getExistingDirectory(self, "Seleccionar carpeta", last_dir)

        if carpeta_seleccionada:
            self.input_ruta.setText(carpeta_seleccionada)

        else:
            QtWidgets.QMessageBox.information(self, 'Aviso', 'No se selecciono ninguna carpeta')
            return

    def _create_image_tab(self) -> QtWidgets.QWidget:
        '''Crearemos el formularo para RD'''
        tab = QtWidgets.QWidget()
        #Definiremos que sea un QFormLayout para que funga como tipo formulario
        layout = QtWidgets.QFormLayout(tab)

        #Crearemos el tipo de entrada que permitira cada seccion
        self.image_format = QtWidgets.QComboBox() #<- Le estamos diciendo que tendra una lista desplegable
        self.image_format.addItems(["jpg", "png", "tif"])

        self.image_quality = QtWidgets.QSpinBox() #<- Le indicamos que acepte valores numericos
        self.image_quality.setRange(1, 100)

        self.image_dpi = QtWidgets.QSpinBox()
        self.image_dpi.setRange(72, 600)

        self.image_long_edge = QtWidgets.QSpinBox()
        self.image_long_edge.setRange(500, 10000)
        self.image_long_edge.setSuffix(" px") #<- Le agregamos un sufijo, que no afecta la matematica

        self.image_folder = QtWidgets.QLineEdit() #<- Le indicamos que acepte texto plano

        layout.addRow("Formato de imagen:", self.image_format) #<- Le indicamos el texto y el tipo de valor que recibira
        layout.addRow("Calidad de la imagen (%):", self.image_quality)
        layout.addRow("DPI:", self.image_dpi)
        layout.addRow("Lado largo:", self.image_long_edge)
        layout.addRow("Nombre carpeta:", self.image_folder)

        return tab
    
    def _create_th_tab(self) -> QtWidgets.QWidget:
        """Crea el formulario para TH"""
        tab = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(tab)
        
        self.create_th = QtWidgets.QCheckBox("Crear thumbnail (TH)")
        layout.addWidget(self.create_th)

        info_label = QtWidgets.QLabel(
            "<i>Nota:<br> Esta opción afecta únicamente al procesamiento de imagen INDIVIDUAL<br>"
            "En el procesamiento por lotes, podrás elegir tu miniatura al finalizar.</i>"
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #888888; font-size: 12px; margin-left: 20px; margin-bottom: 10px;")
        layout.addWidget(info_label)

        form_container = QtWidgets.QWidget()
        form_layout = QtWidgets.QFormLayout(form_container)
        form_layout.setContentsMargins(0,0,0,0)

        self.th_format = QtWidgets.QComboBox()
        self.th_format.addItems(["jpg", "png"])
        
        self.th_quality = QtWidgets.QSpinBox()
        self.th_quality.setRange(1, 100)
        
        self.th_dpi = QtWidgets.QSpinBox()
        self.th_dpi.setRange(72, 300)
        
        self.th_short_edge = QtWidgets.QSpinBox()
        self.th_short_edge.setRange(100, 2000)
        self.th_short_edge.setSuffix(" px")

        form_layout.addRow("Formato de imagen:", self.th_format)
        form_layout.addRow("Calidad JPG (%):", self.th_quality)
        form_layout.addRow("DPI:", self.th_dpi)
        form_layout.addRow("Longitud lado corto:", self.th_short_edge)
        
        layout.addWidget(form_container)
        layout.addStretch()

        return tab
        
    def _create_pdf_tab(self) -> QtWidgets.QWidget:
        '''Creamos formulario para pdf'''
        tab = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(tab)

        # Creamos un checkbox para saber si quiere o no generar pdf
        self.pdf_enable_check = QtWidgets.QCheckBox("Exportar a PDF") 
        # Conectamos el clic de la checkbox a la función que oculta/muestra el formulario
        self.pdf_enable_check.toggled.connect(self._toggle_pdf_options)
        layout.addWidget(self.pdf_enable_check)

        #Creamos un contenedor a parte para que se oculte si no esta marcado el checkbox anterior
        self.pdf_options_container = QtWidgets.QWidget()
        form_layout = QtWidgets.QFormLayout(self.pdf_options_container)

        self.pdf_dpi = QtWidgets.QSpinBox()
        self.pdf_dpi.setRange(72, 600)

        self.pdf_quality = QtWidgets.QSpinBox()
        self.pdf_quality.setRange(1, 100)

        form_layout.addRow("DPI:", self.pdf_dpi)
        form_layout.addRow("Calidad de compresion (%)", self.pdf_quality)

        layout.addWidget(self.pdf_options_container)
        layout.addStretch()

        return tab

    def _toggle_pdf_options(self, checked: bool) -> bool:
        """Muestra u oculta el contenedor de opciones de PDF basado en la checkbox."""
        self.pdf_options_container.setVisible(checked)

    def _create_ai_tab(self) -> QtWidgets.QWidget:
        tab = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(tab)
        
        self.ai_yolo_check = QtWidgets.QCheckBox("Habilitar exportación de coordenadas para IA")
        layout.addWidget(self.ai_yolo_check)
        
        # Nota informativa con formato de "alerta suave"
        info_label = QtWidgets.QLabel(
            "<b>Nota Informativa:</b><br>"
            "Esta casilla sirve para determinar si deseas crear información"
            "para el entrenamiento de un modelo de IA.<br>"
            "<i>(Se recomienda mantener desactivado para usuarios estándar)</i>"
        )
        info_label.setWordWrap(True) # Permite que el texto baje a la siguiente línea
        info_label.setStyleSheet("color: #D6D989; margin-top: 15px;") # Color gris para que no sea agresivo
        
        layout.addWidget(info_label)
        layout.addStretch()
        return tab

    def _load_current_settings(self):
        #Creamos el metodo de precargar los datos guardados en el JSON
        try:
            # Pestaña Path
            is_ruta_definitiva_checked = bool(config_manager.get("paths", "use_preset_dir") or False)
            self.check_ruta_definitiva.setChecked(is_ruta_definitiva_checked)
            self.input_ruta.setText(config_manager.get("paths", "pre_set_output_dir"))

            # Pestaña image
            self.image_format.setCurrentText(config_manager.get("export_image", "format") or "jpg")
            self.image_quality.setValue(int(config_manager.get("export_image", "quality") or 80))
            self.image_dpi.setValue(int(config_manager.get("export_image", "dpi") or 96))
            self.image_long_edge.setValue(int(config_manager.get("export_image", "longest_edge") or 3000))
            self.image_folder.setText(config_manager.get("export_image", "output_dir"))

            # Pestaña TH
            is_create_th_checked = bool(config_manager.get("export_th", "enabled") or False)
            self.create_th.setChecked(is_create_th_checked)
            self.th_format.setCurrentText(config_manager.get("export_th", "format") or "jpg")
            self.th_quality.setValue(int(config_manager.get("export_th", "quality") or 60))
            self.th_dpi.setValue(int(config_manager.get("export_th", "dpi") or 72))
            self.th_short_edge.setValue(int(config_manager.get("export_th", "shortest_edge") or 500))

            # Pestaña PDF
            is_pdf_enabled = bool(config_manager.get("export_pdf", "enabled") or False)
            self.pdf_enable_check.setChecked(is_pdf_enabled)
            self._toggle_pdf_options(is_pdf_enabled) # Ocultamos/mostramos visualmente al inicio
            
            self.pdf_dpi.setValue(int(config_manager.get("export_pdf", "dpi") or 150))
            self.pdf_quality.setValue(int(config_manager.get("export_pdf", "quality") or 75))
            
            # Pestaña IA
            self.ai_yolo_check.setChecked(bool(config_manager.get("ai_export", "yolo_enabled") or False))
            
        except Exception:
            logger.error("Error al colocar el formulario de configuración", exc_info=True)

    def save_and_close(self):
        # Configuramos el metodo de guardado
        try:
            # Verificacion del pre set path
            if self.check_ruta_definitiva.isChecked() and not self.input_ruta.text().strip():
                QtWidgets.QMessageBox.warning(self, "Acción Requerida", "Marcaste la casilla de ruta definitiva, sin seleccionar ninguna carpeta" \
                "\nSelecciona una carpeta para poder guardar")
                return
            
            # Guardado Path
            config_manager.set("paths", "use_preset_dir", self.check_ruta_definitiva.isChecked())
            config_manager.set("paths", "pre_set_output_dir", self.input_ruta.text().strip())

            # Guardado image
            config_manager.set("export_image", "format", self.image_format.currentText())
            config_manager.set("export_image", "quality", self.image_quality.value())
            config_manager.set("export_image", "dpi", self.image_dpi.value())
            config_manager.set("export_image", "long_edge", self.image_long_edge.value())
            config_manager.set("export_image", "output_dir", self.image_folder.text().strip())

            # Guardado TH
            config_manager.set("export_th", "enabled", self.create_th.isChecked())
            config_manager.set("export_th", "format", self.th_format.currentText())
            config_manager.set("export_th", "quality", self.th_quality.value())
            config_manager.set("export_th", "dpi", self.th_dpi.value())
            config_manager.set("export_th", "short_edge", self.th_short_edge.value())

            # Guardado PDF e IA
            config_manager.set("export_pdf", "enabled", self.pdf_enable_check.isChecked())
            config_manager.set("export_pdf", "dpi", self.pdf_dpi.value())
            config_manager.set("export_pdf", "quality", self.pdf_quality.value())
            config_manager.set("ai_export", "yolo_enabled", self.ai_yolo_check.isChecked())
            
            logger.info("Configuraciones guardadas correctamente.")
            self.accept() 
        except Exception:
            logger.error("Error al guardar settings.json", exc_info=True)