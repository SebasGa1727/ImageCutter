from __future__ import annotations

from typing import Optional

from PyQt6 import QtCore, QtGui, QtWidgets
from utils.logger import setup_logger
from ui.views.settings_dialog import SettingsDialog

logger = setup_logger(__name__)

class LandingView(QtWidgets.QWidget):
    """Vista de bienvenida reutilizable que emite señales de navegación"""
    requestLoadImage = QtCore.pyqtSignal()
    requestLoadBatch = QtCore.pyqtSignal()
    #TODO requestFastConvert = QtCore.pyqtSignal()
    #TODO requestPdfGenerator = QtCore.pyqtSignal() 


    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(12)
        layout.setContentsMargins(24, 24, 24, 24)

        welcome = QtWidgets.QLabel('Bienvenido a <span style="color: #0c8ce9;">ImageCutter</span>')
        welcome.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        welcome_font = welcome.font()
        welcome_font.setPointSize(27)
        welcome_font.setBold(True)
        welcome.setFont(welcome_font)
        welcome.setStyleSheet('background-color: transparent')

        label = QtWidgets.QLabel('Selecciona la opcion que deseas ejecutar')
        label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        label_font = label.font()
        label_font.setPointSize(20)
        label_font.setBold(False)
        label.setFont(label_font)
        label.setStyleSheet('background-color: transparent; color: #CCCCCC')

        #Confirguracion estetica de botones
        btn_style = """
            QPushButton {
                background-color: transparent; 
                color: #ffffff; 
                border: 2px solid #0c8ce9; 
                border-radius: 16px; 
                padding: 16px;
                font-size: 17px;
            }
            QPushButton:hover {
                background-color: #0c8ce9;
                font-size: 16px;
                font-weight: bold;
            }
        """

        btn_batch = QtWidgets.QPushButton('Procesamiento por Lote')
        btn_batch.setStyleSheet(btn_style)
        btn_batch.clicked.connect(lambda: self.requestLoadBatch.emit())

        btn_image = QtWidgets.QPushButton('Cargar Imagen Individual')
        btn_image.setStyleSheet(btn_style)
        btn_image.clicked.connect(lambda: self.requestLoadImage.emit())

        # btn_convert = QtWidgets.QPushButton('Convertir Formato de Imagenes')
        # btn_convert.setStyleSheet(btn_style)
        # btn_convert.clicked.connect(lambda: self.requestFastConvert.emit())

        # btn_pdf = QtWidgets.QPushButton('Herramientas de PDF')
        # btn_pdf.setStyleSheet(btn_style)
        # btn_pdf.clicked.connect(lambda: self.requestPdfGenerator.emit())

        #Diseño de cuadricula para los botones principales
        grid_layout = QtWidgets.QGridLayout()
        grid_layout.setSpacing(20)

        grid_layout.addWidget(btn_batch, 0, 0)
        grid_layout.addWidget(btn_image, 0, 1)

        grid_container = QtWidgets.QWidget()
        grid_container.setLayout(grid_layout)
        grid_container.setMinimumWidth(600)
        grid_container.setMaximumWidth(700)

        #Ensamblaje principal
        layout.addStretch(1)
        layout.addWidget(welcome)
        layout.addSpacing(10)
        layout.addWidget(label)
        layout.addSpacing(40)
        layout.addWidget(grid_container, alignment=QtCore.Qt.AlignmentFlag.AlignHCenter)
        layout.addStretch(1)

        #Agregamos el boton de configuracion de formato
        self.btn_settings = QtWidgets.QToolButton(self)
        self.btn_settings.setText("⚙️")
        self.btn_settings.setToolTip("Configuracion de valores de exportacion")
        #Diseño CSS de boton de configuracion
        self.btn_settings.setStyleSheet('''
            QToolButton {
                background: transparent;
                border: none;
                font-size: 20pt;
            }
            QToolButton:hover {
                background-color: rgb(0, 0, 0);
                border-radius: 6px;
            }
        ''')
        self.btn_settings.clicked.connect(self._open_settings)

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:
        """
        Sobrescribimos el evento de redimensionamiento nativo.
        Esto ancla el botón a la coordenada x=24, y=24 (respetando tus márgenes)
        sin importar de qué tamaño haga la ventana el usuario.
        """
        super().resizeEvent(event)
        self.btn_settings.move(1, 24)

    def _open_settings(self) -> None:
        """Instancia y ejecuta la ventana de configuración."""
        try:
            # Usamos self.window() para que herede de MainWindow, centrando el modal a la perfección
            dialog = SettingsDialog(self.window())
            dialog.exec()
        except Exception:
            logger.error("Error al intentar abrir el panel de configuracion", exc_info=True)