"""
Sideways text (e.g. MRP / date / batch lines printed along a pack edge): the letter height
is the OCR box's WIDTH, not its height. Using the box height would report a 40 mm "letter"
and could hide a real Rule 7(2) font violation.
"""

import numpy as np

from app.services import ocr_pipeline


class _FakeReader:
    def __init__(self, results):
        self._results = results

    def readtext(self, image, detail=1, paragraph=False, rotation_info=None):
        return self._results


def _run(monkeypatch, results):
    monkeypatch.setattr(ocr_pipeline, "get_reader", lambda languages=None: _FakeReader(results))
    return ocr_pipeline.extract_text(np.zeros((1000, 1000, 3), dtype=np.uint8), dpi=254, languages=["en"])


def test_horizontal_line_uses_box_height(monkeypatch):
    box = [[100, 100], [400, 100], [400, 130], [100, 130]]  # 300 wide, 30 tall
    out = _run(monkeypatch, [(box, "MRP Rs. 10.00", 0.9)])
    assert out[0].font_height_px == 30.0


def test_sideways_line_uses_box_width(monkeypatch):
    box = [[100, 100], [130, 100], [130, 500], [100, 500]]  # 30 wide, 400 tall
    out = _run(monkeypatch, [(box, "MRP Rs. 10.00 incl. of all taxes", 0.9)])
    assert out[0].font_height_px == 30.0


def test_single_tall_character_is_not_treated_as_sideways(monkeypatch):
    box = [[100, 100], [112, 100], [112, 140], [100, 140]]  # a lone "1": 12 wide, 40 tall
    out = _run(monkeypatch, [(box, "1", 0.9)])
    assert out[0].font_height_px == 40.0
