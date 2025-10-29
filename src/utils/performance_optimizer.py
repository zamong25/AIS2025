"""
델파이 트레이딩 시스템 - 성능 최적화 및 안정성 강화 모듈
시스템 안정성, 성능 최적화, 오류 복구 기능
"""

import logging
import time
import json
import os
import threading
from typing import Dict, Optional, Callable, Any
from datetime import datetime, timezone
from functools import wraps
import traceback


class PerformanceOptimizer:
    """성능 최적화 및 안정성 강화 관리자"""
    
    def __init__(self):
        self.cache = {}
        self.performance_stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'cache_hits': 0,
            'cache_attempts': 0,
            'average_response_time': 0,
            'last_reset': datetime.now(timezone.utc).isoformat()
        }
        self.circuit_breakers = {}
        self.rate_limits = {}
        self.retry_configs = {
            'max_retries': 3,
            'base_delay': 1.0,
            'max_delay': 60.0,
            'exponential_base': 2.0
        }
        
    def cached_call(self, cache_key: str, ttl_seconds: int = 300):
        """캐싱 데코레이터"""
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                now = time.time()
                
                # 캐시 확인
                self.performance_stats['cache_attempts'] += 1
                if cache_key in self.cache:
                    cached_item = self.cache[cache_key]
                    if now - cached_item['timestamp'] < ttl_seconds:
                        self.performance_stats['cache_hits'] += 1
                        self.performance_stats['total_requests'] += 1
                        logging.debug(f"💨 캐시 히트: {cache_key}")
                        return cached_item['data']
                
                # 캐시 미스 - 실제 함수 실행
                try:
                    start_time = time.time()
                    result = func(*args, **kwargs)
                    execution_time = time.time() - start_time
                    
                    # 캐시에 저장
                    self.cache[cache_key] = {
                        'data': result,
                        'timestamp': now
                    }
                    
                    # 성능 통계 업데이트
                    self._update_performance_stats(execution_time, success=True)
                    
                    logging.debug(f"📦 캐시 저장: {cache_key} (실행시간: {execution_time:.2f}초)")
                    return result
                    
                except Exception as e:
                    self._update_performance_stats(0, success=False)
                    raise e
                    
            return wrapper
        return decorator
    
    def retry_with_backoff(self, max_retries: int = None, base_delay: float = None):
        """지수 백오프 재시도 데코레이터"""
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                retries = max_retries or self.retry_configs['max_retries']
                delay = base_delay or self.retry_configs['base_delay']
                
                for attempt in range(retries + 1):
                    try:
                        return func(*args, **kwargs)
                    except Exception as e:
                        if attempt == retries:
                            logging.error(f"❌ 최대 재시도 횟수 초과: {func.__name__}")
                            raise e
                        
                        wait_time = min(
                            delay * (self.retry_configs['exponential_base'] ** attempt),
                            self.retry_configs['max_delay']
                        )
                        
                        logging.warning(f"⚠️ {func.__name__} 실패 (시도 {attempt + 1}/{retries + 1}), {wait_time:.1f}초 후 재시도: {str(e)}")
                        time.sleep(wait_time)
                        
            return wrapper
        return decorator
    
    def circuit_breaker(self, failure_threshold: int = 5, timeout_seconds: int = 60):
        """회로 차단기 패턴 데코레이터"""
        def decorator(func):
            func_name = func.__name__
            
            @wraps(func)
            def wrapper(*args, **kwargs):
                if func_name not in self.circuit_breakers:
                    self.circuit_breakers[func_name] = {
                        'failures': 0,
                        'last_failure': None,
                        'state': 'CLOSED'  # CLOSED, OPEN, HALF_OPEN
                    }
                
                breaker = self.circuit_breakers[func_name]
                now = time.time()
                
                # OPEN 상태 체크
                if breaker['state'] == 'OPEN':
                    if breaker['last_failure'] and (now - breaker['last_failure']) > timeout_seconds:
                        breaker['state'] = 'HALF_OPEN'
                        logging.info(f"🔄 회로 차단기 HALF_OPEN: {func_name}")
                    else:
                        raise Exception(f"회로 차단기 OPEN: {func_name}")
                
                try:
                    result = func(*args, **kwargs)
                    
                    # 성공 시 상태 리셋
                    if breaker['state'] == 'HALF_OPEN':
                        breaker['state'] = 'CLOSED'
                        breaker['failures'] = 0
                        logging.info(f"✅ 회로 차단기 CLOSED: {func_name}")
                    
                    return result
                    
                except Exception as e:
                    breaker['failures'] += 1
                    breaker['last_failure'] = now
                    
                    if breaker['failures'] >= failure_threshold:
                        breaker['state'] = 'OPEN'
                        logging.error(f"🚫 회로 차단기 OPEN: {func_name} (실패 {breaker['failures']}회)")
                    
                    raise e
                    
            return wrapper
        return decorator
    
    def rate_limit(self, calls_per_second: float = 1.0):
        """속도 제한 데코레이터"""
        def decorator(func):
            func_name = func.__name__
            
            @wraps(func)
            def wrapper(*args, **kwargs):
                if func_name not in self.rate_limits:
                    self.rate_limits[func_name] = {
                        'last_call': 0,
                        'min_interval': 1.0 / calls_per_second
                    }
                
                rate_limit = self.rate_limits[func_name]
                now = time.time()
                time_since_last = now - rate_limit['last_call']
                
                if time_since_last < rate_limit['min_interval']:
                    sleep_time = rate_limit['min_interval'] - time_since_last
                    logging.debug(f"⏱️ 속도 제한: {func_name} ({sleep_time:.2f}초 대기)")
                    time.sleep(sleep_time)
                
                rate_limit['last_call'] = time.time()
                return func(*args, **kwargs)
                
            return wrapper
        return decorator
    
    def safe_execute(self, func: Callable, *args, default_return=None, **kwargs) -> Any:
        """안전한 함수 실행 (예외 처리 포함)"""
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logging.error(f"❌ 안전 실행 실패 ({func.__name__}): {str(e)}")
            logging.debug(f"스택 트레이스: {traceback.format_exc()}")
            return default_return
    
    def _update_performance_stats(self, execution_time: float, success: bool):
        """성능 통계 업데이트"""
        self.performance_stats['total_requests'] += 1
        
        if success:
            self.performance_stats['successful_requests'] += 1
            
            # 평균 응답 시간 업데이트 (이동 평균)
            current_avg = self.performance_stats['average_response_time']
            total_success = self.performance_stats['successful_requests']
            
            if total_success == 1:
                self.performance_stats['average_response_time'] = execution_time
            else:
                # 이동 평균 계산
                self.performance_stats['average_response_time'] = (
                    (current_avg * (total_success - 1) + execution_time) / total_success
                )
        else:
            self.performance_stats['failed_requests'] += 1
    
    def clear_cache(self, pattern: str = None):
        """캐시 클리어"""
        if pattern:
            keys_to_remove = [key for key in self.cache.keys() if pattern in key]
            for key in keys_to_remove:
                del self.cache[key]
            logging.info(f"🧹 캐시 클리어 완료: {len(keys_to_remove)}개 항목 (패턴: {pattern})")
        else:
            self.cache.clear()
            logging.info("🧹 전체 캐시 클리어 완료")
    
    def get_performance_report(self) -> Dict:
        """성능 보고서 생성"""
        total = self.performance_stats['total_requests']
        success_rate = (self.performance_stats['successful_requests'] / total * 100) if total > 0 else 0
        
        return {
            'total_requests': total,
            'success_rate': f"{success_rate:.1f}%",
            'cache_hit_rate': f"{(self.performance_stats['cache_hits'] / self.performance_stats['cache_attempts'] * 100):.1f}%" if self.performance_stats['cache_attempts'] > 0 else "0%",
            'average_response_time': f"{self.performance_stats['average_response_time']:.3f}초",
            'active_cache_items': len(self.cache),
            'circuit_breakers': {name: breaker['state'] for name, breaker in self.circuit_breakers.items()},
            'last_reset': self.performance_stats['last_reset']
        }
    
    def reset_stats(self):
        """통계 리셋"""
        self.performance_stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'cache_hits': 0,
            'cache_attempts': 0,
            'average_response_time': 0,
            'last_reset': datetime.now(timezone.utc).isoformat()
        }
        logging.info("📊 성능 통계 리셋 완료")


