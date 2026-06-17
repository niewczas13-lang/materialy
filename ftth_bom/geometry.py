from __future__ import annotations

import math
import struct


Point = tuple[float, float]
Line = tuple[Point, ...]


def read_gpkg_point(blob: bytes | None) -> Point | None:
    parsed = read_gpkg_geometry(blob)
    if not parsed:
        return None
    geometry_type, geometry = parsed
    if geometry_type != "POINT":
        return None
    return geometry[0] if geometry else None


def read_gpkg_lines(blob: bytes | None) -> list[Line]:
    parsed = read_gpkg_geometry(blob)
    if not parsed:
        return []
    geometry_type, geometry = parsed
    if geometry_type == "LINESTRING":
        return [tuple(geometry)] if len(geometry) >= 2 else []
    if geometry_type == "MULTILINESTRING":
        return [tuple(line) for line in geometry if len(line) >= 2]
    return []


def read_gpkg_geometry(blob: bytes | None):
    if not blob or len(blob) < 9 or blob[:2] != b"GP":
        return None
    flags = blob[3]
    envelope_code = (flags >> 1) & 0b111
    offset = 8 + _envelope_size(envelope_code)
    if offset >= len(blob):
        return None
    try:
        geometry_type, geometry, _ = _read_wkb(blob, offset)
    except (struct.error, ValueError, IndexError):
        return None
    return geometry_type, geometry


def point_to_line_distance(point: Point, line: Line) -> float:
    if len(line) < 2:
        return math.inf
    return min(_point_to_segment_distance(point, line[index], line[index + 1]) for index in range(len(line) - 1))


def _envelope_size(code: int) -> int:
    if code == 0:
        return 0
    if code == 1:
        return 32
    if code in {2, 3}:
        return 48
    if code == 4:
        return 64
    return 0


def _read_wkb(blob: bytes, offset: int):
    byte_order = blob[offset]
    offset += 1
    endian = "<" if byte_order == 1 else ">"
    geometry_type = struct.unpack_from(endian + "I", blob, offset)[0]
    offset += 4
    base_type = geometry_type % 1000

    if base_type == 1:
        point = struct.unpack_from(endian + "dd", blob, offset)
        return "POINT", [point], offset + 16

    if base_type == 2:
        count = struct.unpack_from(endian + "I", blob, offset)[0]
        offset += 4
        points = []
        for _ in range(count):
            points.append(struct.unpack_from(endian + "dd", blob, offset))
            offset += 16
        return "LINESTRING", points, offset

    if base_type == 5:
        count = struct.unpack_from(endian + "I", blob, offset)[0]
        offset += 4
        lines = []
        for _ in range(count):
            child_type, child_geometry, offset = _read_wkb(blob, offset)
            if child_type == "LINESTRING":
                lines.append(tuple(child_geometry))
        return "MULTILINESTRING", lines, offset

    raise ValueError(f"Unsupported WKB geometry type: {geometry_type}")


def _point_to_segment_distance(point: Point, start: Point, end: Point) -> float:
    px, py = point
    ax, ay = start
    bx, by = end
    dx = bx - ax
    dy = by - ay
    if dx == 0 and dy == 0:
        return math.hypot(px - ax, py - ay)
    ratio = ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)
    ratio = max(0.0, min(1.0, ratio))
    closest_x = ax + ratio * dx
    closest_y = ay + ratio * dy
    return math.hypot(px - closest_x, py - closest_y)
