#!/usr/bin/env python3
"""
주간 리포트 실행 스크립트
매주 일요일 오전에 실행하거나 수동으로 실행
"""

import sys
import os
import argparse
from datetime import datetime

# 프로젝트 루트 디렉토리를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.monitoring.weekly_performance_report import weekly_report
from src.utils.logging_config import setup_logging


def main():
    # 명령줄 인자 파싱
    parser = argparse.ArgumentParser(description='델파이 트레이딩 주간 리포트 생성')
    parser.add_argument('--days', type=int, default=7, help='분석 기간 (일 단위, 기본값: 7)')
    parser.add_argument('--save-only', action='store_true', help='Discord 알림 없이 저장만')
    args = parser.parse_args()
    
    # 로깅 설정
    setup_logging()
    
    print(f"📊 델파이 트레이딩 주간 리포트 생성 시작...")
    print(f"   - 분석 기간: 최근 {args.days}일")
    print(f"   - 현재 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("-" * 50)
    
    try:
        # 리포트 생성
        report = weekly_report.generate_weekly_report(days=args.days)
        
        if not report:
            print("❌ 리포트 생성 실패")
            return
        
        # 기본 통계 출력
        basic_stats = report.get('basic_stats', {})
        if basic_stats.get('no_trades'):
            print("\n📈 거래 통계: 이번 주 거래 없음")
        else:
            print(f"\n📈 거래 통계:")
            print(f"   - 총 거래: {basic_stats.get('total_trades', 0)}건")
            print(f"   - 승률: {basic_stats.get('win_rate', 0)}%")
            print(f"   - 평균 수익률: {basic_stats.get('avg_pnl_percent', 0)}%")
            print(f"   - 총 수익률: {basic_stats.get('total_pnl_percent', 0)}%")
        
        # 노이즈 분석 출력
        noise_analysis = report.get('noise_analysis', {})
        if noise_analysis:
            print(f"\n🔍 노이즈 분석:")
            print(f"   - 전체 손절: {noise_analysis.get('total_stops', 0)}건")
            print(f"   - 노이즈 손절: {noise_analysis.get('noise_stops', 0)}건")
            print(f"   - 노이즈 비율: {noise_analysis.get('noise_ratio', 0)}%")
            print(f"   - 권장사항: {noise_analysis.get('recommendation', 'N/A')}")
        
        # 개선 제안 출력
        recommendations = report.get('recommendations', [])
        if recommendations:
            print(f"\n💡 개선 제안 (상위 3개):")
            for i, rec in enumerate(recommendations[:3], 1):
                print(f"\n   {i}. [{rec['priority']}] {rec['category']}")
                print(f"      문제: {rec['issue']}")
                print(f"      제안: {rec['suggestion']}")
                print(f"      기대효과: {rec['expected_impact']}")
        
        print("\n✅ 리포트 생성 완료!")
        
        # 리포트 저장 위치 출력
        report_files = [f for f in os.listdir('reports') if f.startswith('weekly_report_')]
        if report_files:
            latest_report = sorted(report_files)[-1]
            print(f"📁 리포트 저장 위치: reports/{latest_report}")
        
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()