class HealthChecker:
    """시스템 상태 체크"""
    
    def __init__(self):
        self.health_checks = {}
        self.last_check = None
        
    def register_health_check(self, name: str, check_func: Callable, critical: bool = False):
        """상태 체크 함수 등록"""
        self.health_checks[name] = {
            'func': check_func,
            'critical': critical,
            'last_result': None,
            'last_check': None
        }
        
    def run_health_checks(self) -> Dict:
        """모든 상태 체크 실행"""
        results = {
            'overall_status': 'HEALTHY',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'checks': {}
        }
        
        for name, check in self.health_checks.items():
            try:
                start_time = time.time()
                result = check['func']()
                execution_time = time.time() - start_time
                
                check['last_result'] = result
                check['last_check'] = datetime.now(timezone.utc).isoformat()
                
                results['checks'][name] = {
                    'status': 'PASS' if result else 'FAIL',
                    'execution_time': f"{execution_time:.3f}초",
                    'critical': check['critical'],
                    'result': result
                }
                
                # 중요한 체크가 실패하면 전체 상태를 UNHEALTHY로 설정
                if check['critical'] and not result:
                    results['overall_status'] = 'UNHEALTHY'
                    
            except Exception as e:
                results['checks'][name] = {
                    'status': 'ERROR',
                    'error': str(e),
                    'critical': check['critical']
                }
                
                if check['critical']:
                    results['overall_status'] = 'UNHEALTHY'
        
        self.last_check = results
        return results


