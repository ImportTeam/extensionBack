"""Hard Mapping 로더 - YAML 리소스 로드 및 캐싱"""

from __future__ import annotations

import json
import os
from typing import Dict, Optional

import yaml

from src.core.logging import logger

# Hard Mapping 캐시 (싱글톤)
_HARD_MAPPING_CACHE: Optional[Dict[str, str]] = None
_HARD_MAPPING_SORTED_KEYS: Optional[list[str]] = None


def load_hard_mapping() -> Dict[str, str]:
    """
    Hard Mapping YAML 파일을 로드하고 캐시합니다.
    
    Returns:
        {"입력": "표준출력", ...}
    """
    global _HARD_MAPPING_CACHE
    
    if _HARD_MAPPING_CACHE is not None:
        return _HARD_MAPPING_CACHE
    
    yaml_path = os.path.join(
        os.path.dirname(__file__),
        "../../../resources/hard_mapping.yaml"
    )
    
    try:
        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        
        mapping = data.get("mapping", {})
        _HARD_MAPPING_CACHE = mapping
        
        logger.info(f"Hard Mapping loaded: {len(mapping)} entries")
        return mapping
    
    except FileNotFoundError:
        logger.warning(f"Hard Mapping file not found: {yaml_path}")
        _HARD_MAPPING_CACHE = {}
        return {}
    
    except Exception as e:
        logger.error(f"Failed to load Hard Mapping: {type(e).__name__}: {e}")
        _HARD_MAPPING_CACHE = {}
        return {}


def get_sorted_mapping_keys() -> list[str]:
    """
    Rule 1: Longest Match First
    매핑 키를 길이 내림차순으로 정렬해 반환
    
    Returns:
        ["맥북 에어 15", "맥북 에어", "맥북", ...]
    """
    global _HARD_MAPPING_SORTED_KEYS
    
    if _HARD_MAPPING_SORTED_KEYS is not None:
        return _HARD_MAPPING_SORTED_KEYS
    
    mapping = load_hard_mapping()
    sorted_keys = sorted(mapping.keys(), key=len, reverse=True)
    _HARD_MAPPING_SORTED_KEYS = sorted_keys
    
    return sorted_keys
