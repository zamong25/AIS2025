"""
델파이 트레이딩 시스템 - DB 마이그레이션 도구
v1에서 v2 스키마로 안전하게 업그레이드
"""

import sqlite3
import logging
from datetime import datetime
import shutil
import os
from typing import List, Tuple


class DBMigrator:
    """DB 스키마 마이그레이션 관리"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.backup_path = f"{db_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.logger = logging.getLogger('DBMigrator')
        
    def migrate_to_v2(self) -> bool:
        """DB를 v2 스키마로 안전하게 마이그레이션"""
        try:
            # 1. 백업
            self.logger.info(f"DB 백업 중: {self.backup_path}")
            shutil.copy2(self.db_path, self.backup_path)
            
            # 2. 연결
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 3. 현재 스키마 확인
            self.logger.info("현재 DB 스키마 확인 중...")
            current_version = self._check_schema_version(cursor)
            
            if current_version >= 2:
                self.logger.info(f"이미 v{current_version} 스키마입니다. 마이그레이션 불필요.")
                conn.close()
                return True
            
            # 4. 스키마 적용
            self.logger.info("스키마 v2 적용 중...")
            schema_path = os.path.join(os.path.dirname(__file__), 'schema_v2.sql')
            
            if not os.path.exists(schema_path):
                raise FileNotFoundError(f"스키마 파일 없음: {schema_path}")
                
            with open(schema_path, 'r', encoding='utf-8') as f:
                schema_sql = f.read()
            
            # SQL 문장을 하나씩 실행 (SQLite의 ALTER TABLE IF NOT EXISTS 미지원 처리)
            for statement in schema_sql.split(';'):
                statement = statement.strip()
                if not statement:
                    continue
                    
                try:
                    if 'ALTER TABLE' in statement and 'ADD COLUMN' in statement:
                        # ALTER TABLE에서 컬럼 존재 여부 먼저 확인
                        self._execute_alter_table_safe(cursor, statement)
                    else:
                        cursor.execute(statement)
                except sqlite3.OperationalError as e:
                    if 'already exists' in str(e):
                        self.logger.debug(f"이미 존재함: {statement[:50]}...")
                    else:
                        raise
            
            # 5. 검증
            self._verify_migration(cursor)
            
            # 6. 버전 기록
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS schema_version (
                    version INTEGER PRIMARY KEY,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("INSERT OR REPLACE INTO schema_version (version) VALUES (2)")
            
            conn.commit()
            conn.close()
            
            self.logger.info("✅ DB 마이그레이션 완료")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ 마이그레이션 실패: {e}")
            self.logger.info(f"백업에서 복원하려면: cp {self.backup_path} {self.db_path}")
            raise
    
    def _check_schema_version(self, cursor: sqlite3.Cursor) -> int:
        """현재 스키마 버전 확인"""
        try:
            cursor.execute("SELECT version FROM schema_version ORDER BY version DESC LIMIT 1")
            result = cursor.fetchone()
            return result[0] if result else 1
        except sqlite3.OperationalError:
            # schema_version 테이블이 없으면 v1
            return 1
    
    def _execute_alter_table_safe(self, cursor: sqlite3.Cursor, statement: str):
        """ALTER TABLE ADD COLUMN을 안전하게 실행"""
        # 테이블명과 컬럼명 추출
        import re
        match = re.search(r'ALTER TABLE (\w+) ADD COLUMN (?:IF NOT EXISTS )?(\w+)', statement)
        if match:
            table_name = match.group(1)
            column_name = match.group(2)
            
            # 컬럼 존재 여부 확인
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = [col[1] for col in cursor.fetchall()]
            
            if column_name not in columns:
                # IF NOT EXISTS 제거하고 실행
                safe_statement = statement.replace('IF NOT EXISTS', '')
                cursor.execute(safe_statement)
                self.logger.debug(f"컬럼 추가됨: {table_name}.{column_name}")
            else:
                self.logger.debug(f"컬럼 이미 존재: {table_name}.{column_name}")
    
    def _verify_migration(self, cursor: sqlite3.Cursor):
        """마이그레이션 검증"""
        # 새 테이블 존재 확인
        expected_tables = ['scenario_tracking', 'position_snapshots', 'market_context']
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        existing_tables = [row[0] for row in cursor.fetchall()]
        
        for table in expected_tables:
            if table not in existing_tables:
                raise Exception(f"테이블 {table} 생성 실패")
            else:
                self.logger.debug(f"✓ 테이블 확인: {table}")
        
        # trade_records 컬럼 확인
        cursor.execute("PRAGMA table_info(trade_records)")
        columns = [col[1] for col in cursor.fetchall()]
        required_columns = ['selected_scenario', 'scenario_confidence', 'max_adverse_excursion']
        
        for col in required_columns:
            if col not in columns:
                raise Exception(f"컬럼 {col} 추가 실패")
            else:
                self.logger.debug(f"✓ 컬럼 확인: trade_records.{col}")
        
        self.logger.info("✅ 마이그레이션 검증 완료")
    
    def rollback(self):
        """백업에서 복원"""
        if os.path.exists(self.backup_path):
            self.logger.info(f"백업에서 복원 중: {self.backup_path} -> {self.db_path}")
            shutil.copy2(self.backup_path, self.db_path)
            self.logger.info("✅ 복원 완료")
        else:
            self.logger.error(f"백업 파일 없음: {self.backup_path}")
    
    def get_migration_info(self) -> dict:
        """마이그레이션 정보 조회"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        info = {
            'current_version': self._check_schema_version(cursor),
            'tables': [],
            'backup_exists': os.path.exists(self.backup_path)
        }
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        info['tables'] = [row[0] for row in cursor.fetchall()]
        
        conn.close()
        return info


if __name__ == "__main__":
    # 테스트 실행
    logging.basicConfig(level=logging.INFO)
    
    import sys
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    else:
        db_path = "data/database/delphi_trades.db"
    
    migrator = DBMigrator(db_path)
    
    print(f"DB 경로: {db_path}")
    print(f"백업 경로: {migrator.backup_path}")
    print(f"현재 정보: {migrator.get_migration_info()}")
    
    response = input("\n마이그레이션을 진행하시겠습니까? (y/n): ")
    if response.lower() == 'y':
        try:
            migrator.migrate_to_v2()
            print(f"\n마이그레이션 후 정보: {migrator.get_migration_info()}")
        except Exception as e:
            print(f"\n마이그레이션 실패: {e}")
            rollback = input("백업에서 복원하시겠습니까? (y/n): ")
            if rollback.lower() == 'y':
                migrator.rollback()