import sys
import os
# TRUCO PARA MOCK: Agregar la raíz del proyecto al PATH
if __name__ == "__main__":
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from PyQt6 import QtWidgets, QtCore, QtGui
from utils.logger import setup_logger

logger = setup_logger(__name__)

class BatchSummaryView(QtWidgets.QWidget):
    request_continue = QtCore.pyqtSignal(bool, str) # True = Continuar con TH, False = Sin TH 
    # El str es el nombre del archivo para crear th

    def __init__(self, parent=None):
        super().__init__(parent)
        self.success_list = []
        self.error_list = []
        self.current_image_path = None
        
        self._setup_ui()

    def _setup_ui(self):
        self.main_layout = QtWidgets.QVBoxLayout(self)
        self.main_layout.setSpacing(15)
        self.main_layout.setContentsMargins(20, 20, 20, 20)
        
        self.setStyleSheet("background-color: #2D2D2D; color: white;")

        group_box_style = """
            QGroupBox { 
                font-weight: bold; 
                font-size: 14px;
                border: 1px solid #828282; 
                border-radius: 6px; 
                margin-top: 12px; 
                padding-top: 6px; 
            } 
            QGroupBox::title { 
                color: #F7F7F7;
                subcontrol-origin: margin; 
                subcontrol-position: top left; 
                left: 20px; 
                padding: 2px 2px; 
            }
        """

        # ==========================================
        # ZONA CENTRAL (Splitter Principal)
        # ==========================================
        split_layout = QtWidgets.QHBoxLayout()
        split_layout.setSpacing(20)
        
        # ------------------------------------------
        # PANEL IZQUIERDO
        # ------------------------------------------
        left_panel = QtWidgets.QVBoxLayout()
        left_panel.setSpacing(15)
        
        # 1. Vista Previa (Arriba)
        preview_group = QtWidgets.QGroupBox("Vista Previa")
        preview_group.setStyleSheet(group_box_style)
        preview_layout = QtWidgets.QVBoxLayout(preview_group)
        
        self.lbl_preview_title = QtWidgets.QLabel("Ningún archivo seleccionado")
        self.lbl_preview_title.setStyleSheet("font-size: 15px; margin-bottom: 5px; font-weight: bold; color: #7CB1D6;")
        
        self.lbl_preview_img = QtWidgets.QLabel()
        self.lbl_preview_img.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.lbl_preview_img.setStyleSheet("background-color: #1E1E1E; border-radius: 5px;")
        self.lbl_preview_img.setMinimumSize(100, 100)
        self.lbl_preview_img.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding)
        self.lbl_preview_img.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding)
        
        preview_layout.addWidget(self.lbl_preview_title)
        preview_layout.addWidget(self.lbl_preview_img, stretch=1)
        
        left_panel.addWidget(preview_group, stretch=1)

        # 2. Estatus de resultados (Abajo)
        top_group = QtWidgets.QGroupBox("Estatus de resultados")
        top_group.setStyleSheet(group_box_style)
        top_layout = QtWidgets.QHBoxLayout(top_group)
        
        self.lbl_success = QtWidgets.QLabel("Exportados correctamente: 0/0")
        self.lbl_success.setStyleSheet("color: #7CB1D6 ; font-weight: bold; font-size: 16px;")
        
        self.lbl_errors = QtWidgets.QLabel("Error de exportación: 0/0")
        self.lbl_errors.setStyleSheet("color: #C23C34; font-weight: bold; font-size: 16px;")
        
        top_layout.addWidget(self.lbl_success)
        top_layout.addStretch()
        top_layout.addWidget(self.lbl_errors)
        
        left_panel.addWidget(top_group) # Se ancla abajo del visor
        
        # Agregamos todo el bloque izquierdo al Splitter
        split_layout.addLayout(left_panel, stretch=3)

        # ------------------------------------------
        # PANEL DERECHO
        # ------------------------------------------
        right_panel = QtWidgets.QVBoxLayout()
        right_panel.setSpacing(15)
        
        # 1. Formato Imagen (Arriba)
        list_group = QtWidgets.QGroupBox("Formato Imagen")
        list_group.setStyleSheet(group_box_style)
        list_layout = QtWidgets.QVBoxLayout(list_group)
        
        self.list_widget = QtWidgets.QListWidget()
        self.list_widget.setStyleSheet("QListWidget { background-color: #1E1E1E; border-radius: 4px; outline: none; font-size: 14px;} QListWidget::item { padding: 8px; border-bottom: 1px solid #444; } QListWidget::item:selected { background-color: #0c8ce9; color: white; border-radius: 4px; font-weight: bold;}")
        self.list_widget.setDragDropMode(QtWidgets.QAbstractItemView.DragDropMode.InternalMove)
        self.list_widget.currentItemChanged.connect(self._on_item_selected)
        
        list_layout.addWidget(self.list_widget)
        right_panel.addWidget(list_group, stretch=3)
        
        # 2. Caja inferior (Información y Checkbox lado a lado)
        bottom_right_layout = QtWidgets.QHBoxLayout()
        
        # 2a. Información de imagen (Izquierda de la caja inferior)
        info_group = QtWidgets.QGroupBox("Información de imagen")
        info_group.setStyleSheet(group_box_style)
        info_layout = QtWidgets.QVBoxLayout(info_group)
        
        self.lbl_dims = QtWidgets.QLabel("Dimensiones: - x -")
        self.lbl_dpi = QtWidgets.QLabel("DPI: - x -")
        self.lbl_quality = QtWidgets.QLabel("Calidad: -%")
        
        for lbl in [self.lbl_dims, self.lbl_dpi, self.lbl_quality]:
            lbl.setStyleSheet("font-weight: bold; font-size: 14px; color: #CFCFCF;")
            info_layout.addWidget(lbl)
            
        bottom_right_layout.addWidget(info_group, stretch=1)
        
        # 2b. Checkbox de confirmación (Derecha de la caja inferior)
        self.chk_confirm_pdf = QtWidgets.QCheckBox("Este es el orden que quiero en mi PDF")
        self.chk_confirm_pdf.setStyleSheet("QCheckBox { font-size: 16px; font-weight: bold; color: #F7F7F7; } QCheckBox::indicator { width: 20px; height: 20px; }")
        self.chk_confirm_pdf.toggled.connect(self._toggle_continue_buttons)
        bottom_right_layout.addWidget(self.chk_confirm_pdf, stretch=1, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)

        right_panel.addLayout(bottom_right_layout, stretch=1)
        
        # Agregamos todo el bloque derecho al Splitter
        split_layout.addLayout(right_panel, stretch=2)

        # Agregamos el Splitter principal al layout maestro
        self.main_layout.addLayout(split_layout, stretch=1)

        # ==========================================
        # 3. FOOTER: Botones de Acción
        # ==========================================
        footer_layout = QtWidgets.QHBoxLayout()
        footer_layout.addStretch()

        self.btn_continue_no_th = QtWidgets.QPushButton("Continuar SIN TH")
        self.btn_continue_no_th.setMinimumHeight(45)
        self.btn_continue_no_th.setMinimumWidth(160)
        self.btn_continue_no_th.setStyleSheet("QPushButton { background-color: transparent; border: 2px solid #555; border-radius: 6px; font-weight: bold; font-size: 14px;} QPushButton:hover { background-color: rgba(255,255,255,0.1); } QPushButton:disabled { color: #555; border-color: #333; }")
        self.btn_continue_no_th.clicked.connect(lambda: self._confirm_continue_without_th(False))
        self.btn_continue_no_th.setEnabled(False) 

        self.btn_continue_th = QtWidgets.QPushButton("Continuar con esta TH")
        self.btn_continue_th.setMinimumHeight(45)
        self.btn_continue_th.setMinimumWidth(200)
        self.btn_continue_th.setStyleSheet("QPushButton { background-color: #0c8ce9; color: white; border-radius: 6px; font-weight: bold; font-size: 15px;} QPushButton:disabled { background-color: #1a4f76; color: #777; }")
        self.btn_continue_th.clicked.connect(lambda: self._confirm_continue_with_th(True))
        self.btn_continue_th.setEnabled(False) 

        footer_layout.addWidget(self.btn_continue_th)
        footer_layout.addWidget(self.btn_continue_no_th)
        self.main_layout.addLayout(footer_layout)

    def _toggle_continue_buttons(self, checked: bool):
        """Activa o desactiva los botones dependiendo de la checkbox de confirmación."""
        self.btn_continue_th.setEnabled(checked)
        self.btn_continue_no_th.setEnabled(checked)


    # --- LÓGICA DE LA VISTA ---

    def load_summary_data(self, success_list: list, error_list: list):
        """Inyecta los datos reales al finalizar el lote."""
        self.success_list = success_list
        self.error_list = error_list
        
        total = len(success_list) + len(error_list)
        self.lbl_success.setText(f"Exportados correctamente: {len(success_list)}/{total}")

        if len(error_list) == 0: #Si la lista de errores es 0
            self.lbl_errors.setVisible(False) #<- La ocultamos
        else:
            self.lbl_errors.setVisible(True)#<- Si no la mostramos
            self.lbl_errors.setText(f"Error de exportación: {len(error_list)}/{total}")
        
        self.list_widget.clear()
        
        # Llenamos la lista (solo guardamos el nombre visible, y la ruta completa como dato oculto)
        for path in success_list:
            item = QtWidgets.QListWidgetItem(os.path.basename(path))
            item.setData(QtCore.Qt.ItemDataRole.UserRole, path)
            self.list_widget.addItem(item)
            
        # Seleccionamos el primero automáticamente si existe
        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(0)

    def _on_item_selected(self, current, previous):
        """Manejador del Lazy Loading. Se ejecuta cada vez que haces clic en un elemento de la lista."""
        if current is None:
            return
            
        # Obtenemos la ruta real oculta en el item
        file_path = current.data(QtCore.Qt.ItemDataRole.UserRole)
        self.current_image_path = file_path
        self.lbl_preview_title.setText(os.path.basename(file_path))
        
        # 1. Leer Metadatos sin cargar toda la imagen a la RAM (Súper eficiente)
        reader = QtGui.QImageReader(file_path)
        size = reader.size()
        
        # Para DPI y Calidad, asumiremos que se leen desde el archivo o la config (por ahora Mock)
        # Nota: Extraer DPI reales requiere leer cabeceras EXIF, aquí simulamos con la config
        from utils.fmt_config import config_manager
        dpi = config_manager.get("export_image", "dpi")
        quality = config_manager.get("export_image", "quality")
        
        self.lbl_dims.setText(f"Dimensiones: {size.width()} x {size.height()}")
        self.lbl_dpi.setText(f"DPI: {dpi} x {dpi}")
        self.lbl_quality.setText(f"Calidad: {quality}%")
        
        # 2. Cargar vista previa (Lazy Loading)
        pixmap = QtGui.QPixmap(file_path)
        if not pixmap.isNull():
            # Escalamos el pixmap para que encaje en el label sin deformarse
            scaled_pixmap = pixmap.scaled(
                self.lbl_preview_img.size(),
                QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                QtCore.Qt.TransformationMode.SmoothTransformation
            )
            self.lbl_preview_img.setPixmap(scaled_pixmap)

    def resizeEvent(self, event):
        """Si el usuario redimensiona la ventana, la imagen se re-escala suavemente."""
        super().resizeEvent(event)
        if self.current_image_path:
            self._on_item_selected(self.list_widget.currentItem(), None)

    def _confirm_continue_without_th(self, with_th: bool):
        """Muestra la alerta de confirmación del orden de las imágenes."""
        if self.list_widget.count() == 0:
            return
            
        respuesta = QtWidgets.QMessageBox.question(
            self,
            "Confirmar Exportación",
            "No se creara formato en TH\n\n¿Estas seguro de continuar?",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No
        )
        
        if respuesta == QtWidgets.QMessageBox.StandardButton.Yes:
            # Aquí recolectaríamos el nuevo orden de la lista para mandárselo a main.py
            ordered_paths = [self.list_widget.item(i).data(QtCore.Qt.ItemDataRole.UserRole) for i in range(self.list_widget.count())]
            self.chk_confirm_pdf.setChecked(False)
            # Emitimos señal para continuar
            self.request_continue.emit(with_th, "")

    def _confirm_continue_with_th(self, with_th: bool):
        '''Ordena la lista y emite el mensaje de confirmacion'''
        ordered_paths = [self.list_widget.item(i).data(QtCore.Qt.ItemDataRole.UserRole) for i in range(self.list_widget.count())]
        self.chk_confirm_pdf.setChecked(False)
        self.request_continue.emit(with_th, self.current_image_path)
        
       
# ZONA DE PRUEBAS AISLADA (MOCK ENVIRONMENT)
if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    
    # Configuramos el estilo de la app de prueba para que se parezca a tu entorno oscuro
    app.setStyle("Fusion")
    
    test_view = BatchSummaryView()
    test_view.resize(1100, 750)
    test_view.showMaximized()
    
    ruta_real_de_prueba = os.path.abspath("C:/Users/Sebastian/Documents/Sebastian Galicia/Proyects/HICutter/output/Recortadas/AHSEDENA_XI_112_Z_E0014_F001F.jpg") # <- Cambia esto por una foto ".jpg" real tuya
    
    datos_exito_falsos = [
        ruta_real_de_prueba,
        "C:/Fake/Foto_002.jpg",
        "C:/Fake/Foto_003.jpg"
    ]
    
    test_view.load_summary_data(datos_exito_falsos, [])
    test_view.show()
    sys.exit(app.exec())