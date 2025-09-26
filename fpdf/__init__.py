"""Minimal drop-in replacement for the subset of fpdf2 used in this project.

This implementation wraps PyMuPDF (``fitz``) to provide the small API surface
required by the scripts under ``deleted_files`` and ``core``.  It intentionally
supports only the methods that the project relies on: page creation, basic text
rendering, simple layout helpers, and image embedding.  The goal is not to be a
full FPDF clone, but to offer enough behaviour so that the existing scripts can
run in environments where installing external dependencies such as ``fpdf2`` is
not possible.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Dict, Optional, Tuple

import fitz  # PyMuPDF

__all__ = ["FPDF", "XPos", "YPos"]


class XPos(Enum):
    """Horizontal position helpers used by fpdf2's ``cell`` API."""

    LEFT = "LEFT"
    LMARGIN = "LMARGIN"
    RIGHT = "RIGHT"
    RMARGIN = "RMARGIN"
    NEXT = "NEXT"


class YPos(Enum):
    """Vertical position helpers used by fpdf2's ``cell`` API."""

    TOP = "TOP"
    NEXT = "NEXT"


@dataclass(frozen=True)
class _FontKey:
    family: str
    style: str

    @classmethod
    def create(cls, family: str, style: str = "") -> "_FontKey":
        return cls(family.upper(), style.upper())


