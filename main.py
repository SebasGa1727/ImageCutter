import sys
import cv2
import numpy as np
import os
import gc
from PyQt6 import QtWidgets, QtGui, QtCore
from PyQt6.QtCore import QThreadPool, QRunnable, pyqtSignal, QObject

from core.batch_engine import BatchManager, BatchWorker, PreloadWorker
from core.processor import process_perspective_crop, rotate_image
from core.output_pdf_fmt import export_to_pdf
from core.converter_engine import ProxyManager
from image_canvas import ImageCanvas
from ui.views.landing_view import LandingView
from utils.logger import setup_logger
from core.output_fmt import export_image, export_th
from utils.fmt_config import config_manager
from ui.components.editor_toolbar import EditorToolbar
from ui.views.batch_summary_view import BatchSummaryView

# @ Created by SGV.dev

logger = setup_logger(__name__)

class PDFWorkerSignals(QObject):
	'''Establecemos las señales para el worjer de PDF'''
	finished = pyqtSignal(str) #<- Devuelve la ruta final del PDF
	error = pyqtSignal(str)

class PDFWorker(QRunnable):
	'''Hilo de trabajo (Worker) para generar PDF en segundo plano'''
	def __init__(self, ordered_paths: list[str], output_filename: str):
		super().__init__()
		self.ordered_paths = ordered_paths
		self.output_filename = output_filename
		self.signals = PDFWorkerSignals()
	
	def run(self):
		try:
			final_path = export_to_pdf(self.ordered_paths, self.output_filename)
			self.signals.finished.emit(final_path)
		except Exception as e:
			self.signals.error.emit(str(e))

