"""가격 캐시 리포지토리 - DB 기반 영속 캐시."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from sqlalchemy.orm import Session

from src.core.logging import logger
from src.core.exceptions import DatabaseException
from src.repositories.models import PriceCache


class PriceCacheRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_fresh(self, cache_key: str, max_age_seconds: int) -> Optional[Dict[str, Any]]:
        """최신 캐시를 반환 (max_age_seconds 이내만 유효)."""
        try:
            if not cache_key:
                return None
            cutoff = datetime.now() - timedelta(seconds=max(1, int(max_age_seconds)))
            row = (
                self.db.query(PriceCache)
                .filter(PriceCache.cache_key == cache_key)
                .filter(PriceCache.updated_at >= cutoff)
                .first()
            )
            if not row:
                return None
            return json.loads(row.payload_json)
        except Exception as e:
            logger.error(f"DB cache read error: {type(e).__name__}: {e}")
            return None

    def upsert(self, cache_key: str, payload: Dict[str, Any]) -> None:
        """캐시를 삽입/갱신."""
        try:
            if not cache_key:
                return
            payload_json = json.dumps(payload, ensure_ascii=False)

            row = self.db.query(PriceCache).filter(PriceCache.cache_key == cache_key).first()
            if row:
                row.payload_json = payload_json
            else:
                row = PriceCache(cache_key=cache_key, payload_json=payload_json)
                self.db.add(row)

            self.db.commit()
        except Exception as e:
            self.db.rollback()
            logger.error(f"DB cache write error: {type(e).__name__}: {e}")
            raise DatabaseException(f"Failed to write price cache: {e}")
