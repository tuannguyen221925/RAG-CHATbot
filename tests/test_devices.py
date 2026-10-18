import sys
from types import SimpleNamespace

import pytest

from rag.config import get_settings
from rag.devices import require_device
from rag.errors import ConfigurationError


def fake_torch(monkeypatch, *, cuda_build, available):
    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(
        version=SimpleNamespace(cuda=cuda_build),
        cuda=SimpleNamespace(is_available=lambda: available),
    ))


def test_cpu_does_not_require_torch(monkeypatch):
    monkeypatch.setitem(sys.modules, "torch", None)
    assert require_device("cpu") == "cpu"


def test_cuda_with_cpu_build_explains_wrong_runtime(monkeypatch):
    fake_torch(monkeypatch, cuda_build=None, available=False)
    with pytest.raises(ConfigurationError, match="chỉ hỗ trợ CPU") as error:
        require_device("cuda")
    assert sys.executable in str(error.value)
    assert "python.exe -m uvicorn" in str(error.value)


def test_cuda_without_gpu_explains_driver_check(monkeypatch):
    fake_torch(monkeypatch, cuda_build="12.6", available=False)
    with pytest.raises(ConfigurationError, match="nvidia-smi"):
        require_device("cuda")


def test_cuda_keeps_requested_device(monkeypatch):
    fake_torch(monkeypatch, cuda_build="12.6", available=True)
    assert require_device("cuda:0") == "cuda:0"


def test_ocr_gpu_rejects_cpu_fallback(monkeypatch):
    from rag.loader import get_ocr_reader

    monkeypatch.setenv("OCR_GPU", "true")
    get_settings.cache_clear()
    fake_torch(monkeypatch, cuda_build=None, available=False)
    get_ocr_reader.cache_clear()
    with pytest.raises(ConfigurationError, match="chỉ hỗ trợ CPU"):
        get_ocr_reader()
    get_ocr_reader.cache_clear()
