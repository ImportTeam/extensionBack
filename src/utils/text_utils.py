"""텍스트 처리 유틸리티"""
import re


def clean_product_name(product_name: str) -> str:
    """
    상품명에서 불필요한 특수문자, 괄호 안의 내용 제거
    
    예시:
    - "[카드할인] 삼성 오디세이 G5" -> "삼성 오디세이 G5"
    - "아이폰 15 프로 (자급제)" -> "아이폰 15 프로"
    
    Args:
        product_name: 원본 상품명
        
    Returns:
        정제된 상품명
    """
    if not product_name:
        return ""
    
    # 대괄호 안의 내용 제거
    cleaned = re.sub(r'\[.*?\]', '', product_name)
    
    # 소괄호 안의 내용 제거
    cleaned = re.sub(r'\(.*?\)', '', cleaned)
    
    # 특수문자 제거 (하이픈, 언더스코어는 유지)
    cleaned = re.sub(r'[^\w\s\-_가-힣]', '', cleaned)
    
    # 다중 공백을 단일 공백으로
    cleaned = re.sub(r'\s+', ' ', cleaned)
    
    return cleaned.strip()


def extract_price_from_text(price_text: str) -> int:
    """
    가격 텍스트에서 숫자만 추출
    
    예시:
    - "1,250,000원" -> 1250000
    - "450,000" -> 450000
    - "판매가: 1,500,000원" -> 1500000
    
    Args:
        price_text: 가격이 포함된 텍스트
        
    Returns:
        추출된 가격 (정수)
    """
    if not price_text:
        return 0
    
    # 숫자와 쉼표만 추출
    numbers = re.findall(r'[\d,]+', price_text)
    
    if not numbers:
        return 0
    
    # 가장 긴 숫자 문자열 선택 (보통 가격이 가장 긴 숫자)
    price_str = max(numbers, key=len)
    
    # 쉼표 제거 후 정수 변환
    try:
        return int(price_str.replace(',', ''))
    except ValueError:
        return 0


def calculate_similarity(text1: str, text2: str) -> float:
    """
    두 텍스트의 유사도를 계산 (간단한 단어 매칭 기반)
    
    Args:
        text1: 첫 번째 텍스트
        text2: 두 번째 텍스트
        
    Returns:
        0.0 ~ 1.0 사이의 유사도 점수
    """
    if not text1 or not text2:
        return 0.0
    
    words1 = set(text1.lower().split())
    words2 = set(text2.lower().split())
    
    if not words1 or not words2:
        return 0.0
    
    intersection = words1.intersection(words2)
    union = words1.union(words2)
    
    return len(intersection) / len(union)


def split_kr_en_boundary(text: str) -> str:
    """
    한글과 영어/숫자가 붙어 있는 경우 경계에 공백을 삽입합니다.

    예: 'N-시리즈BasicWhite' -> 'N-시리즈 BasicWhite'
    """
    if not text:
        return text

    import re
    normalized = re.sub(r'(?<=[\uAC00-\uD7A3])(?=[A-Za-z0-9])', ' ', text)
    normalized = re.sub(r'(?<=[A-Za-z0-9])(?=[\uAC00-\uD7A3])', ' ', normalized)
    # collapse multi spaces
    normalized = re.sub(r'\s+', ' ', normalized)
    return normalized.strip()


