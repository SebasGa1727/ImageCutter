from __future__ import annotations

from typing import List, Optional, Tuple

import numpy as np
from PyQt6 import QtCore, QtGui, QtWidgets
from ui.components.geometry import ScaledPixmapManager
from ui.components.point_manager import PointManager
from ui.components.magnifier import MagnifierTool
from ui.components.sniper_mode import SniperModeManager
from utils.utils import _cv_to_qpixmap


class ImageCanvas(QtWidgets.QWidget):
    """Widget para mostrar una imagen y recoger 4 puntos de control.

    - Usa QPixmap para el renderizado (alta calidad) y mantiene la imagen OpenCV
      original en `self.cv_image`.
    - Emite la señal `fourPointsSelected` cuando el usuario ha seleccionado 4 puntos
      (coordenadas en el espacio de la imagen, formato float32, shape (4,2)).
    - Click izquierdo: añade punto (si está sobre la imagen). Click derecho: borra
      el último punto. Doble click con el botón izquierdo reinicia la selección.
    """
    fourPointsSelected = QtCore.pyqtSignal(object)
    

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(320, 240)

        self.cv_image: Optional[np.ndarray] = None
        self._pixmap: Optional[QtGui.QPixmap] = None
        # helpers
        self._scaled_manager = ScaledPixmapManager()
        self._point_manager = PointManager()

        # interacción/cursor
        self.setMouseTracking(True)
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        self._mouse_in_img: bool = False
        self._mouse_wx: int = 0
        self._mouse_wy: int = 0
        self.cross_len: int = 10
        self.cross_color = QtGui.QColor(12, 140, 233)
        self.line_color = QtGui.QColor(0, 0, 0)
        self.cross_width: int = 2
        self._cross_cursor = self._create_cross_cursor(self.cross_len)
        # Caché del pixmap escalado está gestionada por `ScaledPixmapManager`
        # valores para la Lupa de enfoque 
        MAG_SIZE = 250
        MAG_ZOOM = 1.7
        MAG_BORDER = 2
        MAG_OFFSET = 60
        self._magnifier_enabled: bool = False
        self._magnifier = MagnifierTool(size=MAG_SIZE, zoom=MAG_ZOOM, border=MAG_BORDER, offset=MAG_OFFSET)
        # Modo sniper/precisión
        SNIPER_SENSITIVITY = 0.06
        self._sniper = SniperModeManager(sensitivity=SNIPER_SENSITIVITY)


    def _toggle_magnifier(self) -> None:
        self._magnifier_enabled = not self._magnifier_enabled
        self.update()

    # ---------- Carga y conversión
    def load_image(self, path: Optional[str] = None, cv_image: Optional[np.ndarray] = None) -> None:
        """Recibe una matriz de OpenCV (BGR) y la prepara para renderizado visual.
        El Canvas no lee archivos locales, solo procesa datos en memoria.
        """
        if cv_image is None:
            raise ValueError("Se recibio un cv_image vacio o nulo")
        # Copiamos la matriz para evitar que modificaciones externas dañen la vista
        self.cv_image = cv_image.copy()
        # Delegamos la conversión de colores BGR a RGB y a formato Qt
        self._pixmap = _cv_to_qpixmap(self.cv_image)
        # actualizar la referencia del manager
        self._scaled_manager.set_pixmap(self._pixmap)
        # actualizar caché escalado
        self._update_scaled_pixmap_cache()
        # Reiniciamos las herramientas de dibujo
        self._point_manager.reset()
        self.update()


    def _create_cross_cursor(self, cross_len: int) -> QtGui.QCursor:
        """Crea un QCursor con una cruceta roja centrada."""
        size = cross_len * 2 + 7
        pix = QtGui.QPixmap(size, size)
        pix.fill(QtGui.QColor(0, 0, 0, 0))
        painter = QtGui.QPainter(pix)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        pen = QtGui.QPen(self.cross_color)
        pen.setWidth(self.cross_width)
        pen.setCosmetic(True)
        painter.setPen(pen)
        center = size // 2
        painter.drawLine(center - cross_len, center, center + cross_len, center)
        painter.drawLine(center, center - cross_len, center, center + cross_len)
        painter.end()
        return QtGui.QCursor(pix, center, center)


    # ---------- Utilidades de mapeo coordenadas
    def _scaled_pixmap_and_offset(self) -> Tuple[Optional[QtGui.QPixmap], int, int]:
        """Devuelve (scaled_pixmap, left, top) para centrar la imagen en el widget.
        Usa caché `self._scaled_pixmap_cache` actualizada sólo en `load_image` y `resizeEvent`.
        """
        if self._pixmap is None:
            return None, 0, 0

        scaled, left, top = self._scaled_manager.get_scaled_and_offset()
        if scaled is None:
            self._update_scaled_pixmap_cache()
        return self._scaled_manager.get_scaled_and_offset()


    def _update_scaled_pixmap_cache(self) -> None:
        """Actualiza `self._scaled_pixmap_cache`, `left` y `top` en función
        del tamaño actual del widget y `self._pixmap`.
        Se debe llamar sólo en `load_image` y `resizeEvent`.
        """
        # Delegate scaled-cache computation to the manager
        self._scaled_manager.set_pixmap(self._pixmap)
        self._scaled_manager.update_scaled_cache(self.size())

    def widget_to_image_coords(self, wx: int, wy: int) -> Optional[Tuple[float, float]]:
        """Convierte coordenadas de widget (px) a coordenadas en la imagen (px).
        Retorna None si el punto está fuera del área de la imagen (margen negro alrededor).
        """
        return self._scaled_manager.widget_to_image_coords(wx, wy)

    def image_to_widget_coords(self, ix: float, iy: float) -> Optional[Tuple[int, int]]:
        return self._scaled_manager.image_to_widget_coords(ix, iy)

    # NOTE: Rotations are handled in the core and orchestrated by MainWindow.

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:
        # Actualizar el pixmap escalado cuando cambia el tamaño del widget
        self._update_scaled_pixmap_cache()
        super().resizeEvent(event)
        self.update()

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        """Handle keyboard shortcuts: 'l' toggles magnifier; Shift enters precision (sniper) mode.

        When Shift is pressed (non-autorepeat) we initialize the virtual cursor to the
        current mouse position, hide the system cursor and lock the system pointer to
        the widget center to allow infinite relative movement.
        """
        key = event.key()
        # Toggle magnifier
        if key == QtCore.Qt.Key.Key_A:
            self._magnifier_enabled = not self._magnifier_enabled
            self.update()
            return

        # Delegate sniper/precision handling
        handled, mwx, mwy = self._sniper.handle_key_press(event, self)
        if handled:
            if mwx is not None and mwy is not None:
                self._mouse_wx = mwx
                self._mouse_wy = mwy
            self.update()
            return

        super().keyPressEvent(event)

    def keyReleaseEvent(self, event: QtGui.QKeyEvent) -> None:
        """Maneja la liberación de Shift para salir del modo precisión.
        Evita el glitch del ratón teletransportando el cursor del SO a la posición virtual.
        """
        handled = self._sniper.handle_key_release(event, self)
        if handled:
            # Obtenemos la última coordenada (x, y) de tu cursor lento (Sniper)
            wfx, wfy = self._sniper.get_current_widget_pos(None, self)
            # Convertimos esa coordenada interna de la app a coordenadas absolutas del monitor
            global_pos = self.mapToGlobal(QtCore.QPoint(int(wfx), int(wfy)))
            # Obligamos al mouse físico de Windows a moverse a esa coordenada
            QtGui.QCursor.setPos(global_pos)

            self.update()
            return

        super().keyReleaseEvent(event)

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:
        """Rastrea la posición del cursor y actualiza el cursor cuando está sobre la imagen.

        Si `self._precision_mode` está activo, se usa `_virtual_cursor_pos` y el
        movimiento físico se captura como delta relativo desde el centro del widget
        (bloqueando el cursor en el centro con `QCursor.setPos`).
        """
        # Delegate sniper precision movement
        handled, mwx, mwy, min_img = self._sniper.handle_mouse_move(event, self)
        if handled:
            # update canvas state from sniper
            if mwx is not None and mwy is not None:
                self._mouse_wx = mwx
                self._mouse_wy = mwy
            if isinstance(min_img, bool):
                self._mouse_in_img = min_img
            self.update()
            return

        # Comportamiento normal cuando no hay modo precisión
        wx = int(event.position().x())
        wy = int(event.position().y())
        img_pt = self.widget_to_image_coords(wx, wy)
        # Solo seguir el cursor si aún no se han colocado los 4 puntos
        if img_pt is not None and len(self._point_manager) < 4:
             self._mouse_in_img = True
             self._mouse_wx = wx
             self._mouse_wy = wy
             # cambiar cursor a cruceta roja
             self.setCursor(self._cross_cursor)
        else:
            if self._mouse_in_img:
                self._mouse_in_img = False
                self.unsetCursor()
        # repintar para mostrar líneas punteadas de referencia
        self.update()

    # ---------- Interacción de usuario
    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            # Si estamos en modo precisión, usar la posición virtual (float) para mapear
            wfx, wfy = self._sniper.get_current_widget_pos(event, self)
            pt = self.widget_to_image_coords(wfx, wfy)
            if pt is None:
                return
            if len(self._point_manager) < 4:
                self._point_manager.add_point(pt)
                ordered = self._point_manager.finalize_if_full()
                # si alcanzamos 4 puntos, emitimos y dejamos de seguir el cursor
                if ordered is not None:
                    self.fourPointsSelected.emit(ordered)
                    # desactivar lupa y modo precisión al completar los 4 puntos
                    self._magnifier_enabled = False
                    self._sniper.deactivate(self)
                    self._mouse_in_img = False
                    self.unsetCursor()
                self.update()
        elif event.button() == QtCore.Qt.MouseButton.RightButton:
            # remove last
            if len(self._point_manager) > 0:
                self._point_manager.pop_last()
                # Si ahora hay menos de 4 puntos, el seguimiento volverá al moverse el mouse
                self.update()

    def mouseDoubleClickEvent(self, event: QtGui.QMouseEvent) -> None:
        # doble click reinicia puntos
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self._point_manager.reset()
            self.update()

    # ---------- Acceso a datos
    def get_points(self) -> np.ndarray:
        return self._point_manager.get_points()

    def reset_points(self) -> None:
        self._point_manager.reset()
        self.update()

    def unload_image(self) -> None:
        """Descarga la imagen actual y restaura el widget al estado inicial.
        - Limpia `self.cv_image`, `self._pixmap` y la caché escalada.
        - Limpia `self.points_img`, desactiva la lupa y el seguimiento del cursor.
        - Fuerza un repintado para mostrar el mensaje 'Carga una imagen'.
        """
        self.cv_image = None
        self._pixmap = None
        # reset manager cache
        # Reset scaled manager cache
        self._scaled_manager.set_pixmap(None)

        self._point_manager.reset()
        self._magnifier_enabled = False
        self._mouse_in_img = False
        self.unsetCursor()
        # no hay pantalla de inicio embebida en el canvas (orquestada por MainWindow)
        self.update()

    # Ordering logic moved to `PointManager` in ui/components/point_manager.py

    # ---------- Pintado
    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        painter = QtGui.QPainter(self)
        painter.fillRect(self.rect(), QtGui.QColor(30, 30, 30))

        if self._pixmap is None:
            return

        scaled, left, top = self._scaled_pixmap_and_offset()
        assert scaled is not None
        painter.drawPixmap(left, top, scaled)
        # dibujar crucetas rojas finas (sin numeración)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        pen = QtGui.QPen(self.cross_color)
        pen.setWidth(self.cross_width)
        pen.setCosmetic(True)
        painter.setPen(pen)
        painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)

        # líneas punteadas de referencia (conectan puntos y con el cursor)
        dash_pen = QtGui.QPen(self.line_color)
        dash_pen.setStyle(QtCore.Qt.PenStyle.DashLine)
        dash_pen.setWidth(1)
        dash_pen.setCosmetic(True)

        # Dibujar conexiones entre puntos (ordenadas)
        if len(self._point_manager) >= 2:
            painter.setPen(dash_pen)
            prev_w = None
            prev_h = None
            for (ix, iy) in self._point_manager.points:
                wcoords = self.image_to_widget_coords(ix, iy)
                if wcoords is None:
                    continue
                wx, wy = wcoords
                if prev_w is not None:
                    painter.drawLine(prev_w, prev_h, wx, wy)
                prev_w, prev_h = wx, wy
            # Efecto visual adicional cuando hay 4 puntos: conectar 1-3, 1-4 y 2-4
            if len(self._point_manager) == 4:
                w0 = self.image_to_widget_coords(*self._point_manager.points[0])
                w1 = self.image_to_widget_coords(*self._point_manager.points[1])
                w2 = self.image_to_widget_coords(*self._point_manager.points[2])
                w3 = self.image_to_widget_coords(*self._point_manager.points[3])
                if w0 is not None and w2 is not None:
                    painter.drawLine(w0[0], w0[1], w2[0], w2[1])
                if w0 is not None and w3 is not None:
                    painter.drawLine(w0[0], w0[1], w3[0], w3[1])
                if w1 is not None and w3 is not None:
                    painter.drawLine(w1[0], w1[1], w3[0], w3[1])

        # Si hay cursor sobre la imagen (y aún no se colocaron 4 puntos), dibujar líneas desde el cursor a cada punto
        if self._mouse_in_img and self._point_manager.points and len(self._point_manager) < 4:
            painter.setPen(dash_pen)
            for (ix, iy) in self._point_manager.points:
                wcoords = self.image_to_widget_coords(ix, iy)
                if wcoords is None:
                    continue
                wx, wy = wcoords
                painter.drawLine(wx, wy, self._mouse_wx, self._mouse_wy)

        # dibujar crucetas en cada punto
        painter.setPen(pen)
        for (ix, iy) in self._point_manager.points:
            wcoords = self.image_to_widget_coords(ix, iy)
            if wcoords is None:
                continue
            wx, wy = wcoords
            cl = self.cross_len
            painter.drawLine(wx - cl, wy, wx + cl, wy)
            painter.drawLine(wx, wy - cl, wx, wy + cl)

        # Lupa de enfoque: delegar en el MagnifierTool
        if self._magnifier_enabled and self._mouse_in_img and len(self._point_manager) < 4 and self.cv_image is not None:
            # obtener la posición de widget a usar (sniper virtual o real)
            wfx, wfy = self._sniper.get_current_widget_pos(None, self)
            img_pt = self.widget_to_image_coords(wfx, wfy)
            if img_pt is not None:
                # pasar posición widget en enteros para el overlay
                widget_pos = (int(round(wfx)), int(round(wfy)))
                # delegar dibujo a la herramienta
                self._magnifier.draw(
                    painter, 
                    widget_pos, 
                    img_pt, 
                    self.cv_image, 
                    widget=self, 
                    cross_len=self.cross_len*2,
                    cross_color=self.cross_color,
                    cross_width=self.cross_width,
                    )

        painter.end()


if __name__ == "__main__":
    # pequeño sanity-check si se ejecuta como script
    import sys

    app = QtWidgets.QApplication(sys.argv)
    w = ImageCanvas()
    w.resize(800, 600)
    w.show()
    sys.exit(app.exec())
