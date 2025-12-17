"""Config-driven normalization (domain/tag based).

Goal:
- Keep matching/normalization general across categories (IT, food, fashion, ...)
- Move keywords/stopwords/synonyms/policies to resources/ configs
- Keep a safe fallback to the legacy normalize_search_query implementation

This module is intentionally conservative:
- Detects domain and emits tags, but only applies removals based on policies
- Uses simple token-level filtering for colors/units/accessory terms

"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Set, Tuple

from src.core.logging import logger

from .cleaning import clean_product_name, split_kr_en_boundary

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None


_SEPARATORS = ["·", "•", "|", "/", ","]


@dataclass(frozen=True)
class NormalizationContext:
    domain: str
    tags: Set[str]


def _find_repo_root() -> Path:
    """Find repository root by locating the 'resources' directory."""
    here = Path(__file__).resolve()
    for parent in [here.parent, *here.parents]:
        if (parent / "resources").is_dir():
            return parent
    # Fallback: assume working directory is repo root
    return Path.cwd()


@lru_cache(maxsize=1)
def _resources_root() -> Path:
    return _find_repo_root() / "resources"


def _read_text_lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    return [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]


def _safe_lower(s: str) -> str:
    return (s or "").lower()


def _tokenize_simple(text: str) -> list[str]:
    return [t for t in re.split(r"\s+", text.strip()) if t]


def _strip_separators_first(text: str) -> str:
    raw = text
    for sep in _SEPARATORS:
        if sep in raw:
            raw = raw.split(sep)[0].strip()
            break
    return raw


def _yaml_load(path: Path) -> Dict[str, Any]:
    if yaml is None:
        raise RuntimeError("PyYAML is not installed")
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _json_load(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8")) or {}
    except Exception as e:
        logger.debug(f"hard mapping json load failed: {type(e).__name__}: {e}")
        return {}


@lru_cache(maxsize=64)
def _load_yaml_cached(rel_path: str) -> Dict[str, Any]:
    return _yaml_load(_resources_root() / rel_path)


@lru_cache(maxsize=64)
def _load_wordset_cached(rel_path: str) -> Set[str]:
    return {w.strip().lower() for w in _read_text_lines(_resources_root() / rel_path)}


def _apply_synonyms(text: str, synonyms: Dict[str, str]) -> str:
    if not text or not synonyms:
        return text
    out = text
    for k, v in synonyms.items():
        if not k:
            continue
        out = out.replace(k, f" {v} ")
    return out


def _canonical_key(text: str) -> str:
    """하드매핑 키 매칭용 canonical form.

    - clean_product_name + 경계 분리 + 소문자 + 공백 정규화
    - 도메인/태그 정책 적용 전 단계에서 사용
    """
    v = split_kr_en_boundary(clean_product_name(text or ""))
    v = re.sub(r"\s+", " ", v).strip().lower()
    return v


@lru_cache(maxsize=1)
def _load_hard_mappings() -> Dict[str, str]:
    """resources/hard_mapping.json 로드.

    포맷: {"<key>": "<replacement>"}
    - key: canonical 비교 대상으로 사용(대소문자/공백 무시)
    - replacement: 실제 검색어로 사용할 문자열
    """
    raw = _json_load(_resources_root() / "hard_mapping.json")
    if not isinstance(raw, dict):
        return {}
    mappings: Dict[str, str] = {}
    for k, v in raw.items():
        if not k or not v:
            continue
        mappings[str(k)] = str(v)
    return mappings


def _apply_hard_mapping(text: str) -> Tuple[str, bool]:
    """하드 매핑 적용.

    - 1) canonical exact match
    - 2) canonical substring match (가장 긴 key 우선)
    """
    mappings = _load_hard_mappings()
    if not mappings:
        return text, False

    key = _canonical_key(text)
    if not key:
        return text, False

    # exact
    for raw_k, raw_v in mappings.items():
        if _canonical_key(raw_k) == key:
            return raw_v, True

    # substring (longest first)
    items = sorted(mappings.items(), key=lambda kv: len(_canonical_key(kv[0])), reverse=True)
    for raw_k, raw_v in items:
        ck = _canonical_key(raw_k)
        if ck and ck in key:
            return raw_v, True

    return text, False


@lru_cache(maxsize=1)
def _load_brands() -> list[dict[str, Any]]:
    """resources/brands.yaml 로드.

    포맷:
      version: 1
      brands:
        - id: apple
          domain: domain.electronics
          keywords: ["애플", "apple", ...]
    """
    cfg = _yaml_load(_resources_root() / "brands.yaml")
    brands = cfg.get("brands") if isinstance(cfg, dict) else None
    if not isinstance(brands, list):
        return []
    return [b for b in brands if isinstance(b, dict)]


def _domain_override_by_brand(text: str) -> Optional[str]:
    v = (text or "").lower()
    for b in _load_brands():
        domain = b.get("domain")
        keywords = b.get("keywords") or []
        if not domain or not isinstance(keywords, list):
            continue
        if any(isinstance(k, str) and k.lower() in v for k in keywords):
            return str(domain)
    return None


def _detect_domain(raw_text: str) -> str:
    cfg = _load_yaml_cached("mappings/detect/domain_rules.yaml")
    rules = cfg.get("rules") or []

    v = _safe_lower(raw_text)
    for rule in rules:
        mode = rule.get("mode")
        domain = rule.get("domain")
        if mode == "default" and domain:
            return str(domain)

        if mode != "score" or not domain:
            continue

        signals = rule.get("signals") or {}
        any_contains: list[str] = signals.get("any_contains") or []
        any_regex: list[str] = signals.get("any_regex") or []

        weights = rule.get("weights") or {}
        w_contains = int(weights.get("contains", 1))
        w_regex = int(weights.get("regex", 1))

        score = 0
        for kw in any_contains:
            if kw and kw.lower() in v:
                score += w_contains
        for pat in any_regex:
            try:
                if pat and re.search(pat, v, flags=re.IGNORECASE):
                    score += w_regex
            except re.error:
                continue

        threshold = float(rule.get("threshold", 1))
        if score >= threshold:
            return str(domain)

    return "domain.general"


def _emit_tags(text: str) -> Set[str]:
    cfg = _load_yaml_cached("mappings/detect/tag_rules.yaml")
    rules = cfg.get("rules") or []

    v = text or ""
    v_low = v.lower()

    tags: Set[str] = set()

    for rule in rules:
        match = rule.get("match") or {}
        match_type = match.get("type")
        emit = rule.get("emit_tags") or []

        ok = False
        if match_type == "any_of":
            keywords: Iterable[str] = match.get("keywords") or []
            ok = any(k and k.lower() in v_low for k in keywords)
        elif match_type == "regex":
            pat = match.get("pattern")
            if pat:
                try:
                    ok = re.search(str(pat), v, flags=re.IGNORECASE) is not None
                except re.error:
                    ok = False

        if ok:
            for t in emit:
                if t:
                    tags.add(str(t))

    return tags


def _apply_tag_policies(text: str, tags: Set[str], domain: str) -> str:
    cfg = _load_yaml_cached("policies/normalization.by_tag.yaml")
    by_tag = cfg.get("by_tag") or {}

    out = text

    for tag in tags:
        policy = by_tag.get(tag)
        if not policy:
            continue

        overrides = policy.get("overrides") or {}
        override = overrides.get(domain)
        if override:
            action = override.get("action")
        else:
            action = policy.get("action")

        if action == "replace":
            pat = policy.get("replace_pattern")
            rep = policy.get("replace_with", " ")
            if pat:
                try:
                    out = re.sub(str(pat), str(rep), out)
                except re.error:
                    pass

    return out


def _domain_policy(domain: str) -> Dict[str, Any]:
    # 1) categories/<domain_suffix>.yaml 우선
    # 예: domain.electronics -> resources/categories/electronics.yaml
    try:
        suffix = str(domain).split(".")[-1]
        category_path = _resources_root() / "categories" / f"{suffix}.yaml"
        category_cfg = _yaml_load(category_path)
        if isinstance(category_cfg, dict) and category_cfg:
            return dict(category_cfg)
    except Exception:
        pass

    # 2) 기존 정책 파일로 폴백
    cfg = _load_yaml_cached("policies/normalization.by_domain.yaml")
    by_domain = cfg.get("by_domain") or {}
    return dict(by_domain.get(domain) or by_domain.get("domain.general") or {})


def _remove_tokens_by_dict(text: str, words: Set[str]) -> str:
    if not text or not words:
        return text
    tokens = _tokenize_simple(text)
    kept: list[str] = []
    for tok in tokens:
        key = tok.strip().lower()
        if key in words:
            continue
        kept.append(tok)
    return " ".join(kept)


def normalize_search_query_with_resources(text: str, vendor: Optional[str] = None) -> str:
    """Normalize query using resources/ configs.

    This is intended as a general normalization pipeline.
    - vendor is optional and only affects vendor-specific synonym/noise removal.
    """
    if not text:
        return ""

    if yaml is None:
        raise RuntimeError("PyYAML not available; cannot use resource-based normalization")

    raw = text

    # 0) vendor/global synonym replacement (remove UI noise, standardize tokens)
    global_syn = (_load_yaml_cached("mappings/synonyms.global.yaml").get("synonyms") or {})
    raw = _apply_synonyms(raw, global_syn)

    if vendor:
        vendor_path = f"mappings/overrides/vendor_{vendor}.yaml"
        try:
            vendor_cfg = _load_yaml_cached(vendor_path)
            vendor_syn = vendor_cfg.get("synonyms") or {}
            raw = _apply_synonyms(raw, vendor_syn)
        except Exception:
            pass

    # 1) separator stripping before cleaning
    raw = _strip_separators_first(raw)

    # 2) basic cleaning
    cleaned = clean_product_name(raw)
    cleaned = split_kr_en_boundary(cleaned)

    # 0) (가장 강함) 하드 매핑
    mapped, changed = _apply_hard_mapping(cleaned)
    if changed:
        cleaned = split_kr_en_boundary(clean_product_name(mapped))

    # 1) (중간) 브랜드 사전으로 도메인 오버라이드
    domain = _domain_override_by_brand(cleaned) or _detect_domain(text)
    tags = _emit_tags(cleaned)

    # 4) apply tag policies (e.g., 2세대 -> 2, USB-C -> C)
    cleaned = _apply_tag_policies(cleaned, tags, domain)

    # 5) apply domain policies
    policy = _domain_policy(domain)

    # colors
    if policy.get("remove_colors") is True:
        colors = _load_wordset_cached("dictionaries/colors.txt")
        cleaned = _remove_tokens_by_dict(cleaned, colors)

    # units
    if policy.get("remove_units") is True:
        units = _load_wordset_cached("dictionaries/units.txt")
        cleaned = _remove_tokens_by_dict(cleaned, units)

    # accessory terms (minimal: use a small built-in set + allow future dictionary)
    if policy.get("remove_accessory_terms") is True:
        accessory = {
            "케이스",
            "커버",
            "필름",
            "보호필름",
            "강화유리",
            "파우치",
            "가방",
            "거치대",
            "스탠드",
            "스킨",
            "키스킨",
        }
        cleaned = _remove_tokens_by_dict(cleaned, {a.lower() for a in accessory})

    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    return cleaned
