"""텍스트 처리 유틸리티"""
import re


_KIWI_INSTANCE = None


def _get_kiwi():
    global _KIWI_INSTANCE
    if _KIWI_INSTANCE is not None:
        return _KIWI_INSTANCE

    try:
        from kiwipiepy import Kiwi  # type: ignore

        _KIWI_INSTANCE = Kiwi()
        return _KIWI_INSTANCE
    except Exception:
        _KIWI_INSTANCE = None
        return None


def tokenize_keywords(text: str) -> set[str]:
    """검색/매칭용 키워드 토큰화.

    - Kiwi 사용 가능: 명사/영문/숫자 위주로 토큰화
    - 불가: 정규식 기반 폴백
    """
    if not text:
        return set()

    cleaned = split_kr_en_boundary(clean_product_name(text))
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if not cleaned:
        return set()

    stopwords = {
        "vs검색하기",
        "vs검색",
        "검색하기",
        "검색",
        "도움말",
    }

    kiwi = _get_kiwi()
    if kiwi is not None:
        tokens: list[str] = []
        try:
            for t in kiwi.tokenize(cleaned):
                # N*: 명사, SL: 외국어, SN: 숫자
                if t.tag.startswith("NN") or t.tag in {"SL", "SN"}:
                    form = (t.form or "").strip().lower()
                    if not form:
                        continue
                    if form in stopwords:
                        continue
                    tokens.append(form)
        except Exception:
            tokens = []

        if tokens:
            return set(tokens)

    # 폴백: 한글/영문/숫자 토큰
    rough = re.sub(r"[^\w\s가-힣]", " ", cleaned)
    toks = {t.lower() for t in rough.split() if t}
    return {t for t in toks if t not in stopwords}


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

    목표: 한글 브랜드/제품명 중심으로 남기되, 상품 식별에 중요한 토큰(모델 번호, 화면 크기,
    칩셋/세대 등)은 보존하고, 검색 방해가 되는 스펙/옵션 토큰만 제거합니다.
    
    최적화 전략:
    1. 특수 구분자 이후 제거 (스펙의 99%)
    2. 대문자 영어만 제거 (모델명이 아닌 것)
    3. 알려진 스펙 키워드 제거
    4. 불필요한 상품 설명 제거
    """
    if not text:
        return ""

    # === Phase 0: 원본에서 먼저 분리/노이즈 제거 ===
    # clean_product_name에서 '·' 같은 구분자가 제거되므로, 반드시 그 전에 split해야 함.
    raw = text
    # 쿠팡/확장프로그램 등에서 붙는 노이즈 제거
    raw = re.sub(r"\bVS\s*검색.*$", " ", raw, flags=re.IGNORECASE)
    raw = re.sub(r"\b검색\s*도움말\b", " ", raw)
    raw = re.sub(r"\bVS\s*검색하기\b", " ", raw, flags=re.IGNORECASE)

    # 쿠팡 스타일: "상품명 · 옵션1 · 옵션2" 또는 "상품명 | 옵션"
    for sep in ['·', '•', '|']:
        if sep in raw:
            raw = raw.split(sep)[0].strip()
            break

    cleaned = clean_product_name(raw)
    cleaned = split_kr_en_boundary(cleaned)

    # === Phase 1: (잔존하는) 구분자 처리 보강 ===
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
    # NOTE: 연도는 모델 식별에 중요한 경우가 있어 제거하지 않습니다.
    
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
    
    # === Phase 4: 숫자 토큰 정리 (필요한 숫자는 보존) ===
    # 1~2자리 숫자는 화면 크기(13/15), 제품 모델(아이폰 15), 세대 등의 핵심 식별자일 수 있어
    # 전역 제거를 하지 않습니다. 대신 명백한 스펙 컨텍스트(코어/스레드/와트 등) 앞의 숫자만 제거합니다.
    cleaned = re.sub(
        r"\b\d{1,2}\b(?=\s*(코어|core|스레드|thread|와트|w|hz|Hz|GHz|MHz)\b)",
        " ",
        cleaned,
        flags=re.IGNORECASE,
    )
    
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

    rapidfuzz가 설치되어 있으면 WRatio를 사용하고,
    없으면 기존 calculate_similarity를 사용합니다.
    """
    if not query or not candidate:
        return 0.0

    try:
        from rapidfuzz import fuzz, utils  # type: ignore

        # WRatio는 다양한 스코어러를 조합해 일반적인 상품명 매칭에 더 안정적입니다.
        return float(fuzz.WRatio(query, candidate, processor=utils.default_process))
    except Exception:
        return calculate_similarity(query, candidate) * 100.0


