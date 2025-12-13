"""Alembic 마이그레이션: SearchFailure 테이블 추가"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime


def upgrade():
    """검색 실패 기록 테이블 생성"""
    op.create_table(
        'search_failures',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('original_query', sa.String(255), nullable=False),
        sa.Column('normalized_query', sa.String(255), nullable=False),
        sa.Column('candidates', sa.Text(), nullable=False),
        sa.Column('attempted_count', sa.Integer(), nullable=False, default=1),
        sa.Column('error_message', sa.String(512), nullable=True),
        sa.Column('category_detected', sa.String(50), nullable=True),
        sa.Column('brand', sa.String(100), nullable=True),
        sa.Column('model', sa.String(100), nullable=True),
        sa.Column('is_resolved', sa.String(50), nullable=False, default='pending'),
        sa.Column('correct_product_name', sa.String(255), nullable=True),
        sa.Column('correct_pcode', sa.String(20), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, default=datetime.utcnow),
        sa.Column('updated_at', sa.DateTime(), nullable=False, default=datetime.utcnow),
        sa.PrimaryKeyConstraint('id')
    )
    
    # 인덱스 추가
    op.create_index('ix_search_failures_original_query', 'search_failures', ['original_query'])
    op.create_index('ix_search_failures_created_at', 'search_failures', ['created_at'])
    op.create_index('ix_search_failures_is_resolved', 'search_failures', ['is_resolved'])


def downgrade():
    """테이블 삭제"""
    op.drop_index('ix_search_failures_is_resolved', table_name='search_failures')
    op.drop_index('ix_search_failures_created_at', table_name='search_failures')
    op.drop_index('ix_search_failures_original_query', table_name='search_failures')
    op.drop_table('search_failures')
