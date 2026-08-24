"""Own the process-wide lock required by PDFium."""

from threading import Lock


PDFIUM_LOCK = Lock()
