"""Báo lỗi CUDA rõ ràng, tránh OCR âm thầm chạy CPU khi đã yêu cầu GPU."""

import sys

from rag.errors import ConfigurationError


def require_device(device: str) -> str:
    if device.split(":", 1)[0].lower() != "cuda":
        return device
    import torch

    if torch.version.cuda is None:
        raise ConfigurationError(
            f"Python đang chạy ({sys.executable}) cài PyTorch chỉ hỗ trợ CPU. "
            "Dừng app và chạy .\\.ragvenv\\Scripts\\python.exe -m uvicorn api.main:app --host 127.0.0.1 --port 8000. "
            "Nếu vẫn lỗi, cài requirements-gpu.txt bằng Python của .ragvenv."
        )
    if not torch.cuda.is_available():
        raise ConfigurationError("Đã cài PyTorch CUDA nhưng chưa truy cập được GPU NVIDIA. "
                                 "Kiểm tra nvidia-smi và driver GPU trước khi import.")
    return device
