"""3D scene viewer panel using pyqtgraph's GLViewWidget."""

from __future__ import annotations

import numpy as np
from PyQt6.QtWidgets import QVBoxLayout, QWidget
import pyqtgraph.opengl as gl

from pySimSAR.core.scene import DistributedTarget, PointTarget, Scene


def _rcs_to_scalar(rcs: float | np.ndarray) -> float:
    """Extract a scalar RCS value (dBsm-like magnitude) for coloring."""
    if isinstance(rcs, np.ndarray):
        return float(np.linalg.norm(rcs))
    return float(rcs)


def _colormap(values: np.ndarray) -> np.ndarray:
    """Map normalized values [0,1] to RGBA colors (blue-green-red ramp).

    Returns array of shape (N, 4) with float values in [0, 1].
    """
    n = len(values)
    colors = np.ones((n, 4), dtype=float)
    # Blue (low) -> Green (mid) -> Red (high)
    colors[:, 0] = np.clip(2.0 * values - 1.0, 0.0, 1.0)  # R
    colors[:, 1] = 1.0 - 2.0 * np.abs(values - 0.5)  # G
    colors[:, 2] = np.clip(1.0 - 2.0 * values, 0.0, 1.0)  # B
    return colors


def _cone_mesh(tip: np.ndarray, direction: np.ndarray,
               length: float, radius: float, n_seg: int = 12) -> tuple:
    """Return (vertices, faces) for a cone pointing along *direction*.

    *tip* is the pointy end; the base circle is at tip - direction*length.
    """
    d = np.asarray(direction, dtype=float)
    d = d / np.linalg.norm(d)
    base_center = tip - d * length

    # Build two vectors perpendicular to d
    if abs(d[2]) < 0.9:
        u = np.cross(d, np.array([0, 0, 1], dtype=float))
    else:
        u = np.cross(d, np.array([1, 0, 0], dtype=float))
    u /= np.linalg.norm(u)
    v = np.cross(d, u)

    angles = np.linspace(0, 2 * np.pi, n_seg, endpoint=False)
    verts = [tip]  # index 0 = tip
    for a in angles:
        verts.append(base_center + radius * (np.cos(a) * u + np.sin(a) * v))
    verts.append(base_center)  # index n_seg+1 = base center
    verts = np.array(verts, dtype=float)

    faces = []
    for i in range(n_seg):
        j = (i + 1) % n_seg
        faces.append([0, i + 1, j + 1])  # side
        faces.append([n_seg + 1, j + 1, i + 1])  # base cap
    return verts, np.array(faces, dtype=np.uint32)


class _ScalingAxes:
    """Axis lines + arrowheads + labels that rescale with camera distance."""

    _AXES = [
        # (direction, line_color_f, label, label_color_i)
        (np.array([1, 0, 0], dtype=float), (1.0, 0.2, 0.2, 1.0),
         "X", (255, 80, 80, 255)),
        (np.array([0, 1, 0], dtype=float), (0.2, 1.0, 0.2, 1.0),
         "Y", (80, 255, 80, 255)),
        (np.array([0, 0, 1], dtype=float), (0.2, 0.5, 1.0, 1.0),
         "Z", (80, 128, 255, 255)),
    ]

    def __init__(self, view: gl.GLViewWidget) -> None:
        self._view = view
        self._lines: list[gl.GLLinePlotItem] = []
        self._arrows: list[gl.GLMeshItem] = []
        self._labels: list[gl.GLTextItem] = []

        for direction, color_f, text, color_i in self._AXES:
            line = gl.GLLinePlotItem(
                pos=np.zeros((2, 3), dtype=np.float32),
                color=color_f, width=2.0, antialias=True,
            )
            view.addItem(line)
            self._lines.append(line)

            # Arrowhead (placeholder geometry; updated in refresh)
            verts = np.zeros((3, 3), dtype=float)
            faces = np.array([[0, 1, 2]], dtype=np.uint32)
            md = gl.MeshData(vertexes=verts, faces=faces)
            arrow_color = np.array(color_f[:3] + (1.0,))
            arrow = gl.GLMeshItem(
                meshdata=md, smooth=False,
                color=arrow_color,
                drawEdges=False,
            )
            view.addItem(arrow)
            self._arrows.append(arrow)

            label = gl.GLTextItem(
                pos=np.zeros(3), text=text, color=color_i,
            )
            view.addItem(label)
            self._labels.append(label)

        # Monkey-patch the view's paintGL to refresh axes each frame
        _original_paint = view.paintGL

        def _paint_with_axes():
            self.refresh()
            _original_paint()

        view.paintGL = _paint_with_axes

        self.refresh()

    def refresh(self) -> None:
        """Recompute geometry based on current camera distance."""
        dist = self._view.cameraParams()["distance"]
        axis_len = dist * 0.25
        arrow_len = axis_len * 0.08
        arrow_r = arrow_len * 0.35

        for i, (direction, color_f, _text, _color_i) in enumerate(self._AXES):
            tip = direction * axis_len
            # Line from origin to base of arrowhead
            line_end = direction * (axis_len - arrow_len)
            self._lines[i].setData(
                pos=np.array([[0, 0, 0], line_end], dtype=np.float32),
            )

            # Arrowhead cone
            verts, faces = _cone_mesh(tip, direction, arrow_len, arrow_r)
            md = gl.MeshData(vertexes=verts.astype(np.float32), faces=faces)
            self._arrows[i].setMeshData(meshdata=md)

            # Label just past the tip
            self._labels[i].setData(pos=(tip + direction * arrow_len * 0.6).astype(np.float32))

    def all_items(self) -> list:
        """Return every GL item owned by this helper."""
        return list(self._lines) + list(self._arrows) + list(self._labels)