class MainWindow(QtWidgets.QMainWindow):
	def __init__(self) -> None:
		super().__init__()
		self.setWindowTitle('HICutter - Historical Image Cutter by SGV.dev')

		# Stacked widget: 0 = LandingView, 1 = ImageCanvas (editor), 2= BatchSummaryView
		self.stack = QtWidgets.QStackedWidget()
		self.landing = LandingView()
		self.canvas = ImageCanvas()
		self.summary_view = BatchSummaryView()
		self.stack.addWidget(self.landing)
		self.stack.addWidget(self.canvas)
		self.stack.addWidget(self.summary_view)
		self.setCentralWidget(self.stack)
		self.current_image_path: str | None = None

		# Motor de proxies
		self.proxy_manager = ProxyManager()
		self.proxy_manager.progress.connect(self._on_proxy_progress)
		self.proxy_manager.finished.connect(self._on_proxy_finished)
		self.proxy_manager.error.connect(self._on_proxy_error)
		self.proxy_wait_dialog = None

		#Procesamiento por lote implementado desde Batch_engine
		self.is_batch_mode: bool = False
		self.batch_manager = BatchManager()
		#Gestores de hilos para precesamiento asincrono y lectura de imagen asincrona en 2 vias
		self.cpu_pool = QThreadPool()
		# Pool para lectura de disco, limitado a solo 1 nucleo
		self.io_pool = QThreadPool()
		self.io_pool.setMaxThreadCount(1)
		#Buffer de cache - "Look ahead" para la lectura de la imagen futura
		self.next_image_buffer: np.ndarray | None = None
		self.next_image_path_buffer: str | None = None
		self.next_image_error: tuple[str, str] | None = None
		#Banderas de control de estado asincrono
		self._is_preloading: bool = False
		self._waiting_for_preload: bool = False
		self.batch_manager.batch_finished.connect(self._on_batch_finished)
		self.parent_folder_name: str = ""

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
		self.KEY_ENTER: list =["Return", "Enter", "alt+2"] 
		self.shortcut_return = QtGui.QShortcut(QtGui.QKeySequence(self.KEY_ENTER[0]), self)
		self.shortcut_return.activated.connect(self._on_enter_key)
		self.shortcut_enter = QtGui.QShortcut(QtGui.QKeySequence(self.KEY_ENTER[1]), self)
		self.shortcut_enter.activated.connect(self._on_enter_key)
		self.shortcut_alt2 = QtGui.QShortcut(QtGui.QKeySequence(self.KEY_ENTER[2]), self)
		self.shortcut_alt2.activated.connect(self._on_enter_key)

		#Señales del canvas 
		self.canvas.sig_save_requested.connect(self._on_enter_key)

		#Señales del batch summary view
		self.summary_view.request_continue.connect(self._on_summary_continue)

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

	#Metodos del proxy
	def _on_proxy_progress(self, actuales: int, totales: int, mensaje: str):
		'''Recibe actualizaciones del obrero de la bobeda'''
		if hasattr(self, 'proxy_wait_dialog') and self.proxy_wait_dialog:
			self.proxy_wait_dialog.setMaximum(totales)
			self.proxy_wait_dialog.setValue(actuales)
			self.proxy_wait_dialog.setLabelText(mensaje)

	def _on_proxy_finished(self, final_list: list[str]):
		'''Se ejecuta cuando la bobeda termino de procesar todas las imagenes'''
		#Quitamos la pantalla de carga
		if hasattr(self, 'proxy_wait_dialog') and self.proxy_wait_dialog:
			try:
				self.proxy_wait_dialog.canceled.disconnect()
			except Exception:
				pass
			self.proxy_wait_dialog.hide()
			self.proxy_wait_dialog.deleteLater()
			self.proxy_wait_dialog = None
		
		#Pasamos la lista limpia de puros jpg
		if self.batch_manager.set_files(final_list):
			self.is_batch_mode = True
			logger.info(f"Lote iniciado: {len(self.batch_manager.image_files)} fotos en cola")
			self._load_next_batch_image(force_sync= True)
		else:
			self.is_batch_mode = False
			QtWidgets.QMessageBox.warning(self, "Aviso", "No se encontraron imágenes válidas en la carpeta.")

	def _on_proxy_error(self, err_msg: str):
		'''Error de procesamiento de proxys'''
		if hasattr(self, 'proxy_wait_dialog') and self.proxy_wait_dialog:
			try:
				self.proxy_wait_dialog.canceled.disconnect()
			except Exception:
				pass
			self.proxy_wait_dialog.hide()
			self.proxy_wait_dialog.deleteLater()
			self.proxy_wait_dialog = None
		QtWidgets.QMessageBox.critical(self, "Error de Carpeta", err_msg)	

	def _cancel_proxies(self):
		'''Proceso si el usuario cancela mientras se crea el proxy'''
		self.proxy_manager.cancel()
		self.cancel_operation(prompt_user=False)

		if hasattr(self, 'proxy_wait_dialog') and self.proxy_wait_dialog:
			self.proxy_wait_dialog.hide()
			self.proxy_wait_dialog.deleteLater()
			self.proxy_wait_dialog = None
		self.is_batch_mode = False
		logger.info("El usuario canceló la generación de proxies.")

	# Metodos para cargar la imagen y flujo de trabajo
	def load_image(self, path: str | None = None) -> None:
		# Si se proporciona `path`, úsalo; si no, abrir dialogo de archivo
		if path is None:
			fname, _ = QtWidgets.QFileDialog.getOpenFileName(self, 'Abrir imagen', 'input', 'Images (*.png *.jpg *.jpeg *.bmp *.cr2 *.tif *.tiff)')
			if not fname:
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
			logger.warning("LA funcionalidad de 'Shortcuts' no fue activada/desactivada correctamente", exc_info=True)

	# Metodos para trabajo asincrono del modo lote
	def _start_batch_workflow(self):
		from ui.views.batch_setup_dialog import BatchSetupDialog
		dialog = BatchSetupDialog(self)
		if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
			carpeta_entrada, carpeta_salida = dialog.get_directories()
			self.parent_folder_name = os.path.basename(os.path.normpath(carpeta_entrada))

			# Lanzamos el Diálogo nativo de carga. (Luego lo cambiaremos por la UI bonita)
			self.proxy_wait_dialog = QtWidgets.QProgressDialog("Analizando bóveda de archivos...", "Cancelar", 0, 100, self)
			self.proxy_wait_dialog.setWindowTitle("Convirtiendo imagenes a JPG")
			self.proxy_wait_dialog.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
			self.proxy_wait_dialog.setAutoClose(False)
			self.proxy_wait_dialog.setAutoReset(False)
			self.proxy_wait_dialog.canceled.connect(self._cancel_proxies)
			self.proxy_wait_dialog.show()

			# Mandamos al orquestador a escanear y generar proxies de ser necesario
			self.proxy_manager.process_directory(carpeta_entrada)

	def _load_next_batch_image(self, force_sync: bool = False):
		"""Orquesta la extracción de imágenes, priorizando la memoria RAM (Buffer)."""
		
		# CASO A: Primera imagen o lectura forzada (I/O Síncrono)
		if force_sync:
			path = self.batch_manager.get_next_image()
			if not path:
				return
			
			img = cv2.imread(path)
			if img is not None:
				self._render_image_to_canvas(path, img)
				self._trigger_preload()
			else:
				self.batch_manager.record_error(path, "Lectura síncrona fallida.")
				self._load_next_batch_image(force_sync=True)
			return

		# CASO B: El usuario fue más rápido que el disco duro
		if self._is_preloading:
			# Levantamos la bandera de espera. El callback lo procesará en cuanto termine.
			self._waiting_for_preload = True
			QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.CursorShape.WaitCursor)
			return

		# CASO C: Error en la precarga (Manejo de UX)
		if self.next_image_error is not None:
			err_path, err_msg = self.next_image_error
			self.next_image_error = None # Vaciamos el error
			
			self.batch_manager.record_error(err_path, err_msg)
			
			msg_box = QtWidgets.QMessageBox(self)
			msg_box.setIcon(QtWidgets.QMessageBox.Icon.Warning)
			msg_box.setWindowTitle("Error en el archivo")
			msg_box.setText(f"No se pudo leer la siguiente imagen:\n{err_path}\n\n¿Qué deseas hacer?")
			
			btn_continuar = msg_box.addButton("Continuar con la siguiente", QtWidgets.QMessageBox.ButtonRole.AcceptRole)
			btn_abortar = msg_box.addButton("Abortar Lote", QtWidgets.QMessageBox.ButtonRole.RejectRole)
			msg_box.exec()
			
			if msg_box.clickedButton() == btn_abortar:
				self.cancel_operation(prompt_user=False)
			else:
				# Si decide continuar, forzamos lectura de la siguiente para brincarnos la corrupta
				self._load_next_batch_image(force_sync=True)
			return

		# CASO D: Final del Lote (Buffer vacío y el hilo no está trabajando)
		if self.next_image_buffer is None:
			self._finish_batch_ui()
			return

		# CASO E: Swap de Memoria Instantáneo (Éxito Nominal)
		img, scaled_qimg = self.next_image_buffer
		path = self.next_image_path_buffer
		
		# Propiedad estricta: Limpiamos el buffer para prevenir Memory Leaks
		self.next_image_buffer = None
		self.next_image_path_buffer = None
		
		self._render_image_to_canvas(path, img, scaled_qimg)
		self._trigger_preload()

	def _render_image_to_canvas(self, path: str, img: np.ndarray, scaled_qimg: QtGui.QImage = None):
		"""Inyecta la matriz al canvas y actualiza el HUD"""
		self.current_image_path = path
		nombre_archivo = os.path.basename(path)
		
		# Calculamos el progreso basado en el archivo actual de la lista que esta trabajando
		try:
			indice = self.batch_manager.image_files.index(path)
			progress = f"{indice + 1}/{len(self.batch_manager.image_files)}"
		except ValueError:
			progress = f"?/{len(self.batch_manager.image_files)}"
		
		self.canvas.set_hud_info(nombre_archivo, progress)
		self.canvas.load_image(cv_image=img, pre_scaled_qimage=scaled_qimg)
		self.stack.setCurrentIndex(1)

	def _trigger_preload(self):
		"""Calcula cuál es la siguiente foto y lanza el hilo de lectura."""
		next_path = self.batch_manager.get_next_image()
		
		if next_path:
			self._is_preloading = True
			preload_worker = PreloadWorker(next_path, self.canvas.size())
			preload_worker.signals.finished.connect(self._on_preload_success)
			preload_worker.signals.error.connect(self._on_preload_error)
			self.io_pool.start(preload_worker)
		else:
			logger.info("No hay más imágenes para precargar.")

	def _on_preload_success(self, img: object, scaled_qimg: object, path: str):
		"""Callback asíncrono. Guarda la matriz en la RAM y gestiona la condición de carrera."""

		self.next_image_buffer = (img, scaled_qimg)
		self.next_image_path_buffer = path
		self.next_image_error = None
		self._is_preloading = False
		
		# Si el usuario estaba esperando, quitamos el reloj de arena y forzamos el cargado
		if self._waiting_for_preload:
			self._waiting_for_preload = False
			QtWidgets.QApplication.restoreOverrideCursor()
			self._load_next_batch_image()

	def _on_preload_error(self, path: str, err_msg: str):
		"""Callback asíncrono. Registra el fallo para ser notificado cuando el usuario llegue a esa foto."""
		self.next_image_buffer = None
		self.next_image_path_buffer = None
		self.next_image_error = (path, err_msg)
		self._is_preloading = False
		
		if self._waiting_for_preload:
			self._waiting_for_preload = False
			QtWidgets.QApplication.restoreOverrideCursor()
			self._load_next_batch_image()

	def _finish_batch_ui(self):
		"""Despliega el diálogo de cierre esperando a que los obreros de la CPU terminen."""
		self.wait_dialog = QtWidgets.QProgressDialog("Guardando las últimas imágenes...", None, 0, 0, self)
		self.wait_dialog.setWindowTitle("Procesando")
		self.wait_dialog.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
		self.wait_dialog.setCancelButton(None)
		self.wait_dialog.show()

	def _process_batch_image(self):
		'''Procesa el trabajo de guardado de forma asincrona'''
		if self.canvas.cv_image is None or self.current_image_path is None:
			logger.warning("Error de procesamiento de guardado en canvas o image_path", exc_info=True)
			return

		pts = self.canvas.get_points().astype(np.float32)
		file_path = self.current_image_path
		#Creamos al obrero
		worker = BatchWorker(self.canvas.cv_image, pts, file_path, self.parent_folder_name)
		#Conectamos las señales
		worker.signals.finished.connect(self.batch_manager.record_success)
		worker.signals.error.connect(self.batch_manager.record_error)
		#Lo mandamos a un hilo aparte
		self.cpu_pool.start(worker)
		# Descargamos la imagen vieja del canvas. Esto borra la matriz principal 
		# y el pixmap de la interfaz antes de leer la nueva desde el disco.
		self.canvas.unload_image()
		#Cargamos la siguiente imagen
		self._load_next_batch_image()

	def _on_batch_finished(self, success_list: list, error_list: list):
		'''Se ejecuta cuando el ultimo obrero termina de guardar'''
		#Limpiamos el canvas
		self.canvas.set_hud_info("","")
		self.canvas.unload_image()
		self.current_image_path = None
		self.is_batch_mode = False
		#Limpieza de bufer post lote
		self.next_image_buffer = None
		self.next_image_path_buffer = None
		self.next_image_error = None
		gc.collect()

		#Cargamos los datos de las listas
		self.summary_view.load_summary_data(success_list, error_list)

		#Cambiamos la vista a nuestro summary view
		self.stack.setCurrentIndex(2)

		if hasattr(self, 'wait_dialog') and self.wait_dialog:
			self.wait_dialog.close()

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
			
			else:
				# Si no hay preset estricto, abrimos el diálogo apuntando a la última ruta conocida
				directorio_inicial = pre_set_output_dir if pre_set_output_dir else last_dir
				folder_path = QtWidgets.QFileDialog.getExistingDirectory(self, "Seleccionar carpeta para guardar recortes", directorio_inicial)
				if not folder_path:
					return
			
			config_manager.set("paths", "last_dir", folder_path)
		except Exception:
			logger.error("Error al configurar ruta de exportacion",exc_info=True)
			QtWidgets.QMessageBox.warning(self, "Error", "No se pudo configurar la ruta de exportacion\n Vuelva a intentar o reinicie la aplicacion")

		# Obtenemos el nombre del archivo
		base_name = "crop_temp.jpg"
		parent_folder_name = ""
		if getattr(self,"current_image_path", None):
			base_name = os.path.basename(self.current_image_path)
			#Extraemos solo el nombre de donde se extrajeron las imagenes para poder crear la misma carpeta en al salida
			parent_folder_name = os.path.basename(os.path.dirname(self.current_image_path)) 

		# Delegamos la exportacion a core/output_fmt.py
		try:
			export_image(warped, base_name, parent_folder_name)

		except Exception as e:
			logger.error("Error al Exportar imagen recortada", exc_info=True)
			QtWidgets.QMessageBox.warning(self, "Error", "No se pudo exportar la imagen recortada (revise logs)")
		
		try:
			export_th_is_enabled = config_manager.get("export_th", "enabled")
			if export_th_is_enabled:
				export_th(warped, base_name, parent_folder_name)
				
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
	
	def cancel_operation (self, prompt_user: bool = True) -> None:
		'''Aborto seguro del procesamiento'''
		'''Confirma la operacion de aborto al usuario'''
		if prompt_user:
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
			#Desactivamos el modo lote
			self.is_batch_mode = False
			#Destruimos todo rastro de la memoria en espera
			self.next_image_buffer = None
			self.next_image_path_buffer = None
			self.next_image_error = None
			gc.collect()
			# Cambiamos la vista a la pantalla Landing (índice 0)
			self.stack.setCurrentIndex(0)

			logger.info("Proceso cancelado y memorias liberadas, de vuelta en pagina de inicio")
		except Exception:
			logger.error("Error al critico al intentar cancelar la operacion", exc_info=True)
			QtWidgets.QMessageBox.warning(self, "Error", "Error al limpiar la memoria, intente nuevamente")

	def _on_summary_continue(self, with_th: bool, th_image_path: str) -> None:
		'''Recibe la señal del batchsummary cuando el usuario confirma el lote'''
		#Recibimos la lista ordenada por la UI del usaurio
		ordered_paths = []
		for i in range(self.summary_view.list_widget.count()):
			# Sacamos el dato oculto (la ruta completa real)
			real_path = self.summary_view.list_widget.item(i).data(QtCore.Qt.ItemDataRole.UserRole)
			ordered_paths.append(real_path)

		if with_th and th_image_path:
			logger.info(f"El usuario creo TH para su lote")
			try:
				img_to_th = cv2.imread(th_image_path)
				if img_to_th is not None:
					base_name = os.path.basename(th_image_path)
					export_th(img_to_th, base_name, self.parent_folder_name)
			except Exception:
				logger.error("Error al intentar crear TH en procesamiento por lote", exc_info=True)
				QtWidgets.QMessageBox.warning(self, "Error de procesamiento", "Error al querer generar el TH")
		
		logger.info("inicializando generacion de PDF")
		
		# Mostramos pantalla de carga
		self.pdf_wait_dialog = QtWidgets.QProgressDialog("Ensamblando documento PDF, por favor espere...", None, 0, 0, self)
		self.pdf_wait_dialog.setWindowTitle("Generando PDF")
		self.pdf_wait_dialog.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
		self.pdf_wait_dialog.setCancelButton(None)
		self.pdf_wait_dialog.show()
		
		# Determinamos el nombre de la carpeta final (El nombre de la carpeta de extraccion)
		pdf_name = self.parent_folder_name if self.parent_folder_name else "PDF_exportado_por_HICutter"

		pdf_worker = PDFWorker(ordered_paths, pdf_name)
		pdf_worker.signals.finished.connect(self._on_pdf_success) 
		pdf_worker.signals.error.connect(self._on_pdf_error) 

		self.cpu_pool.start(pdf_worker)
	
	# Metodos para la creacion del PDF
	def _on_pdf_success(self, final_path: str):
		if hasattr(self, 'pdf_wait_dialog') and self.pdf_wait_dialog:
			self.pdf_wait_dialog.close()

			QtWidgets.QMessageBox.information(
				self,
				"PDF Generado exitosamente",
				f"El PDF ha sido generado exitosamente en:\n{final_path}"
				)
		self.stack.setCurrentIndex(0)

	def _on_pdf_error(self, e: str):
		if hasattr(self, 'pdf_wait_dialog') and self.pdf_wait_dialog:
			self.pdf_wait_dialog.close()
		logger.error("Error critico creando el PDF", exc_info=True)
		QtWidgets.QMessageBox.critical(
			self,
			"Error Critico",
			f"No se pudo gnerar el PDF\n\n{e}")
		
		self.stack.setCurrentIndex(0)

def main() -> None:
	app = QtWidgets.QApplication(sys.argv)
	mw = MainWindow()
	mw.resize(1000, 700)
	mw.showMaximized()
	sys.exit(app.exec())

if __name__ == '__main__':
	main()