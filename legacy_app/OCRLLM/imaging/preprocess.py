"""
图像预处理 — HEIC 转换、自动裁剪、透视变换。
"""

from __future__ import annotations

import os
import logging
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from OCRLLM.config import AppConfig
from OCRLLM.core.utils import atomic_temp_path, ensure_dir

logger = logging.getLogger(__name__)


def imwrite_unicode(path: str, img: np.ndarray, params=None) -> bool:
    """cv2.imwrite 的替代，支持中文/Unicode 文件路径，原子写入避免中断留下截断文件。"""
    ext = os.path.splitext(path)[1]
    result, encoded = cv2.imencode(ext, img, params) if params else cv2.imencode(ext, img)
    if not result:
        return False
    tmp_path = atomic_temp_path(path)
    encoded.tofile(tmp_path)
    os.replace(tmp_path, path)
    return True


def convert_heic_to_jpg(image_path: str, temp_dir: str = "temp", quality: int = 85) -> str:
    """将 HEIC/HEIF 转 JPEG，非 HEIC 直接返回原路径。"""
    ext = os.path.splitext(image_path)[1].lower()
    if ext not in (".heic", ".heif"):
        return image_path

    try:
        import pillow_heif
        pillow_heif.register_heif_opener()
    except ImportError:
        raise RuntimeError("需安装 pillow-heif: pip install pillow-heif")

    from PIL import Image
    out_dir = os.path.join(temp_dir, "heic_converted")
    ensure_dir(out_dir)
    out_path = os.path.join(out_dir, Path(image_path).stem + ".jpg")

    img = Image.open(image_path).convert("RGB")
    img.save(out_path, "JPEG", quality=quality)
    logger.info("[HEIC] 转换: %s -> %s", image_path, out_path)
    return out_path