def _rotate_z(points: np.ndarray, angle: float) -> np.ndarray:
    """Rotate an (N, 3) array of points about the Z axis by *angle* radians."""
    c, s = np.cos(angle), np.sin(angle)
    rot = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]], dtype=float)
    return points @ rot.T


def _create_airplane_mesh(
    position: np.ndarray, heading_rad: float, scale: float = 150.0
) -> gl.GLMeshItem:
    """Build a simple airplane mesh at *position* oriented along *heading_rad*.

    The model is defined with the nose pointing along local +Y, then rotated
    so that +Y aligns with the heading direction.  Scale is roughly the
    fuselage length in meters.
    """
    # Vertices in local frame (nose along +Y, wings along X, up = +Z)
    verts = np.array([
        # Fuselage -----------------------------------------------------------
        [0, scale * 0.5, 0],              # 0  nose
        [-scale * 0.04, -scale * 0.5, 0], # 1  tail-left
        [scale * 0.04, -scale * 0.5, 0],  # 2  tail-right
        [0, -scale * 0.5, scale * 0.04],  # 3  tail-top
        # Main wings ---------------------------------------------------------
        [-scale * 0.4, -scale * 0.05, 0], # 4  left wing tip
        [scale * 0.4, -scale * 0.05, 0],  # 5  right wing tip
        # Horizontal tail wings ----------------------------------------------
        [-scale * 0.15, -scale * 0.45, 0],# 6  left tail-wing tip
        [scale * 0.15, -scale * 0.45, 0], # 7  right tail-wing tip
    ], dtype=float)

    faces = np.array([
        # Fuselage
        [0, 1, 2],  # bottom
        [0, 1, 3],  # left side
        [0, 2, 3],  # right side
        [1, 2, 3],  # back cap
        # Wings
        [0, 4, 1],  # left wing
        [0, 2, 5],  # right wing
        # Tail wings
        [1, 6, 3],  # left tail wing
        [2, 3, 7],  # right tail wing
    ], dtype=np.uint32)

    # Rotate to match heading then translate
    verts = _rotate_z(verts, heading_rad)
    verts += np.asarray(position, dtype=float)

    # Per-face colors: light gray fuselage, slightly darker wings
    n_faces = len(faces)
    colors = np.full((n_faces, 4), [0.85, 0.85, 0.88, 1.0])
    # Darken wing/tail faces slightly for visual contrast
    for idx in (4, 5, 6, 7):
        colors[idx] = [0.70, 0.72, 0.78, 1.0]

    md = gl.MeshData(vertexes=verts, faces=faces)
    mesh = gl.GLMeshItem(
        meshdata=md,
        faceColors=colors,
        smooth=False,
        drawEdges=True,
        edgeColor=(0.3, 0.3, 0.3, 1.0),
    )
    return mesh


