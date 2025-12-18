"""리소스 파일(YAML/JSON) 로더 유틸리티"""
import os
import yaml
from typing import Any, Dict, Optional
from functools import lru_cache

from src.core.logging import logger


def get_resource_path(relative_path: str) -> str:
    """프로젝트 루트 기준 리소스 절대 경로 반환"""
    # src/utils/resource_loader.py -> src/utils -> src -> root
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base_dir, "resources", relative_path)


@lru_cache(maxsize=32)
def load_yaml_resource(relative_path: str) -> Dict[str, Any]:
    """YAML 리소스 로드 및 캐싱"""
    path = get_resource_path(relative_path)
    if not os.path.exists(path):
        logger.warning(f"Resource not found: {path}")
        return {}
    
    try:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        logger.error(f"Failed to load YAML resource {path}: {e}")
        return {}


def load_matching_variants() -> list[str | list[str]]:
    """제품군(Variant) 목록 로드 (동의어 그룹 포함 가능)"""
    data = load_yaml_resource("matching/variants.yaml")
    return data.get("variants", [])


def load_accessory_keywords() -> Dict[str, set[str]]:
    """액세서리 및 본체 힌트 키워드 로드"""
    data = load_yaml_resource("matching/accessories.yaml")
    return {
        "accessory_keywords": set(data.get("accessory_keywords", [])),
        "main_product_hints": set(data.get("main_product_hints", []))
    }


def load_search_substitutions() -> Dict[str, list[str]]:
    """검색어 대체 사전 로드"""
    data = load_yaml_resource("search/substitutions.yaml")
    return data.get("substitutions", {})


def load_search_categories() -> Dict[str, Any]:
    """카테고리 정의 로드"""
    data = load_yaml_resource("search/categories.yaml")
    return data.get("categories", {})


def load_matching_signals() -> Dict[str, set[str]]:
    """매칭 신호 관련 블랙리스트/접두사 로드"""
    data = load_yaml_resource("matching/signals.yaml")
    return {
        "model_code_blacklist": set(data.get("model_code_blacklist", [])),
        "named_number_stop_prefixes": set(data.get("named_number_stop_prefixes", []))
    }


def load_normalization_rules(is_it: bool = True) -> Dict[str, Any]:
    """정규화 규칙 로드 (IT/비IT 구분)"""
    filename = "normalization/it_noise_words.yaml" if is_it else "normalization/non_it_noise_words.yaml"
    return load_yaml_resource(filename)
