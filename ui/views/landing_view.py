from __future__ import annotations

from typing import Optional

from PyQt6 import QtCore, QtGui, QtWidgets
from utils.logger import setup_logger
from ui.views.settings_dialog import SettingsDialog

logger = setup_logger(__name__)

class LandingView(QtWidgets.QWidget):
    """Vista de bienvenida reutilizable que emite señales de navegación.

    - `requestLoadImage`: emitida cuando el usuario pulsa 'Cargar Imagen'
    - `requestLoadBatch`: emitida cuando el usuario pulsa 'Cargar Lote'
    """
    requestLoadImage = QtCore.pyqtSignal()
    requestLoadBatch = QtCore.pyqtSignal()

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(12)
        layout.setContentsMargins(24, 24, 24, 24)

        welcome = QtWidgets.QLabel('Bienvenido a <span style="color: #0c8ce9;">HICutter</span>')
        welcome.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        welcome_font = welcome.font()
        welcome_font.setPointSize(27)
        welcome_font.setBold(True)
        welcome.setFont(welcome_font)
        welcome.setStyleSheet('background-color: transparent')

        label = QtWidgets.QLabel('Selecciona la opcion de carga para iniciar el procesamiento')
        label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        label_font = label.font()
        label_font.setPointSize(20)
        label_font.setBold(False)
        label.setFont(label_font)
        label.setStyleSheet('background-color: transparent')

        btn_batch = QtWidgets.QPushButton('Cargar Lote')
        btn_batch_font = btn_batch.font()
        btn_batch_font.setPointSize(16)
        btn_batch_font.setBold(False)
        btn_batch.setFont(btn_batch_font)
        btn_batch.setMinimumHeight(50)
        btn_batch.setFixedWidth(300)
        btn_batch.setStyleSheet('background-color: #1E1E1E; color: #ffffff; border: 3px solid #0c8ce9; border-radius: 6px; padding: 8px;')
        btn_batch.clicked.connect(lambda: self.requestLoadBatch.emit())

        btn_image = QtWidgets.QPushButton('Cargar Imagen')
        btn_image_font = btn_image.font()
        btn_image_font.setPointSize(16)
        btn_image_font.setBold(False)
        btn_image.setFont(btn_image_font)
        btn_image.setMinimumHeight(50)
        btn_image.setFixedWidth(300)
        btn_image.setStyleSheet('background-color: #1E1E1E; color: #ffffff; border: 3px solid #0c8ce9; border-radius: 6px; padding: 8px;')
        btn_image.clicked.connect(lambda: self.requestLoadImage.emit())

        layout.addStretch(1)
        layout.addWidget(welcome)
        layout.addSpacing(15)
        layout.addWidget(label)
        layout.addSpacing(65)
        layout.addWidget(btn_image, alignment=QtCore.Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(btn_batch, alignment=QtCore.Qt.AlignmentFlag.AlignHCenter)
        layout.addStretch(1)

        #Agregamos el boton de configuracion de formato
        self.btn_settings = QtWidgets.QToolButton(self)
        self.btn_settings.setText("⚙️")
        self.btn_settings.setToolTip("Configuracion de Exportacion y PDF")

        #Diseño CSS
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