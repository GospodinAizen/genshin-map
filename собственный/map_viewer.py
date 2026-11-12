"""Tiled HoYoLAB map viewer; source tiles are split into 128px chunks."""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QGraphicsPixmapItem, QGraphicsScene, QGraphicsView, QMainWindow, QLabel
from PySide6.QtGui import QPixmap


TILE_SIZE = 256
CHUNK_SIZE = 128
_TILE_RE = re.compile(r"^(\d+)_(\d+)_([NP])(\d+)\.webp$", re.IGNORECASE)


class TiledMapView(QGraphicsView):
    def __init__(self, map_root: Path, parent=None):
        super().__init__(parent)
        self.map_root = Path(map_root)
        self.meta = json.loads((self.map_root / "meta.json").read_text(encoding="utf-8"))
        self.min_zoom = int(self.meta.get("minZoom", -4))
        self.max_zoom = int(self.meta.get("maxZoom", 0))
        self.active_zoom = None
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        width, height = self.meta["totalSize"]
        self.scene.setSceneRect(0, 0, float(width), float(height))
        self.setBackgroundBrush(Qt.GlobalColor.black)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.MinimalViewportUpdate)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setWindowTitle("Genshin Map — фрагментная карта")
        self.setMinimumSize(900, 620)
        self._load_zoom(self.min_zoom)

    def _suffix(self, zoom: int) -> str:
        return f"N{abs(zoom)}" if zoom < 0 else f"P{zoom}"

    def _load_zoom(self, zoom: int) -> None:
        zoom = max(self.min_zoom, min(self.max_zoom, int(zoom)))
        if zoom == self.active_zoom:
            return
        self.scene.clear()
        scale = 2 ** zoom
        tiles_dir = self.map_root / "tiles"
        if not tiles_dir.is_dir():
            self.active_zoom = None
            return
        files = sorted(tiles_dir.glob(f"*_*_{self._suffix(zoom)}.webp"))
        for path in files:
            match = _TILE_RE.match(path.name)
            if not match:
                continue
            tx, ty = int(match.group(1)), int(match.group(2))
            pixmap = QPixmap(str(path))
            if pixmap.isNull():
                continue
            if pixmap.width() != TILE_SIZE or pixmap.height() != TILE_SIZE:
                pixmap = pixmap.scaled(TILE_SIZE, TILE_SIZE, Qt.AspectRatioMode.IgnoreAspectRatio,
                                       Qt.TransformationMode.SmoothTransformation)
            # Each 256px source tile becomes four independent 128px image fragments.
            for cy in (0, CHUNK_SIZE):
                for cx in (0, CHUNK_SIZE):
                    chunk = pixmap.copy(cx, cy, CHUNK_SIZE, CHUNK_SIZE)
                    item = QGraphicsPixmapItem(chunk)
                    item.setTransformationMode(Qt.TransformationMode.SmoothTransformation)
                    item.setScale(1.0 / scale)
                    item.setPos((tx * TILE_SIZE + cx) / scale,
                                (ty * TILE_SIZE + cy) / scale)
                    item.setZValue(0)
                    self.scene.addItem(item)
        self.active_zoom = zoom

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if self.active_zoom == self.min_zoom:
            self.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def wheelEvent(self, event) -> None:
        factor = 1.2 if event.angleDelta().y() > 0 else 1.0 / 1.2
        self.scale(factor, factor)
        after = self.transform().m11()
        if after <= 0:
            return
        desired = round(math.log2(after))
        desired = max(self.min_zoom, min(self.max_zoom, desired))
        if desired != self.active_zoom:
            center = self.mapToScene(self.viewport().rect().center())
            self._load_zoom(desired)
            self.centerOn(center)


class MapViewer(QMainWindow):
    def __init__(self, map_root: Path, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Genshin Impact — карта")
        self.view = TiledMapView(map_root, self)
        self.setCentralWidget(self.view)
        self.statusBar().showMessage("Колесо мыши — масштаб · перетаскивание — перемещение · фрагменты 128×128")
