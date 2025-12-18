"""Hard Mapping 로더 - YAML 리소스 로드 및 캐싱"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional

import yaml

from src.core.logging import logger

from .hard_mapping_utils import normalize_for_hard_mapping_match

# Hard Mapping 캐시 (싱글톤)
_HARD_MAPPING_CACHE: Optional[Dict[str, str]] = None
_HARD_MAPPING_SORTED_KEYS: Optional[list[str]] = None


def get_hard_mapping_yaml_path() -> str:
    """repo 어디에서 실행되든 resources/hard_mapping.yaml을 찾습니다."""
    here = Path(__file__).resolve()
    for parent in [here.parent, *here.parents]:
        candidate = parent / "resources" / "hard_mapping.yaml"
        if candidate.exists():
            return str(candidate)

    # 마지막 폴백: 개발 중 상대경로(기존 형태)도 시도
    fallback = here.parent / "../../../resources/hard_mapping.yaml"
    return str(fallback)


def load_hard_mapping() -> Dict[str, str]:
    """
    Hard Mapping YAML 파일을 로드하고 캐시합니다.
    
    Returns:
        {"입력": "표준출력", ...}
    """
    global _HARD_MAPPING_CACHE
    
    if _HARD_MAPPING_CACHE is not None:
        return _HARD_MAPPING_CACHE
    
    yaml_path = get_hard_mapping_yaml_path()
    
    try:
        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        
        raw_mapping: dict[str, str] = data.get("mapping", {}) or {}

        # Stage 2와 동일한 규칙으로 키를 정규화해서 저장
        normalized_mapping: dict[str, str] = {}
        collisions: list[tuple[str, str]] = []
        for raw_key, value in raw_mapping.items():
            norm_key = normalize_for_hard_mapping_match(str(raw_key))
            if not norm_key:
                continue
            if norm_key in normalized_mapping and normalized_mapping[norm_key] != value:
                collisions.append((norm_key, str(raw_key)))
                continue
            normalized_mapping[norm_key] = value

        if collisions:
            logger.warning(
                "Hard Mapping key normalization collisions detected: "
                f"{len(collisions)} (first kept)."
            )

        _HARD_MAPPING_CACHE = normalized_mapping
        logger.info(f"Hard Mapping loaded: {len(normalized_mapping)} entries")
        return normalized_mapping
    
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
