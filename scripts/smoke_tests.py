#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Smoke tests for deployment verification"""

import argparse
import sys
import time
from typing import List, Tuple

import requests


class SmokeTestRunner:
    """배포 후 기본 동작 확인 테스트"""
    
    def __init__(self, base_url: str, timeout: int = 30):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.results: List[Tuple[str, bool, str]] = []
    
    def run_all_tests(self) -> bool:
        """모든 smoke test 실행"""
        print(f"Running smoke tests for: {self.base_url}")
        print("-" * 50)
        
        # 테스트 목록
        tests = [
            self.test_health_check,
            self.test_api_version,
            self.test_database_connection,
            self.test_exchange_connection,
            self.test_config_loaded,
            self.test_scheduler_running,
            self.test_logging_system,
            self.test_monitoring_endpoints,
        ]
        
        # 테스트 실행
        for test in tests:
            test_name = test.__name__.replace('test_', '').replace('_', ' ').title()
            try:
                result, message = test()
                self.results.append((test_name, result, message))
                status = "✅ PASS" if result else "❌ FAIL"
                print(f"{status} - {test_name}: {message}")
            except Exception as e:
                self.results.append((test_name, False, f"Exception: {str(e)}"))
                print(f"❌ FAIL - {test_name}: Exception: {str(e)}")
        
        # 결과 요약
        print("\n" + "=" * 50)
        passed = sum(1 for _, result, _ in self.results if result)
        total = len(self.results)
        print(f"Results: {passed}/{total} tests passed")
        
        return passed == total
    
    def test_health_check(self) -> Tuple[bool, str]:
        """헬스체크 엔드포인트 테스트"""
        try:
            response = requests.get(
                f"{self.base_url}/health",
                timeout=self.timeout
            )
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'healthy':
                    return True, "System is healthy"
                else:
                    return False, f"Unhealthy status: {data.get('status')}"
            else:
                return False, f"HTTP {response.status_code}"
        except requests.exceptions.ConnectionError:
            return False, "Cannot connect to server"
        except Exception as e:
            return False, str(e)
    
    def test_api_version(self) -> Tuple[bool, str]:
        """API 버전 확인"""
        try:
            response = requests.get(
                f"{self.base_url}/api/version",
                timeout=self.timeout
            )
            if response.status_code == 200:
                data = response.json()
                version = data.get('version')
                if version and version.startswith('2.'):
                    return True, f"Version {version}"
                else:
                    return False, f"Unexpected version: {version}"
            else:
                return False, f"HTTP {response.status_code}"
        except:
            return False, "Version endpoint not available"
    
    def test_database_connection(self) -> Tuple[bool, str]:
        """데이터베이스 연결 테스트"""
        try:
            response = requests.get(
                f"{self.base_url}/api/status/database",
                timeout=self.timeout
            )
            if response.status_code == 200:
                data = response.json()
                if data.get('connected'):
                    return True, "Database connected"
                else:
                    return False, "Database not connected"
            else:
                return False, f"HTTP {response.status_code}"
        except:
            return False, "Database status check failed"
    
    def test_exchange_connection(self) -> Tuple[bool, str]:
        """거래소 연결 테스트"""
        try:
            response = requests.get(
                f"{self.base_url}/api/status/exchange",
                timeout=self.timeout
            )
            if response.status_code == 200:
                data = response.json()
                if data.get('connected'):
                    return True, f"Connected to {data.get('exchange', 'exchange')}"
                else:
                    return False, "Exchange not connected"
            else:
                return False, f"HTTP {response.status_code}"
        except:
            return False, "Exchange status check failed"
    
    def test_config_loaded(self) -> Tuple[bool, str]:
        """설정 로드 확인"""
        try:
            response = requests.get(
                f"{self.base_url}/api/config/status",
                timeout=self.timeout
            )
            if response.status_code == 200:
                data = response.json()
                if data.get('loaded'):
                    env = data.get('environment', 'unknown')
                    return True, f"Config loaded for {env}"
                else:
                    return False, "Config not loaded"
            else:
                return False, f"HTTP {response.status_code}"
        except:
            return False, "Config status check failed"
    
    def test_scheduler_running(self) -> Tuple[bool, str]:
        """스케줄러 동작 확인"""
        try:
            response = requests.get(
                f"{self.base_url}/api/scheduler/status",
                timeout=self.timeout
            )
            if response.status_code == 200:
                data = response.json()
                if data.get('running'):
                    jobs = data.get('job_count', 0)
                    return True, f"Scheduler running with {jobs} jobs"
                else:
                    return False, "Scheduler not running"
            else:
                return False, f"HTTP {response.status_code}"
        except:
            return False, "Scheduler status check failed"
    
    def test_logging_system(self) -> Tuple[bool, str]:
        """로깅 시스템 테스트"""
        try:
            response = requests.post(
                f"{self.base_url}/api/test/log",
                json={"message": "Smoke test log entry"},
                timeout=self.timeout
            )
            if response.status_code in [200, 201]:
                return True, "Logging system working"
            else:
                return False, f"HTTP {response.status_code}"
        except:
            return False, "Logging test failed"
    
    def test_monitoring_endpoints(self) -> Tuple[bool, str]:
        """모니터링 엔드포인트 테스트"""
        try:
            response = requests.get(
                f"{self.base_url}/api/metrics",
                timeout=self.timeout
            )
            if response.status_code == 200:
                data = response.json()
                if 'system' in data and 'trading' in data:
                    return True, "Monitoring endpoints available"
                else:
                    return False, "Incomplete metrics"
            else:
                return False, f"HTTP {response.status_code}"
        except:
            return False, "Monitoring check failed"


def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(description='Run smoke tests')
    parser.add_argument(
        '--env',
        choices=['local', 'staging', 'production'],
        default='local',
        help='Environment to test'
    )
    parser.add_argument(
        '--url',
        help='Override base URL'
    )
    parser.add_argument(
        '--timeout',
        type=int,
        default=30,
        help='Request timeout in seconds'
    )
    
    args = parser.parse_args()
    
    # 환경별 URL 설정
    urls = {
        'local': 'http://localhost:8000',
        'staging': 'https://staging.delphi-trader.com',
        'production': 'https://api.delphi-trader.com'
    }
    
    base_url = args.url or urls.get(args.env, urls['local'])
    
    # 테스트 실행
    runner = SmokeTestRunner(base_url, args.timeout)
    success = runner.run_all_tests()
    
    # 종료 코드 설정
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()