import os
from PyQt6 import QtWidgets, QtCore, QtGui
from utils.fmt_config import config_manager
from utils.logger import setup_logger
from ui.views.settings_dialog import SettingsDialog

logger = setup_logger(__name__)

class BatchSetupDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configuracion procesamiento por lotes")
        self.setMinimumSize(550, 550)
        self.setModal(True)
        
        self.input_directory = config_manager.get("paths", "input_last_dir") # Aquí guardaremos la ruta de ENTRADA seleccionada
        self.output_directory = config_manager.get("paths", "pre_set_output_dir") # Aquí guardaremos la ruta de SALIDA seleccionada

        self._setup_ui()
        self._load_summary_data()

    def _setup_ui(self):
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setSpacing(15)

        # 1. CARPETA DE ENTRADA
        group_input = QtWidgets.QGroupBox("Carpeta de entrada")
        layout_input = QtWidgets.QHBoxLayout(group_input)
        
        self.txt_input_dir = QtWidgets.QLineEdit()
        if self.input_directory == "":
            self.txt_input_dir.setPlaceholderText("Selecciona una carpeta de entrada")
        else:
            self.txt_input_dir.setPlaceholderText(self.input_directory)
        self.txt_input_dir.setReadOnly(True)
        
        btn_browse_input = QtWidgets.QPushButton("...")
        btn_browse_input.setFixedWidth(40)
        btn_browse_input.clicked.connect(self._select_input_directory)
        
        layout_input.addWidget(self.txt_input_dir)
        layout_input.addWidget(btn_browse_input)
        main_layout.addWidget(group_input)

        # 2 CONTENEDOR CENTRAL (Imagen y TH)

        middle_layout = QtWidgets.QHBoxLayout()

        # --- PANEL: Formato Imagen ---
        group_img = QtWidgets.QGroupBox("Formato Imagen")
        layout_img = QtWidgets.QVBoxLayout(group_img)
        
        # Diccionario visual para actualizar datos fácilmente después
        self.lbls_img = {
            "Formato": QtWidgets.QLabel(),
            "Calidad": QtWidgets.QLabel(),
            "DPI": QtWidgets.QLabel(),
            "Lado largo": QtWidgets.QLabel(),
            "Nombre carpeta": QtWidgets.QLabel()
        }
        layout_img.addLayout(self._create_summary_form(self.lbls_img))
        
        btn_mod_img = QtWidgets.QPushButton("Modificar")
        btn_mod_img.clicked.connect(lambda: self._open_settings_at_tab(1)) # <- Manda a la pestaña indicada 1 = tab imagen
        layout_img.addWidget(btn_mod_img, alignment=QtCore.Qt.AlignmentFlag.AlignHCenter)
        
        middle_layout.addWidget(group_img)

        # --- PANEL: Formato TH ---
        group_th = QtWidgets.QGroupBox("Formato TH")
        layout_th = QtWidgets.QVBoxLayout(group_th)
        
        self.lbls_th = {
            "Formato": QtWidgets.QLabel(),
            "Calidad": QtWidgets.QLabel(),
            "DPI": QtWidgets.QLabel(),
            "Lado corto": QtWidgets.QLabel()
        }
        layout_th.addLayout(self._create_summary_form(self.lbls_th))
        
        btn_mod_th = QtWidgets.QPushButton("Modificar")
        btn_mod_th.clicked.connect(lambda: self._open_settings_at_tab(2)) # 2 = Tab TH
        layout_th.addWidget(btn_mod_th, alignment=QtCore.Qt.AlignmentFlag.AlignHCenter)
        
        middle_layout.addWidget(group_th)
        main_layout.addLayout(middle_layout)

        # 3. FORMATO PDF
        group_pdf = QtWidgets.QGroupBox("Formato PDF")
        layout_pdf = QtWidgets.QVBoxLayout(group_pdf)
        
        self.lbls_pdf = {
            "Estado": QtWidgets.QLabel(),
            "DPI": QtWidgets.QLabel(),
            "Calidad": QtWidgets.QLabel()
        }
        layout_pdf.addLayout(self._create_summary_form({"Estado": self.lbls_pdf["Estado"]}))

        # Para el PDF usamos un grid horizontal
        pdf_form_layout = QtWidgets.QHBoxLayout()
        pdf_form_layout.addLayout(self._create_summary_form({"DPI": self.lbls_pdf["DPI"]}))
        pdf_form_layout.addLayout(self._create_summary_form({"Calidad": self.lbls_pdf["Calidad"]}))
        
        layout_pdf.addLayout(pdf_form_layout)

        btn_mod_pdf = QtWidgets.QPushButton("Modificar")
        btn_mod_pdf.clicked.connect(lambda: self._open_settings_at_tab(3)) # 3 = Tab PDF
        layout_pdf.addWidget(btn_mod_pdf, alignment=QtCore.Qt.AlignmentFlag.AlignHCenter)
        
        main_layout.addWidget(group_pdf)

        # ==========================================
        # 4. CARPETA DE SALIDA
        # ==========================================
        group_output = QtWidgets.QGroupBox("Carpeta de salida")
        layout_output = QtWidgets.QHBoxLayout(group_output)
        
        self.txt_output_dir = QtWidgets.QLineEdit()
        if not self.output_directory:
            self.txt_output_dir.setPlaceholderText("Selecciona una carpeta de salida")
        else:
            self.txt_output_dir.setPlaceholderText(self.output_directory)
        self.txt_output_dir.setReadOnly(True)
        
        btn_mod_out = QtWidgets.QPushButton("Modificar")
        btn_mod_out.clicked.connect(lambda: self._open_settings_at_tab(0)) # 0 = Tab Rutas
        
        layout_output.addWidget(self.txt_output_dir)
        layout_output.addWidget(btn_mod_out)
        main_layout.addWidget(group_output)

        # ==========================================
        # 5. BOTONES DE ACCIÓN (FOOTER)
        # ==========================================
        main_layout.addStretch()
        footer_layout = QtWidgets.QHBoxLayout()
        footer_layout.addStretch()

        btn_cancel = QtWidgets.QPushButton("Cancelar")
        btn_cancel.setMinimumWidth(100)
        btn_cancel.clicked.connect(self.reject)

        btn_start = QtWidgets.QPushButton("Iniciar")
        btn_start.setMinimumWidth(100)
        # CSS básico para el botón azul
        btn_start.setStyleSheet("background-color: #0E86D4; color: white; font-weight: bold;")
        btn_start.clicked.connect(self._validate_and_start)

        footer_layout.addWidget(btn_start)
        footer_layout.addWidget(btn_cancel)
        main_layout.addLayout(footer_layout)

    # --- MÉTODOS DE UTILIDAD Y LÓGICA ---

    def _create_summary_form(self, labels_dict: dict) -> QtWidgets.QFormLayout:
        """Helper para crear la estructura visual de Tabla (Propiedad | Valor)"""
        form = QtWidgets.QFormLayout()
        form.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)
        form.setFormAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)
        form.setHorizontalSpacing(20)
        
        for key, lbl_widget in labels_dict.items():
            # Estilizamos el valor para que resalte
            lbl_widget.setStyleSheet("color: #A0A0A0;") 
            form.addRow(f"{key}:", lbl_widget)
            
        return form

    def _select_input_directory(self):
        """Abre el explorador para elegir la carpeta donde están las fotos a procesar"""
        last_dir = config_manager.get("paths", "input_last_dir") or os.path.expanduser("~")
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, "Seleccionar Carpeta de Entrada", last_dir)
        if folder:
            config_manager.set("paths", "input_last_dir", folder)
            self.input_directory = folder
            self.txt_input_dir.setText(folder)

    def _open_settings_at_tab(self, tab_index: int):
        """Abre el SettingsDialog y lo fuerza a mostrar una pestaña específica"""
        dialog = SettingsDialog(self)
        dialog.tabs.setCurrentIndex(tab_index) # <- Aqui abre la pestaña segun el indice asignado
        
        # Esperamos a que el usuario cierre la ventana (Aceptar o Cancelar)
        dialog.exec() 
        
        # Una vez cerrada, recargamos el JSON por si hubo cambios
        self._load_summary_data()

    def _load_summary_data(self):
        """Lee el JSON y actualiza todos los QLabels de la interfaz"""
        # Imagen
        self.lbls_img["Formato"].setText(str(config_manager.get("export_image", "format")).upper())
        self.lbls_img["Calidad"].setText(str(config_manager.get("export_image", "quality")))
        self.lbls_img["DPI"].setText(str(config_manager.get("export_image", "dpi")))
        self.lbls_img["Lado largo"].setText(f"{config_manager.get('export_image', 'longest_edge')} px")
        self.lbls_img["Nombre carpeta"].setText(str(config_manager.get("export_image", "output_dir")))

        # TH
        self.lbls_th["Formato"].setText(str(config_manager.get("export_th", "format")).upper())
        self.lbls_th["Calidad"].setText(str(config_manager.get("export_th", "quality")))
        self.lbls_th["DPI"].setText(str(config_manager.get("export_th", "dpi")))
        self.lbls_th["Lado corto"].setText(f"{config_manager.get('export_th', 'shortest_edge')} px")

        # PDF
        is_pdf_enabled = config_manager.get("export_pdf", "enabled")
        self.lbls_pdf["Estado"].setText("HABILITADO" if is_pdf_enabled else "Deshabilitado")
        self.lbls_pdf["Estado"].setStyleSheet("color: #4CAF50; font-weight: bold;" if is_pdf_enabled else "color: #D32F2F;")
        
        self.lbls_pdf["DPI"].setText(str(config_manager.get("export_pdf", "dpi")))
        self.lbls_pdf["Calidad"].setText(str(config_manager.get("export_pdf", "quality")))

        # Salida
        use_preset = config_manager.get("paths", "use_preset_dir")
        preset_dir = config_manager.get("paths", "pre_set_output_dir")
        last_dir = config_manager.get("paths", "last_dir")
        
        if use_preset and preset_dir:
            self.txt_output_dir.setText(preset_dir)
            self.output_directory = preset_dir
            config_manager.set("paths", "last_dir", preset_dir)
        elif preset_dir: 
            self.txt_output_dir.setText(preset_dir)
            self.output_directory = preset_dir
            config_manager.set("paths", "last_dir", preset_dir)
        else:
            self.txt_output_dir.setText(last_dir)
            self.output_directory = last_dir

    def _validate_and_start(self):
        """Valida que haya una carpeta de entrada y una de salida antes de iniciar el lote"""
        if not self.input_directory:
            QtWidgets.QMessageBox.warning(self, "Atención", 'Debes seleccionar una carpeta de entrada.\n' \
            'Presiona "Modificar" en la seccion "carpeta de entrada" para seleccionar tu carpeta de entrada')
            return
        
        if not self.output_directory:
            QtWidgets.QMessageBox.warning(self, "Atención", 'Debes seleccionar una carpeta de salida.\n' \
            'Presiona "Modificar" en la seccion "carpeta de salida" para seleccionar tu carpeta de salida')
            return
        # Si todo está bien, cerramos el diálogo devolviendo "Aceptado"
        self.accept()
            
    def get_directories(self) -> tuple[str, str]:
        """Método público para que main.py pueda obtener las rutas seleccionadas"""
        return self.input_directory, self.output_directory