def _create_antenna_beam(
    position: np.ndarray,
    depression_angle: float,
    look_side: str = "right",
    heading_rad: float = 0.0,
    beamwidth_deg: float = 10.0,
) -> gl.GLMeshItem:
    """Create a semi-transparent beam cone from *position* down to z=0.

    Parameters
    ----------
    position : array (3,)
        Platform position.
    depression_angle : float
        Depression angle in degrees below horizontal.
    look_side : str
        ``"right"`` or ``"left"``.
    heading_rad : float
        Platform heading in radians (0 = +Y axis, clockwise positive).
    beamwidth_deg : float
        Full cone beamwidth in degrees (default 10).
    """
    pos = np.asarray(position, dtype=float)
    altitude = pos[2]
    if altitude <= 0:
        # Cannot draw a beam if platform is at or below ground
        # Return an empty invisible mesh
        verts = np.zeros((3, 3), dtype=float)
        faces = np.array([[0, 1, 2]], dtype=np.uint32)
        md = gl.MeshData(vertexes=verts, faces=faces)
        return gl.GLMeshItem(meshdata=md, smooth=False)

    dep_rad = np.radians(depression_angle)
    half_bw = np.radians(beamwidth_deg / 2.0)

    # Slant range to ground at beam center
    slant_center = altitude / np.sin(dep_rad) if dep_rad > 0 else altitude * 10.0

    # The look direction in the local frame:
    #   heading along +Y, look_side="right" => +X direction
    side_sign = 1.0 if look_side == "right" else -1.0

    # Beam center direction in local frame (before heading rotation):
    #   cross-track = +X * side_sign, down = -Z
    #   depression below horizontal means angle from horizontal plane
    cx = np.cos(dep_rad) * side_sign
    cy = 0.0
    cz = -np.sin(dep_rad)
    center_dir = np.array([cx, cy, cz])

    # Build a pyramid with 4 edges around the beam center
    # Offsets: elevation +/-, azimuth +/- (in the beam's own frame)
    n_rim = 16  # number of rim points for a smoother cone
    angles = np.linspace(0, 2 * np.pi, n_rim, endpoint=False)

    # Construct rim points by perturbing the center direction
    # Use two orthogonal vectors in the plane perpendicular to center_dir
    # u = along-track (roughly Y), v = completes the triad
    forward = np.array([0, 1, 0], dtype=float)
    u = forward - center_dir * np.dot(forward, center_dir)
    u_norm = np.linalg.norm(u)
    if u_norm < 1e-9:
        u = np.array([1, 0, 0], dtype=float)
    else:
        u = u / u_norm
    v = np.cross(center_dir, u)

    rim_dirs = []
    for a in angles:
        offset = half_bw * (np.cos(a) * u + np.sin(a) * v)
        d = center_dir + offset
        d = d / np.linalg.norm(d)
        rim_dirs.append(d)
    rim_dirs = np.array(rim_dirs)

    # Scale each rim direction so it reaches z=0 (ground)
    rim_points = []
    for d in rim_dirs:
        if d[2] >= 0:
            # Ray going upward — clip to a large distance
            t = slant_center * 2.0
        else:
            t = -altitude / d[2]  # solve pos[2] + t*d[2] = 0
        rim_points.append(d * t)
    rim_local = np.array(rim_points)

    # Rotate by heading and translate
    rim_world = _rotate_z(rim_local, heading_rad) + pos

    # Apex is the platform position
    apex = pos.copy()

    # Build mesh: n_rim triangles (apex + consecutive rim pairs)
    n = len(rim_world)
    verts = np.vstack([apex.reshape(1, 3), rim_world])  # (n+1, 3)
    faces = []
    for i in range(n):
        faces.append([0, i + 1, (i + 1) % n + 1])
    # Bottom cap (fan from first rim point)
    for i in range(1, n - 1):
        faces.append([1, i + 1, i + 2])
    faces = np.array(faces, dtype=np.uint32)

    # Use per-vertex colors with alpha for reliable transparency
    n_verts = len(verts)
    vert_colors = np.full((n_verts, 4), [0.3, 0.6, 1.0, 0.25], dtype=float)
    # Make the apex (vertex 0) more opaque for visual anchor
    vert_colors[0] = [0.4, 0.7, 1.0, 0.5]

    md = gl.MeshData(vertexes=verts, faces=faces)
    md.setVertexColors(vert_colors)
    mesh = gl.GLMeshItem(
        meshdata=md,
        smooth=False,
        shader="balloon",
        drawEdges=True,
        edgeColor=(0.4, 0.7, 1.0, 0.6),
        glOptions="translucent",
    )
    return mesh


