from __future__ import annotations

from typing import Optional, Tuple

import cv2
import numpy as np
from PyQt6 import QtGui, QtCore
from utils.utils import _cv_to_qpixmap


class MagnifierTool:
    """Tool that renders a magnified overlay from an OpenCV image.

    The tool does the sampling (getRectSubPix fallback) and drawing of the
    magnified patch. It's independent from the widget but accepts the widget
    when required to clamp overlay placement.
    """

    def __init__(self, size: int = 200, zoom: float = 3.0, border: int = 2, offset: int = 60) -> None:
        self.size = int(size)
        self.zoom = float(zoom)
        self.border = int(border)
        self.offset = int(offset)

    def draw(self, painter: QtGui.QPainter, widget_pos: Tuple[int, int], img_pos: Tuple[float, float], 
             cv_image: np.ndarray, widget: Optional[QtGui.QWidget] = None,
              cross_len: int = 8, cross_color: Optional[QtGui.QColor] = None, 
              cross_width: int = 1, border_color: Optional[QtGui.QColor] = None) -> None:
        """Draw the magnifier overlay"""
        if cv_image is None or img_pos is None:
            return

        cx, cy = img_pos
        sample_w = max(1, int(round(self.size / self.zoom)))
        sample_h = max(1, int(round(self.size / self.zoom)))

        try:
            patch = cv2.getRectSubPix(cv_image, (sample_w, sample_h), (float(cx), float(cy)))
        except Exception:
            # fallback: integer bbox with clipping
            ih, iw = cv_image.shape[:2]
            x1 = int(round(cx)) - sample_w // 2
            y1 = int(round(cy)) - sample_h // 2
            x2 = x1 + sample_w
            y2 = y1 + sample_h
            x1c = max(0, x1); y1c = max(0, y1); x2c = min(iw, x2); y2c = min(ih, y2)
            patch = cv_image[y1c:y2c, x1c:x2c].copy()

        if patch is None or patch.size == 0:
            return

        magnified = cv2.resize(patch, (self.size, self.size), interpolation=cv2.INTER_NEAREST)

        # Use centralized conversion util to obtain a QPixmap
        mag_pix = _cv_to_qpixmap(magnified)

        ow = self.size
        oh = self.size
        mwx, mwy = widget_pos
        ox = mwx + self.offset
        oy = mwy + self.offset

        # clamp to widget if provided
        if widget is not None:
            ox = max(0, min(widget.width() - ow, ox))
            oy = max(0, min(widget.height() - oh, oy))

        # dibujar fondo y borde
        painter.setPen(QtCore.Qt.PenStyle.NoPen)
        painter.setBrush(QtGui.QBrush(border_color if border_color else QtGui.QColor(255, 255, 255)))
        painter.drawRect(ox - self.border, oy - self.border, ow + 2 * self.border, oh + 2 * self.border)
        painter.drawPixmap(ox, oy, mag_pix)

        # dibujar cruceta roja proporcional en el centro
        final_color = cross_color if cross_color is not None else QtGui.QColor(220, 0, 0)
        pen_cross = QtGui.QPen(final_color)
        pen_cross.setWidth(cross_width)
        pen_cross.setCosmetic(True)
        painter.setPen(pen_cross)
        cross_half = max(1, int(round(cross_len * self.zoom)))
        cx_o = ox + ow // 2
        cy_o = oy + oh // 2
        painter.drawLine(cx_o - cross_half, cy_o, cx_o + cross_half, cy_o)
        painter.drawLine(cx_o, cy_o - cross_half, cx_o, cy_o + cross_half)