def extract_product_signals(text: str) -> dict:
    """상품명 매칭에 중요한 '범용' 신호를 추출합니다.

    특정 제품군(예: 맥북/아이폰)에 하드코딩하지 않고, 아래 일반 규칙으로 신호를 뽑습니다.
    - 모델코드(영문+숫자 혼합, 하이픈 포함)
    - 단위가 붙은 숫자(인치/형/cm/mm/GB/TB/Hz/W 등)
    - 3자리 이상 숫자(대개 GPU/제품번호/시리즈 등)
    - 연도(19xx/20xx)
    - '이름 + 번호' 패턴(예: "아이폰 15", "맥북 에어 13")
    """
    if not text:
        return {
            "years": set(),
            "model_codes": set(),
            "unit_numbers": set(),
            "big_numbers": set(),
            "named_numbers": {},
        }

    normalized = split_kr_en_boundary(clean_product_name(text))

    years = set(int(y) for y in re.findall(r"\b(19\d{2}|20\d{2})\b", normalized))

    model_codes = set(extract_model_codes(normalized))

    # 단위가 붙은 숫자 (예: 13인치, 15 형, 256GB, 2.4GHz)
    unit_numbers: set[str] = set()
    unit_patterns = [
        r"\b\d{1,3}(?:\.\d+)?\s*(?:인치|inch|\"|형)\b",
        r"\b\d{1,4}(?:\.\d+)?\s*(?:GB|TB|MB|KB)\b",
        r"\b\d{1,4}(?:\.\d+)?\s*(?:Hz|kHz|MHz|GHz)\b",
        r"\b\d{1,4}(?:\.\d+)?\s*(?:W|w)\b",
        r"\b\d{1,4}(?:\.\d+)?\s*(?:cm|mm)\b",
        r"\b\d{1,4}(?:\.\d+)?\s*(?:kg|g)\b",
    ]
    for pat in unit_patterns:
        for m in re.findall(pat, normalized, flags=re.IGNORECASE):
            unit_numbers.add(re.sub(r"\s+", "", m).lower())

    # 3자리 이상 숫자 토큰 (예: 4050, 14900, 9800 등)
    big_numbers = set(re.findall(r"\b\d{3,6}\b", normalized))

    # 이름 + 번호 (1~2단어 이름 뒤에 1~2자리 숫자)
    # 예: "아이폰 15", "맥북 에어 13", "갤럭시 S24"(S24는 분리된 경우만)
    named_numbers: dict[str, set[str]] = {}
    stop_prefix = {
        "win", "windows", "홈", "home", "pro", "프로",
        "정품", "리퍼", "새제품", "중고",
    }
    for name, num in re.findall(
        r"\b([A-Za-z가-힣]{2,}(?:\s+[A-Za-z가-힣]{2,})?)\s*(\d{1,2})\b",
        normalized,
    ):
        key = re.sub(r"\s+", " ", name).strip().lower()
        if not key or key in stop_prefix:
            continue
        named_numbers.setdefault(key, set()).add(num)

    return {
        "years": years,
        "model_codes": model_codes,
        "unit_numbers": unit_numbers,
        "big_numbers": big_numbers,
        "named_numbers": named_numbers,
    }


