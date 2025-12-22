from src.utils.text_utils import parse_fe_options_text, build_option_query_tokens


def test_parse_fe_options_text_mixed_format():
    text = "색상: 스페이스 블랙, CPU 모델명 × GPU 모델명 × RAM용량 × 저장용량 × 키보드 언어: M5 10코어 × 10코어 × 16GB × 512GB × 한글"
    pairs = parse_fe_options_text(text)

    assert ("색상", "스페이스 블랙") in pairs
    assert ("CPU 모델명", "M5 10코어") in pairs
    assert ("GPU 모델명", "10코어") in pairs
    assert ("RAM용량", "16GB") in pairs
    assert ("저장용량", "512GB") in pairs
    assert ("키보드 언어", "한글") in pairs


def test_build_option_query_tokens_filters_and_normalizes_color():
    pairs = [
        ("색상", "스페이스 블랙"),
        ("배송", "모레(수) 12/24 도착 보장"),
        ("저장용량", "512GB"),
    ]
    tokens = build_option_query_tokens(pairs)

    # 색상은 공백 제거
    assert "스페이스블랙" in tokens
    # denylist/value regex에 의해 배송 관련은 제외
    assert not any(t.startswith("배송:") for t in tokens)
    assert "512GB" in tokens
