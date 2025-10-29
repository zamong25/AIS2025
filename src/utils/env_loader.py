"""
간단한 환경 변수 로더
dotenv 패키지가 없을 때 .env 파일을 직접 파싱
"""

import os
import logging

def load_env_file(env_path: str = ".env"):
    """
    .env 파일을 파싱하여 환경 변수로 설정
    
    Args:
        env_path: .env 파일 경로
    """
    if not os.path.exists(env_path):
        logging.warning(f"WARNING: Environment file not found: {env_path}")
        return
    
    try:
        with open(env_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            
            # 빈 줄이나 주석 건너뛰기
            if not line or line.startswith('#'):
                continue
            
            # KEY=VALUE 형식 파싱
            if '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip()
                
                # 따옴표 제거
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                elif value.startswith("'") and value.endswith("'"):
                    value = value[1:-1]
                
                # 환경 변수로 설정 (기존 값이 없는 경우만)
                if key not in os.environ:
                    os.environ[key] = value
            else:
                logging.warning(f"WARNING: Invalid environment variable format ({env_path}:{line_num}): {line}")
        
        logging.info(f"SUCCESS: Environment variables loaded: {env_path}")
        
    except Exception as e:
        logging.error(f"ERROR: Failed to load environment variables: {e}")

def get_env_var(key: str, default: str = None) -> str:
    """
    환경 변수 조회
    
    Args:
        key: 환경 변수 키
        default: 기본값
        
    Returns:
        환경 변수 값 또는 기본값
    """
    return os.environ.get(key, default)

def check_required_env_vars(required_vars: list) -> bool:
    """
    필수 환경 변수들이 설정되어 있는지 확인
    
    Args:
        required_vars: 필수 환경 변수 목록
        
    Returns:
        모든 필수 변수가 설정되어 있으면 True
    """
    missing_vars = []
    
    for var in required_vars:
        if not os.environ.get(var):
            missing_vars.append(var)
    
    if missing_vars:
        logging.error(f"ERROR: Missing required environment variables: {', '.join(missing_vars)}")
        return False
    
    return True

# 모듈 임포트 시 자동으로 .env 파일 로드 (config/.env 경로 사용)
if __name__ != "__main__":
    try:
        # 프로젝트 루트의 config/.env 파일 찾기
        current_file = os.path.abspath(__file__)
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_file)))
        env_path = os.path.join(project_root, "config", ".env")

        # 파일이 실제로 존재하는지 확인 후 로드
        if os.path.exists(env_path):
            load_env_file(env_path)
        else:
            # 파일이 없으면 debug 레벨로만 로깅 (warning 대신)
            logging.debug(f"Environment file not found at calculated path: {env_path}")
    except Exception as e:
        logging.debug(f"Failed to auto-load environment variables: {e}")