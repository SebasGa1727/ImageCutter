from __future__ import annotations

from typing import Optional, Tuple
from PyQt6 import QtCore, QtGui

class ScaledPixmapManager:
    def __init__(self) -> None:
        self._pixmap: Optional[QtGui.QPixmap] = None
        self._orig_w: int = 0
        self._orig_h: int = 0
        self._scaled_pixmap_cache: Optional[QtGui.QPixmap] = None
        self._scaled_pixmap_left: int = 0
        self._scaled_pixmap_top: int = 0

    def set_pixmap(self, pixmap: Optional[QtGui.QPixmap]) -> None:
        self._pixmap = pixmap
        if pixmap is not None:
            self._orig_w = pixmap.width()
            self._orig_h = pixmap.height()
        else:
            self._orig_w = 0
            self._orig_h = 0
        self._scaled_pixmap_cache = None
        self._scaled_pixmap_left = 0
        self._scaled_pixmap_top = 0

    def set_explicit_dimensions(self, w: int, h: int) -> None:
        self._orig_w = w
        self._orig_h = h

    def inject_scaled_cache(self, pixmap: QtGui.QPixmap, left: int, top: int) -> None:
        self._scaled_pixmap_cache = pixmap
        self._scaled_pixmap_left = left
        self._scaled_pixmap_top = top

    def update_scaled_cache(self, widget_size: QtCore.QSize) -> None:
        if self._pixmap is None:
            return
        scaled = self._pixmap.scaled(widget_size, QtCore.Qt.AspectRatioMode.KeepAspectRatio, QtCore.Qt.TransformationMode.SmoothTransformation)
        left = (widget_size.width() - scaled.width()) // 2
        top = (widget_size.height() - scaled.height()) // 2
        self._scaled_pixmap_cache = scaled
        self._scaled_pixmap_left = left
        self._scaled_pixmap_top = top

    def get_scaled_and_offset(self) -> Tuple[Optional[QtGui.QPixmap], int, int]:
        return self._scaled_pixmap_cache, self._scaled_pixmap_left, self._scaled_pixmap_top

    def widget_to_image_coords(self, wx: float, wy: float) -> Optional[Tuple[float, float]]:
        if self._orig_w == 0 or self._orig_h == 0:
            return None
        scaled, left, top = self.get_scaled_and_offset()
        if scaled is None:
            return None
        if not (left <= wx <= left + scaled.width() and top <= wy <= top + scaled.height()):
            return None
        rel_x = wx - left
        rel_y = wy - top
        img_x = rel_x * (self._orig_w / scaled.width())
        img_y = rel_y * (self._orig_h / scaled.height())
        return float(img_x), float(img_y)

    def image_to_widget_coords(self, ix: float, iy: float) -> Optional[Tuple[int, int]]:
        if self._orig_w == 0 or self._orig_h == 0:
            return None
        scaled, left, top = self.get_scaled_and_offset()
        if scaled is None:
            return None
        wx = left + int(ix * (scaled.width() / self._orig_w))
        wy = top + int(iy * (scaled.height() / self._orig_h))
        return wx, wy