# 전역 인스턴스
performance_optimizer = PerformanceOptimizer()
health_checker = HealthChecker()


# 상태 체크 함수들
def check_api_keys():
    """API 키 존재 확인"""
    # 환경 변수 로드 시도
    try:
        from utils.env_loader import load_env_file, check_required_env_vars
        # 프로젝트 루트 기준으로 .env 파일 경로 설정
        import os
        current_file = os.path.abspath(__file__)
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_file)))
        env_path = os.path.join(project_root, "config", ".env")
        load_env_file(env_path)
        required_keys = ['BINANCE_API_KEY', 'BINANCE_API_SECRET', 'GOOGLE_API_KEY']
        return check_required_env_vars(required_keys)
    except ImportError:
        # env_loader가 없는 경우 기본 방식으로 체크
        required_keys = ['BINANCE_API_KEY', 'BINANCE_API_SECRET', 'GOOGLE_API_KEY']
        return all(os.getenv(key) for key in required_keys)

def check_chart_images():
    """차트 이미지 파일 존재 확인"""
    # 프로젝트 루트 기준으로 이미지 경로 설정
    current_file = os.path.abspath(__file__)
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_file)))
    image_paths = [
        os.path.join(project_root, 'data', 'screenshots', 'chart_5m.png'),
        os.path.join(project_root, 'data', 'screenshots', 'chart_15m.png'), 
        os.path.join(project_root, 'data', 'screenshots', 'chart_1H.png'),
        os.path.join(project_root, 'data', 'screenshots', 'chart_1D.png')
    ]
    return all(os.path.exists(path) for path in image_paths)

def check_database_connection():
    """데이터베이스 연결 확인"""
    try:
        import sys
        import os
        sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from data.trade_database import trade_db
        # 간단한 쿼리로 DB 상태 확인
        stats = trade_db.get_performance_statistics()
        return True
    except:
        return False

# 기본 상태 체크 등록
health_checker.register_health_check('api_keys', check_api_keys, critical=True)
health_checker.register_health_check('chart_images', check_chart_images, critical=True)
health_checker.register_health_check('database', check_database_connection, critical=True)