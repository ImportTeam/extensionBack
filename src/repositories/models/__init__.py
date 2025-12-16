"""Models package"""
import sys
from pathlib import Path
import importlib.util

# 부모 디렉토리의 models.py를 import하기 위한 특수 처리
# models/ 디렉토리가 models.py를 가리고 있으므로 직접 로드
models_py_path = Path(__file__).parent.parent / "models.py"
spec = importlib.util.spec_from_file_location("models_base", models_py_path)
models_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(models_module)

SearchLog = models_module.SearchLog
PriceCache = getattr(models_module, "PriceCache", None)

# SearchFailure 모델 (이 패키지 내)
from src.repositories.models.search_failure import SearchFailure

__all__ = ["SearchFailure", "SearchLog", "PriceCache"]

