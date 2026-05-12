import sys
import cv2
import numpy as np
import os
from PyQt6 import QtWidgets, QtGui, QtCore
from PyQt6.QtCore import QThreadPool

from core.batch_engine import BatchManager, BatchWorker
from core.processor import process_perspective_crop, rotate_image
from image_canvas import ImageCanvas
from ui.views.landing_view import LandingView
from utils.logger import setup_logger
from core.output_fmt import export_image, export_th
from utils.fmt_config import config_manager
from ui.components.editor_toolbar import EditorToolbar

logger = setup_logger(__name__)

class MainWindow(QtWidgets.QMainWindow):
	def __init__(self) -> None:
		super().__init__()
		self.setWindowTitle('HICutter - Historical Image Cutter')

		# Stacked widget: 0 = LandingView, 1 = ImageCanvas (editor)
		self.stack = QtWidgets.QStackedWidget()
		self.landing = LandingView()
		self.canvas = ImageCanvas()
		self.stack.addWidget(self.landing)
		self.stack.addWidget(self.canvas)
		self.setCentralWidget(self.stack)
		self.current_image_path: str | None = None

		#Procesamiento por lote implementado desde Batch_engine
		self.is_batch_mode: bool = False
		self.batch_manager = BatchManager()
		self.thread_pool = QThreadPool()
		self.batch_manager.batch_finished.connect(self._on_batch_finished)
		logger.info(f"Multithreading list: {self.thread_pool.maxThreadCount()} hilos maximos")


		# Toolbar implementado desde "editor_toolbar.py"
		self.toolbar = EditorToolbar(self)
		self.addToolBar(self.toolbar)
		
		#Conectamos las "señales" enviadas desde "editor_toolbar.py"
		self.toolbar.sig_reset_requested.connect(self.canvas.reset_points)
		self.toolbar.sig_rotate_right_requested.connect(lambda: self._apply_rotation("derecha"))
		self.toolbar.sig_rotate_left_requested.connect(lambda: self._apply_rotation("izquierda"))
		self.toolbar.sig_rotate_180_requested.connect(lambda: self._apply_rotation("180"))
		self.toolbar.sig_cancel_requested.connect(self.cancel_operation)

		# Atajos globales
		self.shortcut_return = QtGui.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key.Key_Return), self)
		self.shortcut_return.activated.connect(self._on_enter_key)
		self.shortcut_enter = QtGui.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key.Key_Enter), self)
		self.shortcut_enter.activated.connect(self._on_enter_key)
		self.shortcut_alt2 = QtGui.QShortcut(QtGui.QKeySequence("alt+2"), self)
		self.shortcut_alt2.activated.connect(self._on_enter_key)

		# Conectar la señal de la LandingView para abrir imagen
		try:
			self.landing.requestLoadImage.connect(self._handle_request_load_image)
		except Exception:
			logger.error("No se conecto el procesamiento de imagen individual",exc_info=True)

		# Conectar la señal de la configuracion del procesamiento por lotes
		try:
			self.landing.requestLoadBatch.connect(self._start_batch_workflow)
		except Exception:
			logger.error("No se conecto batch_setup_dialog", exc_info=True)

		# Actualizar estado del toolbar cuando cambia la vista
		self.stack.currentChanged.connect(lambda idx: self.update_toolbar_state(idx == 1))
		# Mostrar la LandingView inicialmente
		self.stack.setCurrentIndex(0)
		self.update_toolbar_state(False)

	def load_image(self, path: str | None = None) -> None:
		# Si se proporciona `path`, úsalo; si no, abrir dialogo de archivo
		if path is None:
			fname, _ = QtWidgets.QFileDialog.getOpenFileName(self, 'Abrir imagen', 'input', 'Images (*.png *.jpg *.jpeg *.bmp *.tif *.tiff)')
			if not fname:
				QtWidgets.QMessageBox.information(self, 'Aviso', 'No se selecciono ninguna carpeta')
				return
		else:
			fname = path
		img = cv2.imread(fname)
		if img is None:
			QtWidgets.QMessageBox.warning(self, 'Error', 'No se pudo cargar la imagen')
			return
		self.current_image_path = fname
		self.canvas.load_image(cv_image=img)
		# Cambiar a la vista del editor
		self.stack.setCurrentIndex(1)


	def on_four_points(self, pts) -> None:
		# pts es un numpy.ndarray shape (4,2) en coordenadas de la imagen (float32)
		print('4 puntos seleccionados (imagen coords):')
		print(pts)
		
	def _on_enter_key(self) -> None:
		# Ejecuta save_points si hay 4 puntos seleccionados
		pts = self.canvas.get_points()
		if pts.shape[0] == 4:
			if self.is_batch_mode:
				self._process_batch_image() #<- Ejecutamos guardado de forma asincrona (lotes)
			else:
				self.save_points()#<- Ejecutamos guardado de forma sincrona (1 imagen)

	def _handle_request_load_image(self, *args) -> None:
		# Wrapper that accepts optional path from LandingView signal
		path = args[0] if args else None
		self.load_image(path)

	def _apply_rotation(self, direction_rotate: str) -> None:
		"""Se aplica la rotacion (via processor.rotate_image) y recarga la imagen via canvas"""
		if self.canvas.cv_image is None:
			return
		rotated = rotate_image(self.canvas.cv_image, direction_rotate)
		# reload the rotated image into the canvas
		self.canvas.load_image(cv_image=rotated)

	def update_toolbar_state(self, editor_active: bool) -> None:
		'''Activa/desactiva las heramientas si hay o no imagen cargada'''
		try:
			#Apagamos o encendemos la toolbar
			self.toolbar.set_editor_active(editor_active)
		except Exception:
			logger.error("Error al activar/desactivar la toolbar", exc_info=True)
		
		try:
			#Apagamos o encendemos los shortcuts
			self.shortcut_enter.setEnabled(editor_active)
			self.shortcut_return.setEnabled(editor_active)
			self.shortcut_alt2.setEnabled(editor_active)
		except Exception:
			logger.warning("LA funcionalidad de 'Shortcuts' no fue activada/ desactivada correctamente", exc_info=True)

	def _start_batch_workflow(self):
		from ui.views.batch_setup_dialog import BatchSetupDialog
		dialog = BatchSetupDialog(self)
		if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
			carpeta_entrada, carpeta_salida = dialog.get_directories()
			
			# Le damos la carpeta al administrador de carpetas
			if self.batch_manager.load_directory(carpeta_entrada):
				self.is_batch_mode = True
				logger.info(f"Lote iniciado: {len(self.batch_manager.image_files)} fotos en cola")
				#Cargamos la primera foto
				self._load_next_batch_image()
			else:
				self.is_batch_mode = False
				QtWidgets.QMessageBox.warning(self, "Error", "No se encontraron imagenes validas en la carpeta de entrada")
				self._start_batch_workflow()

	def _load_next_batch_image(self):
		"""Pide la siguiente imagen al manager y la carga en el canvas"""
		next_path =self.batch_manager.get_next_image()

		if next_path:
			img = cv2.imread(next_path)
			if img is not None:
				self.current_image_path = next_path
				#Le pasamos la info al HUD
				nombre_archivo = os.path.basename(next_path)
				progreso = f"[{self.batch_manager.current_index}/{len(self.batch_manager.image_files)}]"
				self.canvas.set_hud_info(nombre_archivo, progreso)
				self.canvas.load_image(cv_image=img)
				self.stack.setCurrentIndex(1)
			else:
				logger.error(f"imagen corrupt: {next_path}", exc_info=True)
				self.batch_manager.record_error(next_path, "No se pudo leer el archivo con OpenCV")
				self._load_next_batch_image()
		else:
			#Si next_path es None, significa que la cola esta vacia
			#Esperamos a que los hilos terminen anuncioando con un mensaje al usuario
			# Mostramos un Pop-Up Indeterminado que NO tiene botón de cancelar ni de OK.
			self.wait_dialog = QtWidgets.QProgressDialog("Guardando las últimas imágenes...", None, 0, 0, self)
			self.wait_dialog.setWindowTitle("Procesando")
			self.wait_dialog.setWindowModality(QtCore.Qt.WindowModality.WindowModal) # Bloquea la ventana detrás
			self.wait_dialog.setCancelButton(None) # Le quitamos el botón cancelar
			self.wait_dialog.show()

	def _process_batch_image(self):
		'''Procesa el trabajo de guardado de forma asincrona'''
		if self.canvas.cv_image is None or self.current_image_path is None:
			logger.warning("Error de procesamiento de guardado en canvas o image_path", exc_info=True)
			return

		pts = self.canvas.get_points().astype(np.float32)
		cv_img_copy = self.canvas.cv_image.copy() #<-Copia de seguridad
		file_path = self.current_image_path
		#Creamos al obrero
		worker = BatchWorker(cv_img_copy, pts, file_path)
		#Conectamos las señales
		worker.signals.finished.connect(self.batch_manager.record_success)
		worker.signals.error.connect(self.batch_manager.record_error)
		#Lo mandamos a un hilo aparte
		self.thread_pool.start(worker)
		#Cargamos la siguiente imagen
		self._load_next_batch_image()

	def _on_batch_finished(self, success_list: list, error_list: list):
		'''Se ejecuta cuando el ultimo obrero termina de guardar'''
		#Cerramos el cuadro de dialogo de carga del "_load_next_batch_image"
		if hasattr(self, 'wait_dialog') and self.wait_dialog:
			self.wait_dialog.close()
		#Limpiamos el canvas de la imagen y el HUD
		self.canvas.set_hud_info("","")
		self.canvas.unload_image()
		#Limpiamos variables de estado
		self.current_image_path = None
		self.is_batch_mode = False
		'''Aqui cambiara el index a otra pestaña para mostrar el resumen, pero de momento regresa al menu inicial'''
		self.stack.setCurrentIndex(0)

	def save_points(self) -> None:
		"""Guarda la imagen procesada preguntando primero el destino.
					(Procesamiento de una sola imagen)"""
		
		pts = self.canvas.get_points()
		if pts.shape[0] != 4:
			QtWidgets.QMessageBox.warning(self, 'Aviso', 'Faltan puntos (se requieren 4)')
			return

		if self.canvas.cv_image is None:
			QtWidgets.QMessageBox.warning(self, 'Error', 'No hay imagen cargada')
			return

		# puntos ordenados en coordenadas de la imagen (float32)
		src = pts.astype(np.float32)

		try:
			warped = process_perspective_crop(self.canvas.cv_image, src)
		except ValueError as e:
			QtWidgets.QMessageBox.warning(self, 'Error', str(e) if str(e) else 'Dimensiones inválidas para el recorte')
			return

		'''Incluimos metodo de guardado a travez de "core/output_fmt.py"'''
		#Configuramos la ruta de salida dependiendo preferencias de usuario
		try:
			use_preset_dir = config_manager.get("paths","use_preset_dir")
			pre_set_output_dir = config_manager.get("paths", "pre_set_output_dir")
			last_dir = config_manager.get("paths", "last_dir")

			if use_preset_dir and pre_set_output_dir:
				folder_path = pre_set_output_dir
			
			elif pre_set_output_dir:
				folder_path = QtWidgets.QFileDialog.getExistingDirectory(self, "Seleccionar carpeta para guardar recortes", pre_set_output_dir)
				#Por si el usuario presiona "cancelar" 
				if not folder_path:
					return
			else:
				folder_path = QtWidgets.QFileDialog.getExistingDirectory(self, "Seleccionar carpeta para guardar recortes", pre_set_output_dir or last_dir)
				if not folder_path:
					return
			
			config_manager.set("paths", "last_dir", folder_path)
		except Exception:
			logger.error("Error al configurar ruta de exportacion",exc_info=True)
			QtWidgets.QMessageBox.warning(self, "Error", "No se pudo configurar la ruta de exportacion\n Vuelva a intentar o reinicie la aplicacion")

		# Obtenemos el nombre del archivo
		base_name = "crop_temp.jpg"
		if getattr(self,"current_image_path", None):
			base_name = os.path.basename(self.current_image_path)
		
		# Delegamos la exportacion a core/output_fmt.py
		try:
			export_image(warped, base_name)

		except Exception as e:
			logger.error("Error al Exportar imagen recortada", exc_info=True)
			QtWidgets.QMessageBox.warning(self, "Error", "No se pudo exportar la imagen recortada (revise logs)")
		
		try:
			export_th_is_enabled = config_manager.get("export_th", "enabled")
			if export_th_is_enabled:
				export_th(warped, base_name)
				
		except Exception:
			logger.error("Error al Exportar formato TH", exc_info=True)
			QtWidgets.QMessageBox.warning(self, "Error", "No se pudo exportar la imagen para formato TH (revise logs)")

		try:
			self.canvas.unload_image()
			self.current_image_path = None
			QtWidgets.QMessageBox.information(self, "Aviso", f"Imagen guardada exitosamente en: \n{folder_path}")
			self.stack.setCurrentIndex(0)
		except Exception as e:
			logger.error("Error al regresar a la pagina de inicio", exc_info=True)
			QtWidgets.QMessageBox.warning(self, "Error", "No se pudo cargar la pagina de inicio, reinicie la aplicacion")
	
	def cancel_operation (self) -> None:
		'''Aborto seguro del procesamiento
		Confirma la operacion de aborto al usuario'''

		answer = QtWidgets.QMessageBox.question(
			self,
			"Confirmar cancelacion",
			"¿Estas seguro de cancelar el proceso actual y regresar a la pagina de inicio?\n" \
			"Nota: En procesamiento por lote, esta accion solo afecta a la imagen actual.\n" \
			"Las imagenes previas no se veran afectadas.",
			QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No, 
			QtWidgets.QMessageBox.StandardButton.No #<- Eleccion por defecto en caso de que se presione "enter"
		)
		if answer == QtWidgets.QMessageBox.StandardButton.No:
			return
		#Ejecutamos el codigo para limpiar el lienzo de forma correcta
		try:
			# Borramos la imagen de la memoria del Canvas
			self.canvas.unload_image()
			# Destruimos la referencia a la ruta original
			self.current_image_path = None
			# Cambiamos la vista a la pantalla Landing (índice 0)
			self.stack.setCurrentIndex(0)

			logger.info("Proceso cancelado por el usuario y redirijido a la paginia principal correctamente")
		except Exception:
			logger.error("Error al critico al intentar cancelar la operacion", exc_info=True)
			QtWidgets.QMessageBox.warning(self, "Error", "Error al limpiar la memoria, intente nuevamente")



def main() -> None:
	app = QtWidgets.QApplication(sys.argv)
	mw = MainWindow()
	mw.resize(1000, 700)
	mw.showMaximized()
	sys.exit(app.exec())


if __name__ == '__main__':
	main()