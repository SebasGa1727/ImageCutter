from __future__ import annotations

from typing import Optional, Tuple, TYPE_CHECKING

from PyQt6 import QtCore, QtGui, QtWidgets
from utils.logger import setup_logger

if TYPE_CHECKING:
    from image_canvas import ImageCanvas

logger = setup_logger(__name__)

class SniperModeManager:
    def __init__(self, sensitivity: float = 0.05) -> None:
        self.active: bool = False
        self.virtual_cursor_pos: QtCore.QPointF = QtCore.QPointF()
        self.saved_cursor: Optional[QtGui.QCursor] = None
        self.sensitivity: float = float(sensitivity)
        self._last_physical_pos = QtCore.QPoint()
        self._ignore_next_move: bool = False

    def handle_key_press(self, event: QtGui.QKeyEvent, widget: "ImageCanvas", key_type) -> tuple[bool, Optional[float], Optional[float]]:
        """Maneja la activacion de la tecla para activar el modo sniper"""
        key = event.key()
        if key == key_type and not event.isAutoRepeat():
            if not self.active:
                # Guardamos donde estaba la cruceta visualmente en el canvas con valores decimales
                gpos = QtGui.QCursor.pos()
                wpos = widget.mapFromGlobal(gpos)
                self.virtual_cursor_pos = QtCore.QPointF(float(wpos.x()), float(wpos.y()))
                # Encontramos el centro del widget de la pantalla
                rect_center = widget.rect().center()
                center_global = widget.mapToGlobal(rect_center)
                # Movemos el mouse al centro para aumentar el lienzo disponible en "sniper mode"
                QtGui.QCursor.setPos(center_global)
                self._last_physical_pos = center_global

                self.active = True
                self._ignore_next_move = True 
                return True, self.virtual_cursor_pos.x(), self.virtual_cursor_pos.y()
        return False, None, None

    def handle_key_release(self, event: QtGui.QKeyEvent, widget: "ImageCanvas", key_type) -> bool:
        try:
            key = event.key()
            if key == key_type and not event.isAutoRepeat():
                if self.active:
                    self.active = False
                    try:
                        #Al soltar regresamos la cruceta de window a nuestra cruceta virtual
                        vpx = int(round(self.virtual_cursor_pos.x()))
                        vpy = int(round(self.virtual_cursor_pos.y()))
                        global_pos = widget.mapToGlobal(QtCore.QPoint(vpx, vpy))
                        QtGui.QCursor.setPos(global_pos)
                    except Exception:
                        logger.error("Fallo al restaurar el cursor al centro",exc_info=True)
                    return True
        except Exception:
            logger.error("Fallo al registrar el evento",exc_info=True)
        return False

    def handle_mouse_move(self, event: QtGui.QMouseEvent, widget: "ImageCanvas") -> Tuple[bool, Optional[float], Optional[float], Optional[bool]]:
        """Procesa el movimiento del raton cuando esta activo el modo sniper"""
        if not self.active:
            return False, None, None, None
        #Calculamos cuanto se movio el mouse fisico desde la ultima vez
        current_physical_pos = QtGui.QCursor.pos()
        #Si acabamos de teletransportar el ratón, ignoramos este movimiento basura y reseteamos el ancla.
        if self._ignore_next_move:
            self._last_physical_pos = current_physical_pos
            self._ignore_next_move = False
            return True, self.virtual_cursor_pos.x(), self.virtual_cursor_pos.y(), True

        dx = current_physical_pos.x() - self._last_physical_pos.x()
        dy = current_physical_pos.y() - self._last_physical_pos.y()
        # evitar procesar cuando no hay movimiento físico
        if dx == 0 and dy == 0:
            #Evitamos un glitch cuando se mueva el mouse con el modo sniper activado
            mouse_wx = self.virtual_cursor_pos.x()
            mouse_wy = self.virtual_cursor_pos.y()
            img_pt = widget.widget_to_image_coords(mouse_wx, mouse_wy)
            mouse_in_img = (img_pt is not None and len(widget._point_manager) < 4)

            return True, mouse_wx, mouse_wy, mouse_in_img

        #Actualizamos la ultima posicion fisica
        self._last_physical_pos = current_physical_pos
        #Aplicamos la sensibilidad al movimiento
        dx *= self.sensitivity
        dy *= self.sensitivity
        #Sumamos al acumulador virtual
        self.virtual_cursor_pos.setX(self.virtual_cursor_pos.x() + dx)
        self.virtual_cursor_pos.setY(self.virtual_cursor_pos.y() + dy)
        # limitar dentro del widget
        vx = max(0.0, min(widget.width() - 1, self.virtual_cursor_pos.x()))
        vy = max(0.0, min(widget.height() - 1, self.virtual_cursor_pos.y()))
        self.virtual_cursor_pos = QtCore.QPointF(vx, vy)
        #Retornamos valores flotantes 
        mouse_wx = self.virtual_cursor_pos.x()
        mouse_wy = self.virtual_cursor_pos.y()

        img_pt = widget.widget_to_image_coords(mouse_wx, mouse_wy)
        mouse_in_img = (img_pt is not None and len(widget._point_manager) < 4)

        return True, mouse_wx, mouse_wy, mouse_in_img

    def get_current_widget_pos(self, event: Optional[QtGui.QMouseEvent], widget: "ImageCanvas") -> Tuple[float, float]:
        if self.active:
            return float(self.virtual_cursor_pos.x()), float(self.virtual_cursor_pos.y())
        if event is not None:
            return float(event.position().x()), float(event.position().y())
        return float(widget._mouse_wx), float(widget._mouse_wy)

    def deactivate(self, widget: QtGui.QWidget) -> None:
        """Force deactivation and restore cursor on widget."""
        if not self.active:
            return
        self.active = False
        try:
            vpx = int(round(self.virtual_cursor_pos.x()))
            vpy = int(round(self.virtual_cursor_pos.y()))
            global_pos = widget.mapToGlobal(QtCore.QPoint(vpx, vpy))
            QtGui.QCursor.setPos(global_pos)
        except Exception:
            logger.error("Fallo al restaurar posición en deactivate()", exc_info=True)