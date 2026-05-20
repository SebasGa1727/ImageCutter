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
        
        self._anchor_pos = QtCore.QPoint()
        self._last_physical_pos = QtCore.QPoint()
        
        self._release_pos = QtCore.QPoint()
        
        self._teleport_source = QtCore.QPoint() 
        
        self._sync_pending: bool = False
        self._ghost_clear_counter: int = 0 

    def handle_key_press(self, event: QtGui.QKeyEvent, widget: "ImageCanvas", key_type) -> tuple[bool, Optional[float], Optional[float]]:
        key = event.key()
        if key == key_type and not event.isAutoRepeat():
            if not widget._mouse_in_img:
                return False, None, None
            
            if not self.active:
                self.virtual_cursor_pos = QtCore.QPointF(float(widget._mouse_wx), float(widget._mouse_wy))
                
                rect_center = widget.rect().center()
                self._anchor_pos = widget.mapToGlobal(rect_center)
                current_phys = QtGui.QCursor.pos()
                
                # Evaluamos si ya estamos físicamente en el centro
                dist_sq = (current_phys.x() - self._anchor_pos.x())**2 + (current_phys.y() - self._anchor_pos.y())**2
                
                if dist_sq < 100: # Si estamos a menos de 10px, no requerimos escudo
                    self._sync_pending = False
                    self._last_physical_pos = current_phys
                else:
                    self._sync_pending = True
                    self._teleport_source = current_phys # Registramos "El Pasado"
                    QtGui.QCursor.setPos(self._anchor_pos)
                    
                self.active = True
                widget.grabMouse()
                return True, self.virtual_cursor_pos.x(), self.virtual_cursor_pos.y()
        return False, None, None

    def handle_key_release(self, event: QtGui.QKeyEvent, widget: "ImageCanvas", key_type) -> bool:
        try:
            key = event.key()
            if key == key_type and not event.isAutoRepeat():
                if self.active:
                    self.active = False
                    self._ghost_clear_counter = 3 
                    try:
                        widget.releaseMouse()
                        vpx = int(round(self.virtual_cursor_pos.x()))
                        vpy = int(round(self.virtual_cursor_pos.y()))
                        global_pos = widget.mapToGlobal(QtCore.QPoint(vpx, vpy))
                        
                        self._release_pos = global_pos 
                        QtGui.QCursor.setPos(global_pos)
                    except Exception:
                        logger.error("Fallo al restaurar el cursor", exc_info=True)
                    return True
        except Exception:
            logger.error("Fallo al registrar el evento", exc_info=True)
        return False

    def handle_mouse_move(self, event: QtGui.QMouseEvent, widget: "ImageCanvas") -> Tuple[bool, Optional[float], Optional[float], Optional[bool]]:
        current_physical_pos = event.globalPosition().toPoint()

        # --- FILTRO 1: CAZAFANTASMAS DE SALIDA ---
        if not self.active:
            if self._ghost_clear_counter > 0:
                self._ghost_clear_counter -= 1
                dist_x = abs(current_physical_pos.x() - self._release_pos.x())
                dist_y = abs(current_physical_pos.y() - self._release_pos.y())
                
                if dist_x < 50 and dist_y < 50:
                    self._ghost_clear_counter = 0 
                    return False, None, None, None
                else:
                    return True, widget._mouse_wx, widget._mouse_wy, widget._mouse_in_img
            return False, None, None, None
            
        # --- FILTRO 2: EL PLANO BISECTOR (La Magia Matemática) ---
        if self._sync_pending:
            dist_to_anchor_sq = (current_physical_pos.x() - self._anchor_pos.x())**2 + (current_physical_pos.y() - self._anchor_pos.y())**2
            dist_to_source_sq = (current_physical_pos.x() - self._teleport_source.x())**2 + (current_physical_pos.y() - self._teleport_source.y())**2
            
            # Si el paquete de Windows está más cerca del Futuro (Ancla) que del Pasado (Fuente)
            if dist_to_anchor_sq < dist_to_source_sq:
                self._sync_pending = False
                self._last_physical_pos = current_physical_pos
                return True, self.virtual_cursor_pos.x(), self.virtual_cursor_pos.y(), True
            else:
                return True, self.virtual_cursor_pos.x(), self.virtual_cursor_pos.y(), True

        # --- MATEMÁTICA PURA RELATIVA ---
        dx = current_physical_pos.x() - self._last_physical_pos.x()
        dy = current_physical_pos.y() - self._last_physical_pos.y()
        
        self._last_physical_pos = current_physical_pos
        
        dx *= self.sensitivity
        dy *= self.sensitivity

        new_vx = self.virtual_cursor_pos.x() + dx
        new_vy = self.virtual_cursor_pos.y() + dy   
        
        # --- LÍMITES A LA IMAGEN ---
        scaled, left, top = widget._scaled_pixmap_and_offset()
        if scaled is not None:
            min_x = float(left)
            max_x = float(left + scaled.width() - 1)
            min_y = float(top)
            max_y = float(top + scaled.height() -1)
        else:
            min_x, max_x = 0.0, float(widget.width() - 1)
            min_y, max_y = 0.0, float(widget.height() - 1)

        vx = max(min_x, min(max_x, new_vx))
        vy = max(min_y, min(max_y, new_vy))
        
        self.virtual_cursor_pos = QtCore.QPointF(vx, vy)
        
        mouse_wx = self.virtual_cursor_pos.x()
        mouse_wy = self.virtual_cursor_pos.y()

        img_pt = widget.widget_to_image_coords(mouse_wx, mouse_wy)
        mouse_in_img = (img_pt is not None and len(widget._point_manager) < 4)

        # --- LA CAJA DE RESPIRO ---
        dist_x_wrap = abs(current_physical_pos.x() - self._anchor_pos.x())
        dist_y_wrap = abs(current_physical_pos.y() - self._anchor_pos.y())
        
        if dist_x_wrap > 250 or dist_y_wrap > 250:
            self._teleport_source = current_physical_pos # Registramos el Pasado
            QtGui.QCursor.setPos(self._anchor_pos)
            self._sync_pending = True 

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
        self._ghost_clear_counter = 3
        try:
            widget.releaseMouse()
            vpx = int(round(self.virtual_cursor_pos.x()))
            vpy = int(round(self.virtual_cursor_pos.y()))
            global_pos = widget.mapToGlobal(QtCore.QPoint(vpx, vpy))
            self._release_pos = global_pos
            QtGui.QCursor.setPos(global_pos)
        except Exception:
            logger.error("Fallo en deactivate()", exc_info=True)