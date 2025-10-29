"""
델파이 트레이딩 시스템 - DB v2 마이그레이션 실행 스크립트
new_venv 환경에서 실행해야 함
"""

import sys
import os

# 프로젝트 루트 추가
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'src'))

from data.db_migrator import DBMigrator
import logging
from datetime import datetime

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def main():
    """DB 마이그레이션 실행"""
    
    print("=" * 60)
    print("Delphi Trading System - DB v2 Migration")
    print("=" * 60)
    
    # DB 경로
    db_path = os.path.join(project_root, "data", "database", "delphi_trades.db")
    
    if not os.path.exists(db_path):
        print(f"[ERROR] DB file not found: {db_path}")
        return
    
    # 마이그레이터 생성
    migrator = DBMigrator(db_path)
    
    # 현재 상태 확인
    print("\n[현재 DB 상태]")
    info = migrator.get_migration_info()
    print(f"  - 현재 버전: v{info['current_version']}")
    print(f"  - 테이블 수: {len(info['tables'])}")
    print(f"  - 테이블 목록: {', '.join(info['tables'])}")
    
    if info['current_version'] >= 2:
        print("\n[OK] 이미 v2로 마이그레이션되어 있습니다.")
        return
    
    # 사용자 확인
    print("\n[주의사항]")
    print("  1. DB가 자동으로 백업됩니다")
    print("  2. 새로운 테이블 4개가 추가됩니다")
    print("  3. trade_records 테이블에 컬럼이 추가됩니다")
    print(f"  4. 백업 위치: {migrator.backup_path}")
    
    response = input("\n마이그레이션을 진행하시겠습니까? (yes/no): ")
    
    if response.lower() != 'yes':
        print("마이그레이션이 취소되었습니다.")
        return
    
    # 마이그레이션 실행
    print("\n[마이그레이션 시작...]")
    
    try:
        success = migrator.migrate_to_v2()
        
        if success:
            print("\n[SUCCESS] 마이그레이션 성공!")
            
            # 새로운 상태 확인
            new_info = migrator.get_migration_info()
            print(f"\n[마이그레이션 후 상태]")
            print(f"  - 새 버전: v{new_info['current_version']}")
            print(f"  - 테이블 수: {len(new_info['tables'])}")
            
            # 새로 추가된 테이블
            new_tables = set(new_info['tables']) - set(info['tables'])
            if new_tables:
                print(f"  - 새 테이블: {', '.join(new_tables)}")
            
            print(f"\n[백업 파일] {migrator.backup_path}")
            print("   (문제 발생 시 이 파일로 복원 가능)")
            
        else:
            print("\n[ERROR] 마이그레이션 실패")
            
    except Exception as e:
        print(f"\n[ERROR] 마이그레이션 중 오류 발생: {e}")
        print(f"\n복원 명령어:")
        print(f"  cp {migrator.backup_path} {db_path}")


if __name__ == "__main__":
    main()