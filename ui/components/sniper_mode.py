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
        self.sensitivity: float = float(sensitivity)
        
        # El Ancla Absoluta
        self._anchor_pos = QtCore.QPoint()
        
        # El Filtro de Tiempo
        self._activation_timestamp: int = 0

    def handle_key_press(self, event: QtGui.QKeyEvent, widget: "ImageCanvas", key_type) -> tuple[bool, Optional[float], Optional[float]]:
        """Maneja la activacion de la tecla para activar el modo sniper"""
        key = event.key()
        if key == key_type and not event.isAutoRepeat():
            #seguridad para evitar activar el modo sniper fuera de la imagen
            if not widget._mouse_in_img:
                return False, None, None
            
            if not self.active:
                # 1. Guardamos dónde estaba la cruceta visual
                gpos = QtGui.QCursor.pos()
                wpos = widget.mapFromGlobal(gpos)
                self.virtual_cursor_pos = QtCore.QPointF(float(wpos.x()), float(wpos.y()))
                
                # 2. Definimos nuestra Ancla (El centro exacto del widget)
                rect_center = widget.rect().center()
                self._anchor_pos = widget.mapToGlobal(rect_center)
                
                # 3. Lanzamos el Ancla por primera vez
                QtGui.QCursor.setPos(self._anchor_pos)
                
                # 4. GUARDAMOS EL TIEMPO EXACTO para filtrar la basura
                self._activation_timestamp = event.timestamp()

                self.active = True
                widget.grabMouse() # Secuestramos el ratón a nivel OS
                return True, self.virtual_cursor_pos.x(), self.virtual_cursor_pos.y()
        return False, None, None

    def handle_key_release(self, event: QtGui.QKeyEvent, widget: "ImageCanvas", key_type) -> bool:
        try:
            key = event.key()
            if key == key_type and not event.isAutoRepeat():
                if self.active:
                    self.active = False
                    try:
                        widget.releaseMouse()
                        vpx = int(round(self.virtual_cursor_pos.x()))
                        vpy = int(round(self.virtual_cursor_pos.y()))
                        global_pos = widget.mapToGlobal(QtCore.QPoint(vpx, vpy))
                        QtGui.QCursor.setPos(global_pos)
                    except Exception:
                        logger.error("Fallo al restaurar el cursor", exc_info=True)
                    return True
        except Exception:
            logger.error("Fallo al registrar el evento", exc_info=True)
        return False

    def handle_mouse_move(self, event: QtGui.QMouseEvent, widget: "ImageCanvas") -> Tuple[bool, Optional[float], Optional[float], Optional[bool]]:
        """Procesa el movimiento usando el patrón de Ancla Absoluta"""
        if not self.active:
            return False, None, None, None
            
        current_physical_pos = event.globalPosition().toPoint()
        
        # --- FILTRO 1: TIEMPO (Ignora movimientos previos a presionar Shift) ---
        if event.timestamp() <= self._activation_timestamp:
            return True, self.virtual_cursor_pos.x(), self.virtual_cursor_pos.y(), True

        # --- FILTRO 2: EL ECO DEL ANCLA (Ignora el evento artificial de Windows) ---
        if current_physical_pos == self._anchor_pos:
            return True, self.virtual_cursor_pos.x(), self.virtual_cursor_pos.y(), True

        # --- MATEMÁTICA PURA (Deltas basados en el Ancla) ---
        dx = current_physical_pos.x() - self._anchor_pos.x()
        dy = current_physical_pos.y() - self._anchor_pos.y()
        
        # Aplicamos la sensibilidad
        dx *= self.sensitivity
        dy *= self.sensitivity

        new_vx = self.virtual_cursor_pos.x() + dx
        new_vy = self.virtual_cursor_pos.y() + dy   
        
        # Actualizamos la posición virtual
        self.virtual_cursor_pos.setX(self.virtual_cursor_pos.x() + dx)
        self.virtual_cursor_pos.setY(self.virtual_cursor_pos.y() + dy)
        
        # Limitamos la cruceta para que no salga del Canvas y de la imagen
        #Le pedimos al canvas las dimensiones de la foto
        scaled, left, top = widget._scaled_pixmap_and_offset()
        if scaled is not None:
            min_x = float(left)
            max_x = float(left + scaled.width() - 1)
            min_y = float(top)
            max_y = float(top + scaled.height() -1)
        else:
            # Fallback por seguridad (Limites del widget)
            min_x, max_x = 0.0, float(widget.width() - 1)
            min_y, max_y = 0.0, float(widget.height() - 1)

        vx = max(min_x, min(max_x, new_vx))
        vy = max(min_y, min(max_y, new_vy))
        
        self.virtual_cursor_pos = QtCore.QPointF(vx, vy)
        
        mouse_wx = self.virtual_cursor_pos.x()
        mouse_wy = self.virtual_cursor_pos.y()

        img_pt = widget.widget_to_image_coords(mouse_wx, mouse_wy)
        mouse_in_img = (img_pt is not None and len(widget._point_manager) < 4)

        # --- EL RE-ANCLAJE (Manteniendo a Windows atrapado) ---
        QtGui.QCursor.setPos(self._anchor_pos)
        # ------------------------------------------------------

        return True, mouse_wx, mouse_wy, mouse_in_img

    def get_current_widget_pos(self, event: Optional[QtGui.QMouseEvent], widget: "ImageCanvas") -> Tuple[float, float]:
        if self.active:
            return float(self.virtual_cursor_pos.x()), float(self.virtual_cursor_pos.y())
        if event is not None:
            return float(event.position().x()), float(event.position().y())
        return float(widget._mouse_wx), float(widget._mouse_wy)

    def deactivate(self, widget: "ImageCanvas") -> None:
        if not self.active:
            return
        self.active = False
        try:
            widget.releaseMouse()
            vpx = int(round(self.virtual_cursor_pos.x()))
            vpy = int(round(self.virtual_cursor_pos.y()))
            global_pos = widget.mapToGlobal(QtCore.QPoint(vpx, vpy))
            QtGui.QCursor.setPos(global_pos)
        except Exception:
            logger.error("Fallo en deactivate()", exc_info=True)