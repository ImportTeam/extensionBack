"""봇 차단/실패 시나리오 자산 (엔진 독립)

- 실제 HTTP 상태코드가 아니라 의미(semantic) 중심으로 기록
"""

BOT_SCENARIOS = {
    "blocked": {
        "error": "BLOCKED",
        "expected_status": "blocked",
    },
    "timeout": {
        "error": "TIMEOUT",
        "expected_status": "timeout",
    },
    "parse_error": {
        "error": "PARSING_ERROR",
        "expected_status": "parse_error",
    },
}
