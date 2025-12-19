"""상품 테스트 자산 (엔진 독립)

- 단순 dict만 보관
- pytest fixture 선언하지 않음
"""

PRODUCTS = {
    "galaxy_buds3": {
        "title": "삼성전자 갤럭시 버즈3 프로 블루투스 이어폰",
        "price": 207900,
    },
    "galaxy_s25_ultra": {
        "title": "삼성전자 갤럭시 S25 Ultra 자급제 SM-S938N",
        "price": 1593200,
    },
    "macbook_air_m4": {
        "title": "Apple 2025 맥북 에어 13 M4",
        "price": 1430980,
    },
    "tcl_tv_55": {
        "title": "TCL 4K QLED Google TV 55인치",
        "price": 634230,
    },
    "shin_ramyeon": {
        "title": "농심 신라면 120g",
        "price": 2986,
    },
    "noguri": {
        "title": "농심 얼큰한 너구리 120g, 20개",
        "price": 16120,
    },
    "intel_i5_12400f": {
        "title": "[INTEL] 코어12세대 i5-12400F 벌크 쿨러미포함",
        "price": 190900,
    },
}
