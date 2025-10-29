#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Health check script for production monitoring"""

import argparse
import json
import sys
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import requests


class HealthChecker:
    """시스템 상태 확인"""
    
    def __init__(self, base_url: str, timeout: int = 10):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.checks: List[Dict] = []
    
    def check_all(self) -> Dict:
        """모든 헬스체크 실행"""
        start_time = time.time()
        
        checks = {
            'api': self.check_api_health(),
            'database': self.check_database(),
            'exchange': self.check_exchange(),
            'scheduler': self.check_scheduler(),
            'websocket': self.check_websocket(),
            'memory': self.check_memory_usage(),
            'disk': self.check_disk_usage(),
            'latency': self.check_latency(),
        }
        
        # 전체 상태 계산
        all_healthy = all(check.get('healthy', False) for check in checks.values())
        degraded = any(
            check.get('status') == 'degraded' 
            for check in checks.values()
        )
        
        result = {
            'timestamp': datetime.utcnow().isoformat(),
            'overall_status': 'healthy' if all_healthy else ('degraded' if degraded else 'unhealthy'),
            'checks': checks,
            'check_duration_ms': int((time.time() - start_time) * 1000)
        }
        
        return result
    
    def check_api_health(self) -> Dict:
        """API 헬스 체크"""
        try:
            start = time.time()
            response = requests.get(
                f"{self.base_url}/health",
                timeout=self.timeout
            )
            latency = (time.time() - start) * 1000
            
            if response.status_code == 200:
                data = response.json()
                return {
                    'healthy': data.get('status') == 'healthy',
                    'status': data.get('status', 'unknown'),
                    'latency_ms': int(latency),
                    'details': data
                }
            else:
                return {
                    'healthy': False,
                    'status': 'unhealthy',
                    'error': f'HTTP {response.status_code}',
                    'latency_ms': int(latency)
                }
        except Exception as e:
            return {
                'healthy': False,
                'status': 'unhealthy',
                'error': str(e)
            }
    
    def check_database(self) -> Dict:
        """데이터베이스 상태 체크"""
        try:
            response = requests.get(
                f"{self.base_url}/api/health/database",
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    'healthy': data.get('connected', False),
                    'status': 'healthy' if data.get('connected') else 'unhealthy',
                    'connection_count': data.get('connections', 0),
                    'response_time_ms': data.get('response_time', 0)
                }
            else:
                return {
                    'healthy': False,
                    'status': 'unhealthy',
                    'error': f'HTTP {response.status_code}'
                }
        except Exception as e:
            return {
                'healthy': False,
                'status': 'unhealthy',
                'error': str(e)
            }
    
    def check_exchange(self) -> Dict:
        """거래소 연결 상태 체크"""
        try:
            response = requests.get(
                f"{self.base_url}/api/health/exchange",
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    'healthy': data.get('connected', False),
                    'status': 'healthy' if data.get('connected') else 'unhealthy',
                    'exchange': data.get('exchange', 'unknown'),
                    'api_weight': data.get('api_weight', 0),
                    'rate_limit_remaining': data.get('rate_limit_remaining', 0)
                }
            else:
                return {
                    'healthy': False,
                    'status': 'unhealthy',
                    'error': f'HTTP {response.status_code}'
                }
        except Exception as e:
            return {
                'healthy': False,
                'status': 'unhealthy',
                'error': str(e)
            }
    
    def check_scheduler(self) -> Dict:
        """스케줄러 상태 체크"""
        try:
            response = requests.get(
                f"{self.base_url}/api/health/scheduler",
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                running = data.get('running', False)
                job_count = data.get('job_count', 0)
                
                # 잡이 너무 적거나 많으면 degraded
                if running and (job_count < 5 or job_count > 50):
                    status = 'degraded'
                elif running:
                    status = 'healthy'
                else:
                    status = 'unhealthy'
                
                return {
                    'healthy': running,
                    'status': status,
                    'running': running,
                    'job_count': job_count,
                    'next_run': data.get('next_run')
                }
            else:
                return {
                    'healthy': False,
                    'status': 'unhealthy',
                    'error': f'HTTP {response.status_code}'
                }
        except Exception as e:
            return {
                'healthy': False,
                'status': 'unhealthy',
                'error': str(e)
            }
    
    def check_websocket(self) -> Dict:
        """웹소켓 연결 상태 체크"""
        try:
            response = requests.get(
                f"{self.base_url}/api/health/websocket",
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                connected = data.get('connected', False)
                reconnect_count = data.get('reconnect_count', 0)
                
                # 재연결이 많으면 degraded
                if connected and reconnect_count > 10:
                    status = 'degraded'
                elif connected:
                    status = 'healthy'
                else:
                    status = 'unhealthy'
                
                return {
                    'healthy': connected,
                    'status': status,
                    'connected': connected,
                    'reconnect_count': reconnect_count,
                    'last_message': data.get('last_message_time')
                }
            else:
                return {
                    'healthy': False,
                    'status': 'unhealthy',
                    'error': f'HTTP {response.status_code}'
                }
        except Exception as e:
            return {
                'healthy': False,
                'status': 'unhealthy',
                'error': str(e)
            }
    
    def check_memory_usage(self) -> Dict:
        """메모리 사용량 체크"""
        try:
            response = requests.get(
                f"{self.base_url}/api/health/memory",
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                usage_percent = data.get('usage_percent', 0)
                
                # 메모리 사용량에 따른 상태
                if usage_percent < 80:
                    status = 'healthy'
                elif usage_percent < 90:
                    status = 'degraded'
                else:
                    status = 'unhealthy'
                
                return {
                    'healthy': usage_percent < 90,
                    'status': status,
                    'usage_percent': usage_percent,
                    'used_mb': data.get('used_mb', 0),
                    'total_mb': data.get('total_mb', 0)
                }
            else:
                return {
                    'healthy': False,
                    'status': 'unhealthy',
                    'error': f'HTTP {response.status_code}'
                }
        except Exception as e:
            return {
                'healthy': False,
                'status': 'unhealthy',
                'error': str(e)
            }
    
    def check_disk_usage(self) -> Dict:
        """디스크 사용량 체크"""
        try:
            response = requests.get(
                f"{self.base_url}/api/health/disk",
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                usage_percent = data.get('usage_percent', 0)
                
                # 디스크 사용량에 따른 상태
                if usage_percent < 80:
                    status = 'healthy'
                elif usage_percent < 90:
                    status = 'degraded'
                else:
                    status = 'unhealthy'
                
                return {
                    'healthy': usage_percent < 90,
                    'status': status,
                    'usage_percent': usage_percent,
                    'free_gb': data.get('free_gb', 0)
                }
            else:
                return {
                    'healthy': False,
                    'status': 'unhealthy',
                    'error': f'HTTP {response.status_code}'
                }
        except Exception as e:
            return {
                'healthy': False,
                'status': 'unhealthy',
                'error': str(e)
            }
    
    def check_latency(self) -> Dict:
        """API 응답 지연 체크"""
        try:
            latencies = []
            
            # 5번 ping 테스트
            for _ in range(5):
                start = time.time()
                response = requests.get(
                    f"{self.base_url}/ping",
                    timeout=self.timeout
                )
                if response.status_code == 200:
                    latencies.append((time.time() - start) * 1000)
                time.sleep(0.1)
            
            if latencies:
                avg_latency = sum(latencies) / len(latencies)
                max_latency = max(latencies)
                
                # 지연 시간에 따른 상태
                if avg_latency < 100:
                    status = 'healthy'
                elif avg_latency < 500:
                    status = 'degraded'
                else:
                    status = 'unhealthy'
                
                return {
                    'healthy': avg_latency < 500,
                    'status': status,
                    'avg_latency_ms': int(avg_latency),
                    'max_latency_ms': int(max_latency),
                    'samples': len(latencies)
                }
            else:
                return {
                    'healthy': False,
                    'status': 'unhealthy',
                    'error': 'No successful pings'
                }
        except Exception as e:
            return {
                'healthy': False,
                'status': 'unhealthy',
                'error': str(e)
            }


def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(description='Health check for Delphi Trader')
    parser.add_argument(
        '--env',
        choices=['local', 'staging', 'production'],
        default='production',
        help='Environment to check'
    )
    parser.add_argument(
        '--url',
        help='Override base URL'
    )
    parser.add_argument(
        '--timeout',
        type=int,
        default=10,
        help='Request timeout in seconds'
    )
    parser.add_argument(
        '--format',
        choices=['json', 'text'],
        default='text',
        help='Output format'
    )
    
    args = parser.parse_args()
    
    # 환경별 URL
    urls = {
        'local': 'http://localhost:8000',
        'staging': 'https://staging.delphi-trader.com',
        'production': 'https://api.delphi-trader.com'
    }
    
    base_url = args.url or urls.get(args.env)
    
    # 헬스체크 실행
    checker = HealthChecker(base_url, args.timeout)
    result = checker.check_all()
    
    # 결과 출력
    if args.format == 'json':
        print(json.dumps(result, indent=2))
    else:
        print(f"Health Check Report - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)
        print(f"Overall Status: {result['overall_status'].upper()}")
        print(f"Check Duration: {result['check_duration_ms']}ms")
        print("\nDetailed Checks:")
        print("-" * 60)
        
        for name, check in result['checks'].items():
            status = check.get('status', 'unknown').upper()
            emoji = "✅" if check.get('healthy') else "❌"
            print(f"{emoji} {name.ljust(15)} - {status}")
            
            # 추가 정보 출력
            if check.get('error'):
                print(f"   Error: {check['error']}")
            if check.get('latency_ms'):
                print(f"   Latency: {check['latency_ms']}ms")
            if check.get('usage_percent') is not None:
                print(f"   Usage: {check['usage_percent']}%")
    
    # 종료 코드
    sys.exit(0 if result['overall_status'] == 'healthy' else 1)


if __name__ == '__main__':
    main()