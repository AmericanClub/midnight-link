"""Render a QR payload (e.g. a raw EMV QRIS string) into a PNG data URL.

Uses only dependencies that are already installed in production (reportlab's pure-python
QR encoder for the module matrix + Pillow for the bitmap) — the VPS deploy does not run
`pip install`, so no new package may be introduced for this.
"""
import base64
import io
import logging

from PIL import Image
from reportlab.graphics.barcode import qrencoder

logger = logging.getLogger("midgate.qr_image")


def qr_png_bytes(text: str, *, scale: int = 8, border: int = 4) -> bytes:
    qr = qrencoder.QRCode(None, qrencoder.QRErrorCorrectLevel.M)
    # Byte mode = what every QRIS generator/scanner expects for EMV payloads.
    qr.dataList.append(qrencoder.QR8bitByte(text))
    qr.dataCache = None
    qr.make()
    n = qr.getModuleCount()
    side = n + 2 * border
    img = Image.new("1", (side, side), 1)
    px = img.load()
    for r in range(n):
        for c in range(n):
            if qr.isDark(r, c):
                px[c + border, r + border] = 0
    img = img.resize((side * scale, side * scale), Image.NEAREST)
    out = io.BytesIO()
    img.save(out, format="PNG", optimize=True)
    return out.getvalue()


def qr_data_url(text: str | None) -> str | None:
    """`data:image/png;base64,...` for an <img src>, or None if it cannot be rendered."""
    if not text:
        return None
    try:
        return "data:image/png;base64," + base64.b64encode(qr_png_bytes(str(text))).decode()
    except Exception as e:  # noqa: BLE001 — never break a payment over a rendering issue
        logger.error("QR render failed: %s", e)
        return None