class ImagePreprocessor:
    """板书图片预处理器 — 裁剪黑板/白板区域。"""

    def __init__(self, cfg: Optional[AppConfig] = None, save_debug: bool = False):
        from OCRLLM.config import AppConfig
        self.cfg = cfg or AppConfig()
        self.save_debug = save_debug
        self.debug_dir = os.path.join(self.cfg.paths.temp_dir, "preprocess_debug")
        if save_debug:
            ensure_dir(self.debug_dir)

    def process_single(
        self,
        image_path: str,
        output_path: str = None,
        manual_quad: Optional[list] = None,
        crop_roi: Optional[tuple] = None,
    ) -> str:
        """预处理单张图片：HEIC 转换 → 裁剪/透视变换 → 保存。

        Args:
            image_path: 输入图片路径。
            output_path: 输出路径，None 则自动生成。
            manual_quad: 手动指定的四边形裁剪区域。
            crop_roi: 矩形裁剪区域 (x_min, y_min, x_max, y_max)。

        Returns:
            输出图片路径。
        """
        prefix = Path(image_path).stem
        image_path = convert_heic_to_jpg(image_path, self.cfg.paths.temp_dir, self.cfg.processing.image_quality)

        img = cv2.imdecode(np.fromfile(image_path, dtype=np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            raise FileNotFoundError(f"无法读取图片: {image_path}")

        self._save_debug(img, "01_original", prefix)

        if manual_quad is not None:
            img_cropped = self.perspective_crop(img, manual_quad)
        elif crop_roi is not None and crop_roi is not False:
            x_min, y_min, x_max, y_max = crop_roi
            h, w = img.shape[:2]
            x_min, y_min = max(0, min(int(x_min), w)), max(0, min(int(y_min), h))
            x_max, y_max = max(0, min(int(x_max), w)), max(0, min(int(y_max), h))
            img_cropped = img[y_min:y_max, x_min:x_max]
            if img_cropped.size == 0:
                img_cropped = img
        elif crop_roi is False:
            img_cropped = img
        else:
            img_cropped = self.auto_crop_board(img)

        self._save_debug(img_cropped, "02_cropped", prefix)

        if output_path is None:
            out_dir = os.path.join(self.cfg.paths.temp_dir, "board_processed")
            ensure_dir(out_dir)
            stem = Path(image_path).stem
            ext = Path(image_path).suffix.lower()
            # TIFF 不被多数视觉模型 API 接受，转为 JPEG
            if ext in (".tif", ".tiff"):
                ext = ".jpg"
            output_path = os.path.join(out_dir, stem + ext)

        ext = os.path.splitext(output_path)[1].lower()
        if ext in (".jpg", ".jpeg"):
            params = [cv2.IMWRITE_JPEG_QUALITY, self.cfg.processing.image_quality]
        elif ext == ".png":
            params = [cv2.IMWRITE_PNG_COMPRESSION, 3]
        else:
            params = None
        imwrite_unicode(output_path, img_cropped, params)
        return output_path

    def process_batch(
        self,
        image_paths: list[str],
        manual_quads: Optional[dict] = None,
        crop_roi: Optional[tuple] = None,
    ) -> list[str]:
        """批量预处理图片。

        Args:
            image_paths: 图片路径列表。
            manual_quads: 各图片的手动四边形映射。
            crop_roi: 统一矩形裁剪区域。

        Returns:
            处理后图片路径列表。
        """
        results = []
        for img_path in image_paths:
            quad = manual_quads.get(img_path) if manual_quads else None
            try:
                results.append(self.process_single(img_path, manual_quad=quad, crop_roi=crop_roi))
            except Exception as e:
                logger.warning("[PREPROCESS] 处理失败: %s: %s", img_path, e)
                results.append(img_path)
        return results

    def auto_crop_board(self, img: np.ndarray) -> np.ndarray:
        """自动检测并裁剪黑板/白板区域。

        使用 Canny 边缘检测和轮廓分析，尝试找到四边形区域并透视变换。

        Args:
            img: OpenCV BGR 图像。

        Returns:
            裁剪后的 OpenCV BGR 图像。
        """
        h, w = img.shape[:2]
        img_area = h * w

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blurred, self.cfg.imaging.canny_low, self.cfg.imaging.canny_high)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        edges = cv2.dilate(edges, kernel, iterations=2)

        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return img

        contours = sorted(contours, key=cv2.contourArea, reverse=True)
        for cnt in contours[:10]:
            area = cv2.contourArea(cnt)
            if area < img_area * self.cfg.imaging.min_contour_area_ratio:
                continue
            peri = cv2.arcLength(cnt, True)
            approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)
            if len(approx) == 4:
                pts = approx.reshape(4, 2).tolist()
                return self.perspective_crop(img, pts)

        largest = contours[0]
        if cv2.contourArea(largest) > img_area * self.cfg.imaging.min_contour_area_ratio:
            x, y, cw, ch = cv2.boundingRect(largest)
            return img[y:y + ch, x:x + cw]
        return img

    def perspective_crop(self, img: np.ndarray, quad: list) -> np.ndarray:
        """对图像执行四点透视变换裁剪。

        Args:
            img: OpenCV BGR 图像。
            quad: 四个角点坐标列表。

        Returns:
            透视变换后的矩形图像。
        """
        pts = np.array(quad, dtype=np.float32)
        pts = self._order_points(pts)

        widthA = np.linalg.norm(pts[0] - pts[1])
        widthB = np.linalg.norm(pts[3] - pts[2])
        maxW = int(max(widthA, widthB))

        heightA = np.linalg.norm(pts[0] - pts[3])
        heightB = np.linalg.norm(pts[1] - pts[2])
        maxH = int(max(heightA, heightB))

        dst = np.array([[0, 0], [maxW - 1, 0], [maxW - 1, maxH - 1], [0, maxH - 1]], dtype=np.float32)
        M = cv2.getPerspectiveTransform(pts, dst)
        return cv2.warpPerspective(img, M, (maxW, maxH))

    @staticmethod
    def _order_points(pts: np.ndarray) -> np.ndarray:
        rect = np.zeros((4, 2), dtype=np.float32)
        s = pts.sum(axis=1)
        rect[0] = pts[np.argmin(s)]
        rect[2] = pts[np.argmax(s)]
        d = np.diff(pts, axis=1)
        rect[1] = pts[np.argmin(d)]
        rect[3] = pts[np.argmax(d)]
        return rect

    def _save_debug(self, img: np.ndarray, name: str, prefix: str = ""):
        if not self.save_debug:
            return
        filename = f"{prefix}_{name}.jpg" if prefix else f"{name}.jpg"
        imwrite_unicode(os.path.join(self.debug_dir, filename), img)