def is_accessory_trap(query: str, candidate: str) -> bool:
    """본품 검색어에 대해 액세서리 상품이 상위로 매칭되는 함정을 감지합니다.

    규칙(실무형 하드 필터):
    - 후보에 액세서리 키워드가 있고
    - 그 키워드가 쿼리에는 없으며
    - 쿼리가 '본품 카테고리'로 보이면
    => 액세서리 함정(True)
    """
    if not query or not candidate:
        return False

    accessory_keywords = {
        "케이스",
        "커버",
        "키스킨",
        "스킨",
        "필름",
        "보호필름",
        "강화유리",
        "거치대",
        "스탠드",
        "파우치",
        "가방",
        "충전기",
        "어댑터",
        "케이블",
        "허브",
        "젠더",
        "독",
        "도킹",
        "키보드커버",
        "키보드덮개",
        "교체용",
        "전용",
        "호환",
        "리필",
        "리필용",
        "스티커",
        "보호",
        "케이스형",
        "키캡",
        "키패드",
    }

    main_product_hints = {
        "노트북",
        "랩탑",
        "맥북",
        "울트라북",
        "태블릿",
        "아이패드",
        "스마트폰",
        "핸드폰",
        "아이폰",
        "갤럭시",
        "모니터",
        "tv",
        "데스크탑",
        "본체",
        "카메라",
        "렌즈",
        "이어폰",
        "헤드폰",
        "스피커",
        "마우스",
    }

    q_tokens = tokenize_keywords(query)
    c_tokens = tokenize_keywords(candidate)

    suspicious = c_tokens.intersection(accessory_keywords)
    if not suspicious:
        return False

    # 사용자가 액세서리를 직접 찾는 경우(쿼리에 액세서리 단어 포함)면 함정이 아님
    if not suspicious.isdisjoint(q_tokens):
        return False

    # 본품으로 보이는 쿼리에서만 강하게 필터링
    if q_tokens.isdisjoint(main_product_hints):
        return False

    return True


def weighted_match_score(query: str, candidate: str) -> float:
    """유사도(0~100)에 도메인 가중치를 더해 최종 스코어를 계산합니다."""
    if not query or not candidate:
        return 0.0

    # 0) 액세서리 포함관계 함정은 하드 필터로 제거
    if is_accessory_trap(query, candidate):
        return 0.0

    base = fuzzy_score(query, candidate)

    q = extract_product_signals(query)
    c = extract_product_signals(candidate)

    score = base

    # 1) 모델코드는 강한 신호: 쿼리에 모델코드가 있으면 후보에도 포함되는지 중요
    if q["model_codes"] and c["model_codes"]:
        if q["model_codes"].isdisjoint(c["model_codes"]):
            score -= 40.0
        else:
            score += 10.0
    elif q["model_codes"] and not c["model_codes"]:
        score -= 18.0

    # 2) 단위 붙은 숫자(13인치/256gb 등)는 비교적 강한 신호
    if q["unit_numbers"] and c["unit_numbers"]:
        if q["unit_numbers"].isdisjoint(c["unit_numbers"]):
            score -= 22.0
        else:
            score += 6.0

    # 3) 3자리 이상 숫자(4050 등): 쿼리의 큰 숫자가 후보에 없으면 패널티
    if q["big_numbers"]:
        if q["big_numbers"].isdisjoint(c["big_numbers"]):
            score -= 15.0
        else:
            score += 3.0

    # 4) '이름 + 번호' 패턴: 같은 이름인데 번호가 다르면 강한 패널티
    q_named: dict[str, set[str]] = q["named_numbers"]
    c_named: dict[str, set[str]] = c["named_numbers"]
    common_keys = set(q_named.keys()).intersection(c_named.keys())
    mismatch = False
    matched = False
    for k in common_keys:
        if q_named[k] and c_named[k]:
            if q_named[k].isdisjoint(c_named[k]):
                mismatch = True
            else:
                matched = True
    if mismatch:
        score -= 28.0
    elif matched:
        score += 8.0

    # 5) 연도는 보조 신호
    if q["years"] and c["years"]:
        if q["years"].isdisjoint(c["years"]):
            score -= 6.0
        else:
            score += 2.0

    # 0~100 범위로 클램프
    if score < 0:
        return 0.0
    if score > 100:
        return 100.0
    return float(score)