class SceneViewerPanel(QWidget):
    """3D scene viewer panel for visualizing SAR scene geometry.

    Displays point targets as colored scatter points, platform position,
    projected trajectory, a 3D airplane model, and antenna beam pattern.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._view = gl.GLViewWidget()
        layout.addWidget(self._view)

        # Add reference grid
        self._grid = gl.GLGridItem()
        self._grid.setSize(10000, 10000)
        self._grid.setSpacing(1000, 1000)
        self._view.addItem(self._grid)

        # XYZ axes (scale with camera zoom)
        self._axes = _ScalingAxes(self._view)

        # Camera defaults
        self._view.setCameraPosition(distance=8000, elevation=30, azimuth=45)

        # Track added items for clearing
        self._scene_items: list = []

    def update_scene(self, scene: Scene) -> None:
        """Refresh the 3D display with targets from *scene*.

        Does NOT auto-fit the camera — call :meth:`fit_camera` or
        :meth:`update_platform` afterwards so that the platform is
        also included in the view.
        """
        self.clear()
        self._add_point_targets(scene.point_targets)
        self._add_distributed_targets(scene.distributed_targets)

    def update_platform(
        self,
        start_position: np.ndarray | None = None,
        trajectory_positions: np.ndarray | None = None,
        depression_angle: float | None = None,
        look_side: str | None = None,
        heading_rad: float | None = None,
    ) -> None:
        """Show platform start position, trajectory, airplane, and beam.

        Parameters
        ----------
        start_position : array-like (3,), optional
            Platform start [x, y, z] in scene coordinates.
        trajectory_positions : array (N, 3), optional
            Full trajectory path.
        depression_angle : float, optional
            Antenna depression angle in degrees below horizontal.
        look_side : str, optional
            ``"right"`` or ``"left"`` — which side the antenna looks.
        heading_rad : float, optional
            Platform heading in radians (0 = +Y axis, positive = clockwise).
            If *None* and *trajectory_positions* has >= 2 points, heading is
            inferred from the first trajectory segment.
        """
        # Infer heading from trajectory if not provided
        if heading_rad is None and trajectory_positions is not None and len(trajectory_positions) >= 2:
            delta = trajectory_positions[1] - trajectory_positions[0]
            heading_rad = float(np.arctan2(delta[0], delta[1]))  # angle from +Y

        if start_position is not None:
            pos = np.array(start_position, dtype=float).reshape(1, 3)
            marker = gl.GLScatterPlotItem(
                pos=pos,
                color=(1.0, 1.0, 0.0, 1.0),  # yellow
                size=12.0,
                pxMode=True,
            )
            self._view.addItem(marker)
            self._scene_items.append(marker)

            # Add 3D airplane model
            airplane = _create_airplane_mesh(
                pos.ravel(), heading_rad if heading_rad is not None else 0.0,
            )
            self._view.addItem(airplane)
            self._scene_items.append(airplane)

            # Add antenna beam pattern
            if depression_angle is not None:
                beam = _create_antenna_beam(
                    pos.ravel(),
                    depression_angle,
                    look_side or "right",
                    heading_rad if heading_rad is not None else 0.0,
                )
                self._view.addItem(beam)
                self._scene_items.append(beam)

        if trajectory_positions is not None and len(trajectory_positions) > 1:
            line = gl.GLLinePlotItem(
                pos=trajectory_positions.astype(np.float32),
                color=(1.0, 1.0, 0.0, 0.6),  # yellow semi-transparent
                width=2.0,
                antialias=True,
            )
            self._view.addItem(line)
            self._scene_items.append(line)

        self._auto_camera()

    def update_antenna_beam(
        self,
        start_position: np.ndarray,
        depression_angle: float,
        look_side: str = "right",
        heading_rad: float = 0.0,
    ) -> None:
        """Add (or replace) the antenna beam cone independently.

        Parameters
        ----------
        start_position : array-like (3,)
            Platform position.
        depression_angle : float
            Depression angle in degrees below horizontal.
        look_side : str
            ``"right"`` or ``"left"``.
        heading_rad : float
            Platform heading in radians (0 = +Y).
        """
        pos = np.asarray(start_position, dtype=float).ravel()
        beam = _create_antenna_beam(pos, depression_angle, look_side, heading_rad)
        self._view.addItem(beam)
        self._scene_items.append(beam)

    def clear(self) -> None:
        """Remove all scene items (keeps grid and axes)."""
        for item in self._scene_items:
            self._view.removeItem(item)
        self._scene_items.clear()

    def fit_camera(self) -> None:
        """Fit camera to show all scene items (public API)."""
        self._auto_camera()

    def _auto_camera(self) -> None:
        """Fit camera to show all scene items."""
        if not self._scene_items:
            return
        # Collect all positions from scatter and line items
        all_points = []
        for item in self._scene_items:
            if isinstance(item, gl.GLScatterPlotItem):
                pos = item.pos
                if pos is not None and len(pos) > 0:
                    all_points.append(np.array(pos))
            elif isinstance(item, gl.GLLinePlotItem):
                pos = item.pos
                if pos is not None and len(pos) > 0:
                    all_points.append(np.array(pos))
        if not all_points:
            return
        all_pos = np.concatenate(all_points, axis=0)
        extent = float(np.max(np.ptp(all_pos, axis=0)))
        self._view.setCameraPosition(
            distance=max(extent * 1.8, 2000.0), elevation=30, azimuth=45
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _add_point_targets(self, targets: list[PointTarget]) -> None:
        if not targets:
            return
        positions = np.array([t.position for t in targets], dtype=float)
        rcs_vals = np.array([_rcs_to_scalar(t.rcs) for t in targets])

        # Normalise RCS for colormap
        rmin, rmax = rcs_vals.min(), rcs_vals.max()
        if rmax > rmin:
            normed = (rcs_vals - rmin) / (rmax - rmin)
        else:
            normed = np.full_like(rcs_vals, 0.5)

        colors = _colormap(normed)
        size = np.clip(5.0 + 10.0 * normed, 5.0, 15.0)

        scatter = gl.GLScatterPlotItem(
            pos=positions, color=colors, size=size, pxMode=True
        )
        self._view.addItem(scatter)
        self._scene_items.append(scatter)

    def _add_distributed_targets(
        self, targets: list[DistributedTarget]
    ) -> None:
        for dt in targets:
            self._add_one_distributed(dt)

    def _add_one_distributed(self, dt: DistributedTarget) -> None:
        # Build x/y coordinate vectors
        xs = dt.origin[0] + np.arange(dt.nx) * dt.cell_size
        ys = dt.origin[1] + np.arange(dt.ny) * dt.cell_size

        # Elevation surface (ny x nx)
        if dt.elevation is not None:
            zdata = dt.elevation + dt.origin[2]
        else:
            zdata = np.full((dt.ny, dt.nx), dt.origin[2])

        # Color from reflectivity
        if dt.reflectivity is not None:
            refl = dt.reflectivity
            rmin, rmax = refl.min(), refl.max()
            if rmax > rmin:
                normed = (refl - rmin) / (rmax - rmin)
            else:
                normed = np.full_like(refl, 0.5)
            # Build RGBA image (ny, nx, 4)
            flat = normed.ravel()
            rgba_flat = _colormap(flat)
            rgba = rgba_flat.reshape(dt.ny, dt.nx, 4)
        else:
            rgba = np.ones((dt.ny, dt.nx, 4), dtype=float)
            rgba[:, :, :3] = 0.5  # neutral grey

        surface = gl.GLSurfacePlotItem(
            x=xs,
            y=ys,
            z=zdata,
            colors=rgba,
            shader=None,
            smooth=False,
        )
        self._view.addItem(surface)
        self._scene_items.append(surface)


__all__ = ["SceneViewerPanel", "_ScalingAxes"]
