"""Stage 1b: turn a photo of a page into model-ready images.

Steps, each optional and individually testable:
1. Find the paper quadrilateral and warp it flat (removes sleeve curvature, table).
2. Grayscale + CLAHE + mild unsharp. No hard binarisation: VLMs read grayscale better.
3. Gentle bleed-through suppression by dividing out a large-scale background estimate.
4. Resize so the long side is ``long_side`` px.
5. Cut overlapping horizontal bands; bands are sent alongside the full page so the model
   sees each line at higher effective resolution.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np


@dataclass
class PreprocessConfig:
    long_side: int = 2200
    dewarp: bool = True
    min_quad_area: float = 0.30  # quad must cover this fraction of the photo
    max_quad_area: float = 0.97  # a quad covering (almost) the whole photo is not a page
    clahe_clip: float = 0.0  # off by default: CLAHE amplifies bleed-through
    bleed_kernel: int = 61  # odd; larger = smoother background estimate
    bleed_strength: float = 1.0  # 0 = off, 1 = full background normalisation
    levels_low: float = 0.30  # after normalisation: below -> black
    levels_high: float = 0.80  # above -> white; faint reverse-side ink lands here
    unsharp_amount: float = 0.4
    bands: int = 5
    band_overlap: float = 0.18
    jpeg_quality: int = 92


@dataclass
class ProcessedPage:
    page_path: Path
    band_paths: list[Path] = field(default_factory=list)
    quad: np.ndarray | None = None


def order_quad(pts: np.ndarray) -> np.ndarray:
    """Order 4 points as top-left, top-right, bottom-right, bottom-left."""
    pts = pts.reshape(4, 2).astype(np.float32)
    s = pts.sum(axis=1)
    d = np.diff(pts, axis=1).ravel()
    return np.array(
        [pts[np.argmin(s)], pts[np.argmin(d)], pts[np.argmax(s)], pts[np.argmax(d)]], np.float32
    )


def find_page_quad(
    img: np.ndarray, min_area_frac: float = 0.30, max_area_frac: float = 0.97
) -> np.ndarray | None:
    """Largest 4-corner contour that looks like a sheet of paper, or None."""
    h, w = img.shape[:2]
    scale = 800 / max(h, w)
    small = cv2.resize(img, (int(w * scale), int(h * scale)))
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)
    # Paper is the bright region; Otsu separates it from a darker table/sleeve edge.
    _, thr = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    thr = cv2.morphologyEx(thr, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    contours, _ = cv2.findContours(thr, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    best = None
    best_area = 0.0
    for c in contours:
        area = cv2.contourArea(c)
        frac = area / (small.shape[0] * small.shape[1])
        if frac < min_area_frac or frac > max_area_frac:
            continue
        peri = cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, 0.02 * peri, True)
        if len(approx) != 4:
            # fall back to the minimum-area rectangle of a large blob
            approx = cv2.boxPoints(cv2.minAreaRect(c)).astype(np.int32).reshape(-1, 1, 2)
        if area > best_area:
            best, best_area = approx, area
    if best is None:
        return None
    return order_quad(best.astype(np.float32) / scale)


def warp_to_quad(img: np.ndarray, quad: np.ndarray) -> np.ndarray:
    tl, tr, br, bl = quad
    width = int(max(np.linalg.norm(tr - tl), np.linalg.norm(br - bl)))
    height = int(max(np.linalg.norm(bl - tl), np.linalg.norm(br - tr)))
    dst = np.array([[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]], np.float32)
    m = cv2.getPerspectiveTransform(quad, dst)
    return cv2.warpPerspective(img, m, (width, height), flags=cv2.INTER_CUBIC)


def suppress_bleed(gray: np.ndarray, kernel: int, strength: float) -> np.ndarray:
    if strength <= 0:
        return gray
    kernel = kernel if kernel % 2 else kernel + 1
    background = cv2.medianBlur(gray, kernel).astype(np.float32) + 1.0
    normalised = np.clip(gray.astype(np.float32) / background * 255.0, 0, 255)
    out = (1 - strength) * gray.astype(np.float32) + strength * normalised
    return out.astype(np.uint8)


def levels(gray: np.ndarray, low: float, high: float) -> np.ndarray:
    """Linear stretch: values <= low*255 become black, >= high*255 become white."""
    if high <= low:
        return gray
    f = gray.astype(np.float32) / 255.0
    f = np.clip((f - low) / (high - low), 0.0, 1.0)
    return (f * 255.0).astype(np.uint8)


def enhance(img: np.ndarray, cfg: PreprocessConfig) -> np.ndarray:
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    gray = suppress_bleed(gray, cfg.bleed_kernel, cfg.bleed_strength)
    if cfg.clahe_clip > 0:
        clahe = cv2.createCLAHE(clipLimit=cfg.clahe_clip, tileGridSize=(8, 8))
        gray = clahe.apply(gray)
    gray = levels(gray, cfg.levels_low, cfg.levels_high)
    if cfg.unsharp_amount > 0:
        blur = cv2.GaussianBlur(gray, (0, 0), 2.0)
        gray = cv2.addWeighted(gray, 1 + cfg.unsharp_amount, blur, -cfg.unsharp_amount, 0)
    return gray


def resize_long_side(img: np.ndarray, long_side: int) -> np.ndarray:
    h, w = img.shape[:2]
    scale = long_side / max(h, w)
    if abs(scale - 1) < 1e-3:
        return img
    interp = cv2.INTER_AREA if scale < 1 else cv2.INTER_CUBIC
    return cv2.resize(img, (round(w * scale), round(h * scale)), interpolation=interp)


def cut_bands(img: np.ndarray, n: int, overlap: float) -> list[np.ndarray]:
    if n <= 1:
        return [img]
    h = img.shape[0]
    step = h / (n - (n - 1) * overlap)
    band_h = round(step)
    stride = step * (1 - overlap)
    bands = []
    for i in range(n):
        y0 = round(i * stride)
        y1 = min(h, y0 + band_h)
        bands.append(img[y0:y1])
    return bands


def preprocess_image(
    img: np.ndarray, cfg: PreprocessConfig
) -> tuple[np.ndarray, list[np.ndarray], np.ndarray | None]:
    quad = find_page_quad(img, cfg.min_quad_area, cfg.max_quad_area) if cfg.dewarp else None
    if quad is not None:
        img = warp_to_quad(img, quad)
    gray = enhance(img, cfg)
    gray = resize_long_side(gray, cfg.long_side)
    bands = cut_bands(gray, cfg.bands, cfg.band_overlap)
    return gray, bands, quad


def preprocess_page(
    src: Path, page_id: str, out_dir: Path, cfg: PreprocessConfig | None = None
) -> ProcessedPage:
    cfg = cfg or PreprocessConfig()
    out_dir.mkdir(parents=True, exist_ok=True)
    img = cv2.imread(str(src), cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError(f"cannot read image {src}")
    gray, bands, quad = preprocess_image(img, cfg)
    page_path = out_dir / f"{page_id}.jpg"
    params = [cv2.IMWRITE_JPEG_QUALITY, cfg.jpeg_quality]
    cv2.imwrite(str(page_path), gray, params)
    band_paths = []
    for i, band in enumerate(bands):
        p = out_dir / f"{page_id}_band{i}.jpg"
        cv2.imwrite(str(p), band, params)
        band_paths.append(p)
    return ProcessedPage(page_path=page_path, band_paths=band_paths, quad=quad)
