"""
주간 성과 리포트 생성
노이즈 손절 분석 및 개선 제안 포함
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
import sqlite3
import json
from data.trade_database import trade_db
from utils.discord_notifier import discord_notifier


class WeeklyPerformanceReport:
    """주간 성과 분석 및 개선 제안"""
    
    def __init__(self):
        self.logger = logging.getLogger('WeeklyReport')
        
    def generate_weekly_report(self, days: int = 7) -> Dict:
        """
        주간 성과 리포트 생성
        
        Args:
            days: 분석 기간 (기본 7일)
            
        Returns:
            리포트 데이터
        """
        try:
            end_date = datetime.now(timezone.utc)
            start_date = end_date - timedelta(days=days)
            
            # 1. 기본 통계
            basic_stats = self._get_basic_statistics(start_date, end_date)
            
            # 2. 노이즈 손절 분석
            noise_analysis = self._analyze_noise_stops(start_date, end_date)
            
            # 3. 시장 상태별 성과
            market_performance = self._analyze_market_conditions(start_date, end_date)
            
            # 4. 에이전트 정확도
            agent_accuracy = self._analyze_agent_accuracy(start_date, end_date)
            
            # 5. 개선 제안
            recommendations = self._generate_recommendations(
                basic_stats, noise_analysis, market_performance
            )
            
            report = {
                'period': {
                    'start': start_date.isoformat(),
                    'end': end_date.isoformat(),
                    'days': days
                },
                'basic_stats': basic_stats,
                'noise_analysis': noise_analysis,
                'market_performance': market_performance,
                'agent_accuracy': agent_accuracy,
                'recommendations': recommendations,
                'generated_at': datetime.now(timezone.utc).isoformat()
            }
            
            # 리포트 저장
            self._save_report(report)
            
            # Discord 알림
            self._send_discord_summary(report)
            
            return report
            
        except Exception as e:
            self.logger.error(f"❌ 주간 리포트 생성 실패: {e}")
            return {}
    
    def _get_basic_statistics(self, start_date: datetime, end_date: datetime) -> Dict:
        """기본 거래 통계"""
        try:
            with sqlite3.connect(trade_db.db_path) as conn:
                cursor = conn.cursor()
                
                # 전체 거래 수
                cursor.execute("""
                    SELECT COUNT(*) as total_trades,
                           COUNT(CASE WHEN outcome = 'WIN' THEN 1 END) as wins,
                           COUNT(CASE WHEN outcome = 'LOSS' THEN 1 END) as losses,
                           AVG(pnl_percent) as avg_pnl,
                           SUM(pnl_percent) as total_pnl,
                           MAX(pnl_percent) as max_win,
                           MIN(pnl_percent) as max_loss,
                           AVG(time_to_stop_minutes) as avg_trade_duration
                    FROM trade_records
                    WHERE exit_time BETWEEN ? AND ?
                """, (start_date.isoformat(), end_date.isoformat()))
                
                result = cursor.fetchone()
                
                if result[0] == 0:  # 거래 없음
                    return {'no_trades': True}
                
                win_rate = (result[1] / result[0]) * 100 if result[0] > 0 else 0
                
                return {
                    'total_trades': result[0],
                    'wins': result[1],
                    'losses': result[2],
                    'win_rate': round(win_rate, 1),
                    'avg_pnl_percent': round(result[3] or 0, 2),
                    'total_pnl_percent': round(result[4] or 0, 2),
                    'best_trade': round(result[5] or 0, 2),
                    'worst_trade': round(result[6] or 0, 2),
                    'avg_duration_minutes': round(result[7] or 0, 0)
                }
                
        except Exception as e:
            self.logger.error(f"❌ 기본 통계 조회 실패: {e}")
            return {}
    
    def _analyze_noise_stops(self, start_date: datetime, end_date: datetime) -> Dict:
        """노이즈 손절 분석"""
        try:
            with sqlite3.connect(trade_db.db_path) as conn:
                cursor = conn.cursor()
                
                # 손절 유형별 통계
                cursor.execute("""
                    SELECT stop_loss_type,
                           COUNT(*) as count,
                           AVG(pnl_percent) as avg_pnl,
                           AVG(time_to_stop_minutes) as avg_duration
                    FROM trade_records
                    WHERE exit_time BETWEEN ? AND ?
                    GROUP BY stop_loss_type
                """, (start_date.isoformat(), end_date.isoformat()))
                
                results = cursor.fetchall()
                
                stop_analysis = {}
                total_stops = 0
                noise_stops = 0
                
                for stop_type, count, avg_pnl, avg_duration in results:
                    if stop_type:
                        stop_analysis[stop_type] = {
                            'count': count,
                            'avg_pnl': round(avg_pnl or 0, 2),
                            'avg_duration_minutes': round(avg_duration or 0, 0)
                        }
                        total_stops += count
                        if stop_type == 'NOISE':
                            noise_stops = count
                
                noise_ratio = (noise_stops / total_stops * 100) if total_stops > 0 else 0
                
                return {
                    'stop_type_breakdown': stop_analysis,
                    'total_stops': total_stops,
                    'noise_stops': noise_stops,
                    'noise_ratio': round(noise_ratio, 1),
                    'recommendation': self._get_noise_recommendation(noise_ratio)
                }
                
        except Exception as e:
            self.logger.error(f"❌ 노이즈 분석 실패: {e}")
            return {}
    
    def _analyze_market_conditions(self, start_date: datetime, end_date: datetime) -> Dict:
        """시장 상태별 성과 분석"""
        try:
            with sqlite3.connect(trade_db.db_path) as conn:
                cursor = conn.cursor()
                
                # 시장 상태별 성과
                cursor.execute("""
                    SELECT mc.trend_type,
                           mc.volatility_level,
                           COUNT(*) as trades,
                           AVG(tr.pnl_percent) as avg_pnl,
                           COUNT(CASE WHEN tr.outcome = 'WIN' THEN 1 END) * 100.0 / COUNT(*) as win_rate
                    FROM trade_records tr
                    JOIN market_classifications mc ON tr.trade_id = mc.trade_id
                    WHERE tr.exit_time BETWEEN ? AND ?
                    GROUP BY mc.trend_type, mc.volatility_level
                """, (start_date.isoformat(), end_date.isoformat()))
                
                results = cursor.fetchall()
                
                market_analysis = {}
                for trend, volatility, trades, avg_pnl, win_rate in results:
                    key = f"{trend}_{volatility}"
                    market_analysis[key] = {
                        'trend': trend,
                        'volatility': volatility,
                        'trades': trades,
                        'avg_pnl': round(avg_pnl or 0, 2),
                        'win_rate': round(win_rate or 0, 1)
                    }
                
                # 가장 수익성 높은/낮은 시장 조건 찾기
                if market_analysis:
                    best_market = max(market_analysis.items(), key=lambda x: x[1]['avg_pnl'])
                    worst_market = min(market_analysis.items(), key=lambda x: x[1]['avg_pnl'])
                    
                    return {
                        'market_breakdown': market_analysis,
                        'best_conditions': best_market,
                        'worst_conditions': worst_market
                    }
                
                return {'market_breakdown': {}}
                
        except Exception as e:
            self.logger.error(f"❌ 시장 조건 분석 실패: {e}")
            return {}
    
    def _analyze_agent_accuracy(self, start_date: datetime, end_date: datetime) -> Dict:
        """에이전트별 정확도 분석"""
        try:
            # 여기서는 간단히 평균값만 계산
            # 실제로는 trade_analyses 테이블에서 가져올 수 있음
            return {
                'chartist': {'accuracy': 'N/A', 'trend': 'stable'},
                'journalist': {'accuracy': 'N/A', 'trend': 'stable'},
                'quant': {'accuracy': 'N/A', 'trend': 'stable'},
                'stoic': {'accuracy': 'N/A', 'trend': 'stable'}
            }
        except Exception as e:
            self.logger.error(f"❌ 에이전트 정확도 분석 실패: {e}")
            return {}
    
    def _generate_recommendations(self, basic_stats: Dict, noise_analysis: Dict, 
                                market_performance: Dict) -> List[Dict]:
        """개선 제안 생성"""
        recommendations = []
        
        # 1. 노이즈 손절 관련
        if noise_analysis.get('noise_ratio', 0) > 30:
            recommendations.append({
                'priority': 'HIGH',
                'category': 'RISK_MANAGEMENT',
                'issue': f"노이즈 손절 비율이 {noise_analysis['noise_ratio']}%로 높음",
                'suggestion': "ATR 멀티플라이어를 1.0에서 1.2로 상향 조정 권장",
                'expected_impact': "노이즈 손절 30% → 15% 감소 예상"
            })
        
        # 2. 승률 관련
        if basic_stats.get('win_rate', 0) < 40:
            recommendations.append({
                'priority': 'HIGH',
                'category': 'ENTRY_QUALITY',
                'issue': f"승률이 {basic_stats.get('win_rate', 0)}%로 낮음",
                'suggestion': "에이전트 임계값 상향 조정 (차티스트 60 → 65)",
                'expected_impact': "진입 빈도 감소하나 승률 향상 예상"
            })
        
        # 3. 시장 조건 관련
        if market_performance.get('worst_conditions'):
            worst = market_performance['worst_conditions'][1]
            if worst['avg_pnl'] < -3:
                recommendations.append({
                    'priority': 'MEDIUM',
                    'category': 'MARKET_FILTER',
                    'issue': f"{worst['trend']} + {worst['volatility']} 조합에서 평균 {worst['avg_pnl']}% 손실",
                    'suggestion': f"{worst['trend']} 시장에서는 진입 자제 또는 포지션 축소",
                    'expected_impact': "해당 시장 조건에서의 손실 회피"
                })
        
        # 4. 거래 시간 관련
        if basic_stats.get('avg_duration_minutes', 0) > 240:  # 4시간 이상
            recommendations.append({
                'priority': 'LOW',
                'category': 'POSITION_MANAGEMENT',
                'issue': f"평균 거래 시간이 {basic_stats['avg_duration_minutes']}분으로 김",
                'suggestion': "부분 익절 전략 활성화 검토",
                'expected_impact': "수익 실현 기회 증가"
            })
        
        return recommendations
    
    def _get_noise_recommendation(self, noise_ratio: float) -> str:
        """노이즈 비율에 따른 권장사항"""
        if noise_ratio > 40:
            return "심각: ATR 멀티플라이어 1.3 이상으로 즉시 상향"
        elif noise_ratio > 30:
            return "높음: ATR 멀티플라이어 1.2로 상향 권장"
        elif noise_ratio > 20:
            return "보통: 현재 설정 유지하며 모니터링"
        else:
            return "양호: 현재 설정이 적절함"
    
    def _save_report(self, report: Dict):
        """리포트 저장"""
        try:
            import os
            
            # reports 폴더 확인 및 생성
            reports_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'reports')
            if not os.path.exists(reports_dir):
                os.makedirs(reports_dir)
                self.logger.info("📁 reports 폴더 생성됨")
            
            filename = os.path.join(reports_dir, f"weekly_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
            self.logger.info(f"✅ 주간 리포트 저장: {filename}")
        except Exception as e:
            self.logger.error(f"❌ 리포트 저장 실패: {e}")
    
    def _send_discord_summary(self, report: Dict):
        """Discord로 요약 전송"""
        try:
            basic = report.get('basic_stats', {})
            noise = report.get('noise_analysis', {})
            
            if basic.get('no_trades'):
                message = "📊 **주간 리포트**\n이번 주 거래 없음"
            else:
                message = f"""📊 **주간 성과 리포트**
                
**기간**: {report['period']['days']}일
**총 거래**: {basic.get('total_trades', 0)}건
**승률**: {basic.get('win_rate', 0)}%
**총 수익률**: {basic.get('total_pnl_percent', 0)}%

**노이즈 분석**
- 노이즈 손절: {noise.get('noise_stops', 0)}건 ({noise.get('noise_ratio', 0)}%)
- 권장사항: {noise.get('recommendation', 'N/A')}

**주요 개선 제안**"""
            
            # 상위 2개 권장사항 추가
            for rec in report.get('recommendations', [])[:2]:
                message += f"\n• [{rec['priority']}] {rec['suggestion']}"
            
            discord_notifier.send_message(message)
            
        except Exception as e:
            self.logger.error(f"❌ Discord 알림 실패: {e}")


# 전역 리포트 생성기 인스턴스
weekly_report = WeeklyPerformanceReport()