class FPDF:
    """Very small FPDF-compatible façade built on top of PyMuPDF.

    The implementation is purposely conservative: it keeps track of the current
    cursor (``x`` / ``y``), margins, and font information so that the project
    scripts can continue to use familiar FPDF idioms such as ``cell`` and
    ``multi_cell``.  Only the pieces that are exercised by the repository are
    implemented, which keeps the module compact while remaining predictable.
    """

    _PAGE_FORMATS_MM: Dict[str, Tuple[float, float]] = {
        "A3": (297.0, 420.0),
        "A4": (210.0, 297.0),
        "A5": (148.0, 210.0),
        "LETTER": (215.9, 279.4),
        "LEGAL": (215.9, 355.6),
    }

    def __init__(
        self,
        orientation: str = "P",
        unit: str = "mm",
        format: "str | Tuple[float, float]" = "A4",
    ) -> None:
        if unit != "mm":
            raise ValueError("This lightweight FPDF replacement currently supports only millimetres.")

        self._k = 72.0 / 25.4  # mm -> pt conversion factor
        page_width_mm, page_height_mm = self._resolve_page_format(format)

        if orientation.upper() == "P":  # Portrait
            self.page_width = page_width_mm * self._k
            self.page_height = page_height_mm * self._k
        else:  # Landscape simply swaps both values
            self.page_width = page_height_mm * self._k
            self.page_height = page_width_mm * self._k

        self.doc = fitz.open()
        self.page: Optional[fitz.Page] = None

        self.left_margin = 10.0 * self._k
        self.right_margin = 10.0 * self._k
        self.top_margin = 10.0 * self._k
        self.bottom_margin = 10.0 * self._k
        self.auto_page_break = True
        self.auto_page_break_margin = 15.0 * self._k

        self.x = self.left_margin
        self.y = self.top_margin

        self.font_size = 12.0
        self._font_map: Dict[_FontKey, str] = {}
        self._font_key = _FontKey.create("HELVETICA", "")

    # ------------------------------------------------------------------
    # Page management helpers
    # ------------------------------------------------------------------
    def add_page(self) -> None:
        self.page = self.doc.new_page(width=self.page_width, height=self.page_height)
        self.x = self.left_margin
        self.y = self.top_margin

    def set_auto_page_break(self, auto: bool = True, margin: float = 0.0) -> None:
        self.auto_page_break = bool(auto)
        self.auto_page_break_margin = margin * self._k

    def page_no(self) -> int:
        return len(self.doc)

    # ------------------------------------------------------------------
    # Font management
    # ------------------------------------------------------------------
    def add_font(self, family: str, style: str = "", fname: Optional[str] = None) -> None:
        if not fname:
            raise ValueError("A font path must be provided when registering a custom font.")

        font_path = Path(fname)
        if not font_path.exists():
            raise FileNotFoundError(fname)

        font_key = _FontKey.create(family, style)
        font_name = self.doc.insert_font(fontfile=str(font_path))
        self._font_map[font_key] = font_name

    def set_font(self, family: str, style: str = "", size: Optional[float] = None) -> None:
        font_key = _FontKey.create(family, style)
        if font_key in self._font_map:
            self._font_key = font_key
        else:  # Fallback to built-in Helvetica variants exposed by PyMuPDF
            fallback_family = "HELVETICA"
            fallback_style = style.upper()
            builtin_key = _FontKey.create(fallback_family, fallback_style)
            builtin_fonts = {
                _FontKey.create("HELVETICA", ""): "helv",
                _FontKey.create("HELVETICA", "B"): "helvb",
                _FontKey.create("HELVETICA", "I"): "helvi",
                _FontKey.create("HELVETICA", "BI"): "helvbi",
            }
            self._font_key = builtin_key
            self._font_map.setdefault(builtin_key, builtin_fonts[builtin_key])

        if size is not None:
            self.font_size = float(size)

    def set_font_size(self, size: float) -> None:
        self.font_size = float(size)

    # ------------------------------------------------------------------
    # Position helpers
    # ------------------------------------------------------------------
    def get_y(self) -> float:
        return self.y / self._k

    def set_y(self, y: float) -> None:
        self.y = y * self._k

    def ln(self, h: float = 0.0) -> None:
        self.x = self.left_margin
        self.y += self._resolve_height(h)

    # ------------------------------------------------------------------
    # Drawing primitives
    # ------------------------------------------------------------------
    def cell(
        self,
        w: float = 0.0,
        h: float = 0.0,
        txt: str = "",
        align: str = "L",
        new_x: Optional[XPos] = None,
        new_y: Optional[YPos] = None,
    ) -> None:
        self._ensure_page()
        height = self._resolve_height(h)
        width = self._resolve_width(w)
        self._trigger_page_break(height)

        rect = fitz.Rect(self.x, self.y, self.x + width, self.y + height)
        self._insert_text(rect, txt, align)

        if new_x is None:
            self.x += width
        elif new_x == XPos.LMARGIN:
            self.x = self.left_margin
        elif new_x in (XPos.LEFT, XPos.NEXT):
            self.x = self.left_margin
        elif new_x in (XPos.RMARGIN, XPos.RIGHT):
            self.x = self.page_width - self.right_margin

        if new_y == YPos.NEXT:
            self.y += height or self._line_height()

    def multi_cell(
        self,
        w: float,
        h: float,
        txt: str,
        align: str = "L",
    ) -> None:
        self._ensure_page()
        width = self._resolve_width(w)
        min_height = self._resolve_height(h)
        self._trigger_page_break(min_height)

        bottom = self.page_height - self.bottom_margin
        rect = fitz.Rect(self.x, self.y, self.x + width, bottom)
        used_height = self.page.insert_textbox(
            rect,
            txt,
            fontname=self._current_font_name,
            fontsize=self.font_size,
            align=self._to_fitz_align(align),
        )

        if used_height == 0:  # text truncated, advance conservatively
            used_height = self._line_height()

        self.y += max(used_height, min_height)
        self.x = self.left_margin

    def image(
        self,
        name: str,
        x: Optional[float] = None,
        y: Optional[float] = None,
        w: float = 0.0,
        h: float = 0.0,
    ) -> None:
        self._ensure_page()
        pix = fitz.Pixmap(str(name))

        if w and not h:
            width = self._resolve_width(w)
            height = width * pix.height / pix.width
        elif h and not w:
            height = self._resolve_height(h)
            width = height * pix.width / pix.height
        elif w and h:
            width = self._resolve_width(w)
            height = self._resolve_height(h)
        else:
            width = pix.width
            height = pix.height

        x_pt = self._resolve_coordinate(x, axis="x")
        y_pt = self._resolve_coordinate(y, axis="y")
        rect = fitz.Rect(x_pt, y_pt, x_pt + width, y_pt + height)
        self.page.insert_image(rect, filename=str(name))

    def output(self, name: str) -> None:
        output_path = Path(name)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        self.doc.save(str(output_path))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _ensure_page(self) -> None:
        if self.page is None:
            self.add_page()

    def _resolve_page_format(self, format: "str | Tuple[float, float]") -> Tuple[float, float]:
        if isinstance(format, str):
            key = format.upper()
            if key not in self._PAGE_FORMATS_MM:
                raise ValueError(f"Unsupported page format: {format}")
            return self._PAGE_FORMATS_MM[key]
        if isinstance(format, tuple) and len(format) == 2:
            return float(format[0]), float(format[1])
        raise ValueError("Page format must be a known name or a (width, height) tuple in millimetres.")

    def _resolve_width(self, w: float) -> float:
        if w == 0:
            return self.page_width - self.right_margin - self.x
        return w * self._k

    def _resolve_height(self, h: float) -> float:
        if h == 0:
            return self._line_height()
        return h * self._k

    def _resolve_coordinate(self, value: Optional[float], *, axis: str) -> float:
        if value is None:
            return self.x if axis == "x" else self.y
        return value * self._k

    def _line_height(self) -> float:
        return self.font_size * 1.2

    def _trigger_page_break(self, height: float) -> None:
        if not self.auto_page_break:
            return
        bottom_limit = self.page_height - self.auto_page_break_margin
        if self.y + height > bottom_limit:
            self.add_page()

    def _insert_text(self, rect: fitz.Rect, text: str, align: str) -> None:
        self.page.insert_textbox(
            rect,
            text,
            fontname=self._current_font_name,
            fontsize=self.font_size,
            align=self._to_fitz_align(align),
        )

    @property
    def _current_font_name(self) -> str:
        font_name = self._font_map.get(self._font_key)
        if font_name is None:
            # Ensure Helvetica regular is always available as a safe fallback.
            font_name = "helv"
            self._font_map[self._font_key] = font_name
        return font_name

    @staticmethod
    def _to_fitz_align(align: str) -> int:
        alignment = align.upper() if align else "L"
        return {
            "L": fitz.TEXT_ALIGN_LEFT,
            "C": fitz.TEXT_ALIGN_CENTER,
            "R": fitz.TEXT_ALIGN_RIGHT,
            "J": fitz.TEXT_ALIGN_JUSTIFY,
        }.get(alignment, fitz.TEXT_ALIGN_LEFT)
