from __future__ import annotations

from typing import Optional, Tuple

from PyQt6 import QtCore, QtGui, QtWidgets
from utils.logger import setup_logger

logger = setup_logger(__name__)

class SniperModeManager:
    """Manage a virtual cursor for precision/snipe mode.

    Responsibilities:
    - Track activation state (Shift pressed)
    - Maintain a `virtual_cursor_pos` QPointF
    - Save/restore the widget cursor
    - Compute virtual movement using a reduced sensitivity
    """

    def __init__(self, sensitivity: float = 0.05) -> None:
        self.active: bool = False
        self.virtual_cursor_pos: QtCore.QPointF = QtCore.QPointF()
        self.saved_cursor: Optional[QtGui.QCursor] = None
        self.sensitivity: float = float(sensitivity)
        self._last_physical_pos = QtCore.QPoint()

    def handle_key_press(self, event: QtGui.QKeyEvent, widget: QtWidgets.QWidget) -> tuple[bool, Optional[int], Optional[int]]:
        """Maneja la activacion de la tecla para activar el modo sniper"""
        key = event.key()
        if key == QtCore.Qt.Key.Key_Shift and not event.isAutoRepeat():
            if not self.active:
                # Guardamos donde estaba la cruceta visualmente en el canvas
                gpos = QtGui.QCursor.pos()
                wpos = widget.mapFromGlobal(gpos)
                self.virtual_cursor_pos = QtCore.QPointF(float(wpos.x()), float(wpos.y()))
                self.saved_cursor = widget.cursor()
                
                # Encontramos el centro del widget de la pantalla
                rect_center = widget.rect().center()
                center_global = widget.mapToGlobal(rect_center)

                # Movemos el mouse al centro para aumentar el lienzo disponible en "sniper mode"
                QtGui.QCursor.setPos(center_global)

                self._last_physical_pos = center_global

                try:
                    widget.setCursor(QtCore.Qt.CursorShape.BlankCursor)
                except Exception:
                    logger.warning("Fallo al ocultar el mouse entrando en el modo sniper", exc_info=True)
                
                self.active = True
                mouse_wx = int(round(self.virtual_cursor_pos.x()))
                mouse_wy = int(round(self.virtual_cursor_pos.y()))
                return True, mouse_wx, mouse_wy
        return False, None, None

    def handle_key_release(self, event: QtGui.QKeyEvent, widget: QtWidgets.QWidget) -> bool:
        try:
            key = event.key()
            if key == QtCore.Qt.Key.Key_Shift and not event.isAutoRepeat():
                if self.active:
                    self.active = False
                    try:
                        vpx = int(round(self.virtual_cursor_pos.x()))
                        vpy = int(round(self.virtual_cursor_pos.y()))
                        global_pos = widget.mapToGlobal(QtCore.QPoint(vpx, vpy))
                        QtGui.QCursor.setPos(global_pos)
                    except Exception:
                        logger.error("Fallo al restaurar el cursor al centro",exc_info=True)
                    try:
                        if self.saved_cursor is not None:
                            widget.setCursor(self.saved_cursor)
                        else:
                            widget.unsetCursor()
                    except Exception:
                        logger.error("Fallo al restaurar el color del cursor",exc_info=True)
                    return True
        except Exception:
            logger.error("Fallo al registrar el evento",exc_info=True)
        return False

    def handle_mouse_move(self, event: QtGui.QMouseEvent, widget: QtWidgets.QWidget) -> Tuple[bool, Optional[int], Optional[int], Optional[bool]]:
        """Procesa el movimiento del raton cuando esta activo el modo sniper.
        Retorna: (handled, mouse_wx, mouse_wy, mouse_in_img).
        """
        if not self.active:
            return False, None, None, None

        #Calculamos cuanto se movio el mouse fisico desde la ultima vez
        current_physical_pos = QtGui.QCursor.pos()
        gposf = event.globalPosition()

        dx = gposf.x() - self._last_physical_pos.x()
        dy = gposf.y() - self._last_physical_pos.y()

        # evitar procesar cuando no hay movimiento físico
        if dx == 0 and dy == 0:
            return True, int(round(self.virtual_cursor_pos.x())), int(round(self.virtual_cursor_pos.y())), False

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

        mouse_wx = int(round(self.virtual_cursor_pos.x()))
        mouse_wy = int(round(self.virtual_cursor_pos.y()))

        img_pt = widget.widget_to_image_coords(mouse_wx, mouse_wy)
        mouse_in_img = (img_pt is not None and len(widget._point_manager) < 4)

        return True, mouse_wx, mouse_wy, mouse_in_img

    def get_current_widget_pos(self, event: Optional[QtGui.QMouseEvent], widget: QtWidgets.QWidget) -> Tuple[float, float]:
        """Return the widget coords (float) that should be used for mapping to image.

        If sniper is active returns the virtual cursor position, otherwise returns
        the position from the provided event or the current widget mouse coords.
        """
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
        try:
            if self.saved_cursor is not None:
                widget.setCursor(self.saved_cursor)
            else:
                widget.unsetCursor()
        except Exception:
            logger.error("Fallo al restaurar icono del cursor en deactivate()", exc_info=True)
