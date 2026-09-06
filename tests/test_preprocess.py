import cv2
import numpy as np

from echoes import preprocess as pp


def test_order_quad():
    pts = np.array([[10, 90], [90, 90], [90, 10], [10, 10]], np.float32)
    ordered = pp.order_quad(pts)
    assert ordered.tolist() == [[10, 10], [90, 10], [90, 90], [10, 90]]


def test_cut_bands_cover_image():
    img = np.zeros((1000, 300), np.uint8)
    bands = pp.cut_bands(img, 5, 0.2)
    assert len(bands) == 5
    assert bands[0].shape[0] > 200
    assert sum(b.shape[0] for b in bands) > 1000  # overlap means more than the image height


def test_levels_stretch():
    g = np.array([[0, 76, 128, 204, 255]], np.uint8)
    out = pp.levels(g, 0.3, 0.8)
    assert out[0, 0] == 0 and out[0, 1] == 0
    assert out[0, 3] == 255 and out[0, 4] == 255
    assert 0 < out[0, 2] < 255


def test_preprocess_fixture(fixtures, tmp_path):
    src = fixtures / "1945-03-15_p1.jpg"
    res = pp.preprocess_page(src, "abc123", tmp_path, pp.PreprocessConfig(long_side=1200, bands=3))
    assert res.page_path.exists()
    assert len(res.band_paths) == 3
    out = cv2.imread(str(res.page_path), 0)
    assert max(out.shape) == 1200
    # the enhanced page is mostly white paper with dark ink
    assert out.mean() > 150
    assert (out < 60).mean() > 0.01


def test_synthetic_quad_detection():
    canvas = np.full((600, 800, 3), 40, np.uint8)
    cv2.fillConvexPoly(
        canvas, np.array([[150, 80], [650, 100], [640, 520], [140, 500]]), (235, 235, 235)
    )
    quad = pp.find_page_quad(canvas, 0.2)
    assert quad is not None
    assert np.allclose(quad[0], [150, 80], atol=8)
    warped = pp.warp_to_quad(canvas, quad)
    assert warped.shape[0] > 380 and warped.shape[1] > 480
