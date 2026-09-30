"""Tạo mã QR để người dùng quét và tham gia."""
from __future__ import annotations

import base64
import io

import qrcode


def qr_base64(data: str, box_size: int = 10) -> str:
    """Tạo ảnh QR dạng PNG base64."""
    qr = qrcode.QRCode(border=2, box_size=box_size)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#04223F", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def qr_html(data: str, size: int = 220) -> str:
    b64 = qr_base64(data)
    return f'<img src="data:image/png;base64,{b64}" style="width:{size}px;border-radius:12px;">'
