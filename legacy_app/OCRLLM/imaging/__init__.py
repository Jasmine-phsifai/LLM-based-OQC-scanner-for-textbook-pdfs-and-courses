"""
imaging 子包 — 按需导入以避免缺少可选依赖时崩溃。
"""


def __getattr__(name):
    """延迟导入，仅在实际使用时加载。"""
    if name == "RapidOCREngine":
        from OCRLLM.imaging.ocr_engine import RapidOCREngine
        return RapidOCREngine
    if name == "run_tbpu":
        from OCRLLM.imaging.tbpu import run_tbpu
        return run_tbpu
    if name == "pdf_to_images":
        from OCRLLM.imaging.pdf_renderer import pdf_to_images
        return pdf_to_images
    if name == "is_scanned_pdf":
        from OCRLLM.imaging.scan_detector import is_scanned_pdf
        return is_scanned_pdf
    if name == "imwrite_unicode":
        from OCRLLM.imaging.imwrite_unicode import imwrite_unicode
        return imwrite_unicode
    if name == "extract_audio":
        from OCRLLM.imaging.audio_extractor import extract_audio
        return extract_audio
    raise AttributeError(f"module 'OCRLLM.imaging' has no attribute {name!r}")
