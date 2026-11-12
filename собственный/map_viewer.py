"""Interactive tiled HoYoLAB map with a lightweight, clickable marker layer."""
from __future__ import annotations

import json
import math
import re
import sqlite3
import zlib
from pathlib import Path

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QPainter, QPen, QBrush, QColor, QPixmap
from PySide6.QtWidgets import (
    QComboBox, QGraphicsItem, QGraphicsPixmapItem, QGraphicsScene, QGraphicsView,
    QMainWindow, QToolBar,
)

TILE_SIZE = 256
CHUNK_SIZE = 64
_TILE_RE = re.compile(r"^(\d+)_(\d+)_([NP])(\d+)\.webp$", re.IGNORECASE)
PALETTE = ((255, 190, 70), (90, 210, 255), (120, 230, 150),
           (220, 130, 255), (255, 220, 90), (100, 220, 220),
           (255, 110, 150), (170, 210, 255))


def _category_color(value: str) -> QColor:
    return QColor(*PALETTE[zlib.crc32(value.encode("utf-8")) % len(PALETTE)])


class MarkerLayer(QGraphicsItem):
    """One paint item for the whole catalogue: avoids tens of thousands of scene items."""
    def __init__(self, markers: list[dict], progress_db: Path, bounds: QRectF, asset_root: Path):
        super().__init__()
        self.markers = markers
        self.asset_root = asset_root
        self.icon_cache: dict[str, QPixmap] = {}
        self.active_floor = "all"
        self.bounds = bounds
        self.db = sqlite3.connect(progress_db)
        self.db.execute("""CREATE TABLE IF NOT EXISTS progress (
            marker_id TEXT PRIMARY KEY, found INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""")
        self.db.commit()
        self.found = {row[0] for row in self.db.execute(
            "SELECT marker_id FROM progress WHERE found=1"
        )}
        self.setZValue(10)

    def boundingRect(self) -> QRectF:
        return self.bounds

    def paint(self, painter: QPainter, option, widget=None) -> None:
        scale = max(0.0001, painter.worldTransform().m11())
        radius = 4.0 / scale
        pen = QPen(QColor(20, 25, 30, 220))
        pen.setWidthF(1.0 / scale)
        painter.setPen(pen)
        exposed = option.exposedRect.adjusted(-radius, -radius, radius, radius)
        for marker in self.markers:
            if self.active_floor != "all" and str(marker.get("floor_id", "surface")) != self.active_floor:
                continue
            x, y = marker.get("world_x"), marker.get("world_y")
            if x is None or y is None or not exposed.contains(float(x), float(y)):
                continue
            icon_rel = marker.get("icon")
            icon = None
            if icon_rel:
                key = str(icon_rel)
                if key not in self.icon_cache:
                    icon_path = (self.asset_root / key).resolve()
                    try:
                        icon_path.relative_to(self.asset_root.resolve())
                        self.icon_cache[key] = QPixmap(str(icon_path))
                    except ValueError:
                        self.icon_cache[key] = QPixmap()
                icon = self.icon_cache[key]
            if icon is not None and not icon.isNull():
                side = 22.0 / scale
                if marker["id"] in self.found:
                    painter.setOpacity(0.35)
                painter.drawPixmap(QRectF(float(x)-side/2, float(y)-side/2, side, side), icon, QRectF(icon.rect()))
                painter.setOpacity(1.0)
            else:
                found = marker["id"] in self.found
                color = QColor(115, 120, 125, 150) if found else _category_color(str(marker.get("type", "Other")))
                painter.setBrush(QBrush(color))
                painter.drawEllipse(QRectF(float(x)-radius, float(y)-radius, radius*2, radius*2))

    def set_floor(self, floor_id: str) -> None:
        self.active_floor = floor_id
        self.update()

    def toggle_nearest(self, x: float, y: float, tolerance: float) -> dict | None:
        best, best_d2 = None, tolerance * tolerance
        for marker in self.markers:
            if self.active_floor != "all" and str(marker.get("floor_id", "surface")) != self.active_floor:
                continue
            if marker.get("world_x") is None or marker.get("world_y") is None:
                continue
            dx, dy = float(marker["world_x"])-x, float(marker["world_y"])-y
            d2 = dx*dx + dy*dy
            if d2 <= best_d2:
                best, best_d2 = marker, d2
        if best is None:
            return None
        marker_id = best["id"]
        found = marker_id not in self.found
        if found:
            self.found.add(marker_id)
            self.db.execute(
                "INSERT INTO progress(marker_id,found) VALUES(?,1) "
                "ON CONFLICT(marker_id) DO UPDATE SET found=1,updated_at=CURRENT_TIMESTAMP",
                (marker_id,),
            )
        else:
            self.found.remove(marker_id)
            self.db.execute(
                "INSERT INTO progress(marker_id,found) VALUES(?,0) "
                "ON CONFLICT(marker_id) DO UPDATE SET found=0,updated_at=CURRENT_TIMESTAMP",
                (marker_id,),
            )
        self.db.commit()
        self.update()
        return {**best, "found": found}

    def close(self) -> None:
        self.db.close()


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
        self.map_bounds = QRectF(0, 0, float(width), float(height))
        self.scene.setSceneRect(self.map_bounds)
        self.setBackgroundBrush(Qt.GlobalColor.black)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.MinimalViewportUpdate)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setWindowTitle("Genshin Impact — подробная карта")
        self.setMinimumSize(900, 620)
        self.marker_layer = None
        self.last_marker = None
        self._load_markers()
        self._load_zoom(self.min_zoom)

    def _load_markers(self) -> None:
        marker_file = self.map_root / "markers.runtime.json"
        if not marker_file.is_file():
            return
        markers = json.loads(marker_file.read_text(encoding="utf-8"))
        if not isinstance(markers, list):
            raise ValueError("markers.runtime.json должен содержать массив.")
        self.marker_layer = MarkerLayer(markers, self.map_root / "progress.db", self.map_bounds, self.map_root)
        self.scene.addItem(self.marker_layer)
        self.setWindowTitle(f"Genshin Impact — карта · {len(markers):,} меток")

    def _suffix(self, zoom: int) -> str:
        return f"N{abs(zoom)}" if zoom < 0 else f"P{zoom}"

    def _load_zoom(self, zoom: int) -> None:
        zoom = max(self.min_zoom, min(self.max_zoom, int(zoom)))
        if zoom == self.active_zoom:
            return
        for item in list(self.scene.items()):
            if item is not self.marker_layer:
                self.scene.removeItem(item)
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
            if pixmap.size().width() != TILE_SIZE or pixmap.size().height() != TILE_SIZE:
                from PySide6.QtCore import QSize
                pixmap = pixmap.scaled(QSize(TILE_SIZE, TILE_SIZE), Qt.AspectRatioMode.IgnoreAspectRatio,
                                       Qt.TransformationMode.SmoothTransformation)
            for cy in range(0, TILE_SIZE, CHUNK_SIZE):
                for cx in range(0, TILE_SIZE, CHUNK_SIZE):
                    chunk = pixmap.copy(cx, cy, CHUNK_SIZE, CHUNK_SIZE)
                    item = QGraphicsPixmapItem(chunk)
                    item.setTransformationMode(Qt.TransformationMode.SmoothTransformation)
                    item.setScale(1.0 / scale)
                    item.setPos((tx*TILE_SIZE+cx)/scale, (ty*TILE_SIZE+cy)/scale)
                    item.setZValue(0)
                    self.scene.addItem(item)
        self.active_zoom = zoom
        if self.marker_layer is not None:
            self.marker_layer.setZValue(10)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if self.active_zoom == self.min_zoom:
            self.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def wheelEvent(self, event) -> None:
        factor = 1.2 if event.angleDelta().y() > 0 else 1.0/1.2
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

    def mousePressEvent(self, event) -> None:
        if (event.button() == Qt.MouseButton.LeftButton and self.marker_layer is not None
                and not (event.modifiers() & Qt.KeyboardModifier.ShiftModifier)):
            point = self.mapToScene(event.position().toPoint())
            tolerance = 14.0 / max(self.transform().m11(), 0.0001)
            marker = self.marker_layer.toggle_nearest(point.x(), point.y(), tolerance)
            if marker is not None:
                state = "найдено" if marker["found"] else "снова не найдено"
                self.last_marker = marker
                self.window().statusBar().showMessage(
                    f"{marker.get('name', 'Метка')} — {state} · {marker.get('type', '')}", 4000
                )
                return
        super().mousePressEvent(event)

    def closeEvent(self, event) -> None:
        if self.marker_layer is not None:
            self.marker_layer.close()
        super().closeEvent(event)


class MapViewer(QMainWindow):
    def __init__(self, map_root: Path, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Genshin Impact — карта")
        self.view = TiledMapView(map_root, self)
        self.setCentralWidget(self.view)
        if self.view.marker_layer is not None:
            toolbar = QToolBar("Слои карты", self)
            self.addToolBar(toolbar)
            floors = QComboBox(toolbar)
            floors.addItem("Все этажи", "all")
            unique = {}
            for marker in self.view.marker_layer.markers:
                fid = str(marker.get("floor_id", "surface"))
                unique.setdefault(fid, str(marker.get("floor_label", fid)))
            for fid, label in sorted(unique.items(), key=lambda item: (item[0] != "surface", item[0])):
                floors.addItem(label, fid)
            floors.currentIndexChanged.connect(
                lambda index: self.view.marker_layer.set_floor(str(floors.itemData(index)))
            )
            toolbar.addWidget(floors)
        self.statusBar().showMessage(
            "Колесо — масштаб · перетаскивание — перемещение · ЛКМ по метке — найдено/не найдено · Shift+ЛКМ — перемещение"
        )