def normalize_search_query(text: str) -> str:
    """외부 쇼핑몰 상품명을 다나와 검색에 적합하게 정규화합니다.

    목표: 한글 브랜드/제품명 중심으로 남기고, 명백한 스펙/숫자 토큰은 제거합니다.
    
    최적화 전략:
    1. 특수 구분자 이후 제거 (스펙의 99%)
    2. 대문자 영어만 제거 (모델명이 아닌 것)
    3. 알려진 스펙 키워드 제거
    4. 불필요한 상품 설명 제거
    """
    if not text:
        return ""

    cleaned = clean_product_name(text)
    cleaned = split_kr_en_boundary(cleaned)

    # === Phase 1: 구분자 이후 내용 제거 (가장 효과적) ===
    # 쿠팡 스타일: "상품명 · 옵션1 · 옵션2"
    for sep in ['·', '•', '|']:
        if sep in cleaned:
            cleaned = cleaned.split(sep)[0].strip()
            break

    # === Phase 2: 명백한 스펙 제거 ===
    # 용량 (256GB, 1TB 등)
    cleaned = re.sub(r"\b\d+\s*(GB|TB|MB|KB)\b", " ", cleaned, flags=re.IGNORECASE)
    
    # 메모리 타입
    cleaned = re.sub(r"\b(DDR\d+|LPDDR\d+|GDDR\d+)\b", " ", cleaned, flags=re.IGNORECASE)
    
    # 저장소 타입
    cleaned = re.sub(r"\b(SSD|HDD|NVME|NVMe)\b", " ", cleaned, flags=re.IGNORECASE)
    
    # 연도 (2024, 2025 등)
    cleaned = re.sub(r"\b(19|20)\d{2}\b", " ", cleaned)
    
    # 운영체제
    cleaned = re.sub(r"\b(WIN(?:DOWS)?\s*\d+|Windows|HOME|PRO|Home|Pro)\b", " ", cleaned, flags=re.IGNORECASE)
    
    # 프로세서 세대/종류 (인텔 14세대, 라이젠 8000 등)
    cleaned = re.sub(r"\b(\d+\s*)?세대\b", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\b(인텔|라이젠|AMD)\s+\d+", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\b(세대|시리즈)\b", " ", cleaned, flags=re.IGNORECASE)
    
    # 스펙 기술 용어
    cleaned = re.sub(r"\b(코어|GHZ|MHZ|GHz|MHz|IPS|VA|FIPS)\b", " ", cleaned, flags=re.IGNORECASE)
    
    # 그래픽 관련 (RTX, GTX 등 지포스/라데온 모델명은 유지하되, 순수 기술 스펙은 제거)
    cleaned = re.sub(r"\b지포스\s+", " ", cleaned, flags=re.IGNORECASE)
    
    # 오디오 관련 스펙
    cleaned = re.sub(r"\b(액티브|노이즈|캔슬링|무선|유선|블루투스|입체음향|돌비)\b", " ", cleaned, flags=re.IGNORECASE)
    
    # 연결/포트 관련
    cleaned = re.sub(r"\b(USB-?C|Type-?C|HDMI|DP|Thunderbolt|3\.5mm|이어폰)\b", " ", cleaned, flags=re.IGNORECASE)
    
    # 상품 상태/구성 (정품, 리퍼, 세트, 구성, 포함 등)
    cleaned = re.sub(r"\b(정품|리퍼|새제품|중고|리뉴얼|패키지|세트|구성|포함|별도|추가)\b", " ", cleaned, flags=re.IGNORECASE)
    
    # 색상 (색상은 검색에 별로 도움이 안 되고, 상품 구분을 복잡하게 함)
    cleaned = re.sub(r"\b(화이트|블랙|실버|골드|그레이|블루|핑크|레드|그린|퍼플|로즈|샴페인|뉴트럼|차콜|브론즈|건메탈)\b", " ", cleaned, flags=re.IGNORECASE)
    
    # === Phase 3: 단독 영어 단어 제거 (BasicWhite의 White 같은 것) ===
    # 단독 대문자 영어 토큰 (BB1422SS-N의 N 같은 하나 글자는 제거, 하지만 모델명 보존)
    # N-시리즈 → 제거하되, RTX 4050은 유지
    cleaned = re.sub(r"\b([A-Z])\s+", " ", cleaned)  # 단독 대문자 제거
    
    # === Phase 4: 1-2자리 순수 숫자 제거 (16 → 제거, 하지만 4050은 유지) ===
    # "16 코어" → "16" 제거하되 "15인치"의 "15"도 제거
    cleaned = re.sub(r"\b([0-9]{1,2})\b(?![0-9])", " ", cleaned)  # 1-2자리만
    
    # === Phase 5: 공백 정리 ===
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    
    return cleaned


def extract_model_codes(text: str) -> list[str]:
    """상품명에서 모델코드 후보를 추출합니다.

    예: '... BB1422SS-N' -> ['BB1422SS-N']
    """
    if not text:
        return []

    normalized = split_kr_en_boundary(clean_product_name(text))
    tokens = [t for t in normalized.split() if t]

    # (영문+숫자 조합) 또는 (대문자/숫자/하이픈 조합) 형태의 토큰을 모델코드로 간주
    mixed_re = re.compile(r"^(?=.*\d)(?=.*[A-Za-z])[A-Za-z0-9][A-Za-z0-9\-_]{2,}$")
    caps_re = re.compile(r"^[A-Z0-9][A-Z0-9\-_]{4,}$")

    blacklist = {
        "WIN10", "WIN11", "WINDOWS", "HOME", "PRO", "SSD", "HDD", "NVME",
        "RAM", "PCIE", "PCIe",
    }

    codes: list[str] = []
    seen: set[str] = set()
    for tok in tokens:
        if tok in blacklist:
            continue
        if mixed_re.match(tok) or caps_re.match(tok):
            if tok not in seen:
                seen.add(tok)
                codes.append(tok)

    return codes


def fuzzy_score(query: str, candidate: str) -> float:
    """두 문자열의 유사도 점수(0~100).

    rapidfuzz가 설치되어 있으면 token_set_ratio를 사용하고,
    없으면 기존 calculate_similarity를 사용합니다.
    """
    if not query or not candidate:
        return 0.0

    try:
        from rapidfuzz import fuzz, utils  # type: ignore

        return float(
            fuzz.token_set_ratio(query, candidate, processor=utils.default_process)
        )
    except Exception:
        return calculate_similarity(query, candidate) * 100.0
