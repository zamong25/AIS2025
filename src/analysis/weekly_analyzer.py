"""
델파이 트레이딩 시스템 - 주간 성과 분석기
매주 시나리오별, 시장 상황별 성과를 분석하여 개선 포인트 도출
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import sqlite3
import os
import numpy as np


class WeeklyPerformanceAnalyzer:
    """주간 시나리오 성과 분석"""
    
    def __init__(self, db_path: str = "data/database/delphi_trades.db"):
        self.db_path = db_path
        self.report_dir = "reports/weekly"
        self.logger = logging.getLogger('WeeklyAnalyzer')
        
        # 리포트 디렉토리 생성
        os.makedirs(self.report_dir, exist_ok=True)
        
        self.logger.info("📊 주간 분석기 초기화")
    
    def generate_weekly_report(self, end_date: Optional[datetime] = None) -> Dict:
        """주간 성과 리포트 생성"""
        try:
            if end_date is None:
                end_date = datetime.now()
            
            start_date = end_date - timedelta(days=7)
            
            # 1. 전체 성과 요약
            summary = self._get_weekly_summary(start_date, end_date)
            
            # 2. 시나리오별 성과
            scenario_analysis = self._analyze_by_scenario(start_date, end_date)
            
            # 3. 시장 조건별 성과
            market_analysis = self._analyze_by_market(start_date, end_date)
            
            # 4. 리스크 분석
            risk_analysis = self._analyze_risk_metrics(start_date, end_date)
            
            # 5. 시간대별 분석
            temporal_analysis = self._analyze_temporal_patterns(start_date, end_date)
            
            # 6. 권장사항 생성
            recommendations = self._generate_recommendations(
                summary,
                scenario_analysis, 
                market_analysis, 
                risk_analysis
            )
            
            report = {
                'week': end_date.strftime('%Y-W%V'),
                'period': {
                    'start': start_date.isoformat(),
                    'end': end_date.isoformat()
                },
                'summary': summary,
                'scenario_analysis': scenario_analysis,
                'market_analysis': market_analysis,
                'risk_analysis': risk_analysis,
                'temporal_analysis': temporal_analysis,
                'recommendations': recommendations,
                'generated_at': datetime.now().isoformat()
            }
            
            # 파일로 저장
            self._save_report(report)
            
            # DB에도 요약 저장
            self._save_report_summary(report)
            
            self.logger.info(f"✅ 주간 리포트 생성 완료: {report['week']}")
            return report
            
        except Exception as e:
            self.logger.error(f"❌ 주간 리포트 생성 실패: {e}")
            return {'status': 'error', 'message': str(e)}
    
    def _get_weekly_summary(self, start_date: datetime, end_date: datetime) -> Dict:
        """주간 전체 요약"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # 기본 통계
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_trades,
                    SUM(CASE WHEN outcome = 'WIN' THEN 1 ELSE 0 END) as wins,
                    AVG(pnl_percent) as avg_pnl,
                    SUM(pnl_percent) as total_pnl,
                    MAX(pnl_percent) as best_trade,
                    MIN(pnl_percent) as worst_trade,
                    AVG(max_adverse_excursion) as avg_mdd
                FROM trade_records
                WHERE exit_time BETWEEN ? AND ?
                  AND outcome IS NOT NULL
            """, (start_date.isoformat(), end_date.isoformat()))
            
            row = cursor.fetchone()
            if not row or row[0] == 0:
                return {'total_trades': 0, 'message': '이번 주 거래 없음'}
            
            total_trades = row[0]
            wins = row[1]
            
            # 방향별 통계
            cursor.execute("""
                SELECT 
                    direction,
                    COUNT(*) as count,
                    AVG(pnl_percent) as avg_pnl
                FROM trade_records
                WHERE exit_time BETWEEN ? AND ?
                  AND outcome IS NOT NULL
                GROUP BY direction
            """, (start_date.isoformat(), end_date.isoformat()))
            
            direction_stats = {}
            for dir_row in cursor.fetchall():
                direction_stats[dir_row[0]] = {
                    'count': dir_row[1],
                    'avg_pnl': round(dir_row[2], 2) if dir_row[2] else 0
                }
            
            return {
                'total_trades': total_trades,
                'win_rate': round(wins / total_trades * 100, 1),
                'wins': wins,
                'losses': total_trades - wins,
                'avg_pnl': round(row[2], 2) if row[2] else 0,
                'total_pnl': round(row[3], 2) if row[3] else 0,
                'best_trade': round(row[4], 2) if row[4] else 0,
                'worst_trade': round(row[5], 2) if row[5] else 0,
                'avg_mdd': round(row[6], 2) if row[6] else 0,
                'by_direction': direction_stats
            }
            
        finally:
            conn.close()
    
    def _analyze_by_scenario(self, start_date: datetime, end_date: datetime) -> Dict:
        """시나리오별 성과 분석"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT 
                    s.selected_scenario,
                    COUNT(*) as count,
                    SUM(CASE WHEN t.outcome = 'WIN' THEN 1 ELSE 0 END) as wins,
                    AVG(t.pnl_percent) as avg_pnl,
                    AVG(t.max_adverse_excursion) as avg_mdd,
                    AVG(s.accuracy_score) as avg_accuracy
                FROM trade_records t
                JOIN scenario_tracking s ON t.trade_id = s.trade_id
                WHERE t.exit_time BETWEEN ? AND ?
                  AND t.outcome IS NOT NULL
                  AND s.selected_scenario IS NOT NULL
                GROUP BY s.selected_scenario
                ORDER BY count DESC
            """, (start_date.isoformat(), end_date.isoformat()))
            
            scenarios = {}
            for row in cursor.fetchall():
                scenario = row[0]
                count = row[1]
                wins = row[2]
                
                scenarios[scenario] = {
                    'count': count,
                    'win_rate': round(wins / count * 100, 1) if count > 0 else 0,
                    'avg_pnl': round(row[3], 2) if row[3] else 0,
                    'avg_mdd': round(row[4], 2) if row[4] else 0,
                    'avg_accuracy': round(row[5], 2) if row[5] else None,
                    'performance_score': self._calculate_performance_score(
                        wins / count if count > 0 else 0,
                        row[3] or 0,
                        row[4] or 0
                    )
                }
            
            # 베스트/워스트 시나리오 식별
            if scenarios:
                best_scenario = max(scenarios.items(), 
                                  key=lambda x: x[1]['performance_score'])
                worst_scenario = min(scenarios.items(), 
                                   key=lambda x: x[1]['performance_score'])
                
                return {
                    'scenarios': scenarios,
                    'best': {'name': best_scenario[0], **best_scenario[1]},
                    'worst': {'name': worst_scenario[0], **worst_scenario[1]},
                    'total_scenarios': len(scenarios)
                }
            
            return {'scenarios': {}, 'message': '시나리오 데이터 없음'}
            
        finally:
            conn.close()
    
    def _analyze_by_market(self, start_date: datetime, end_date: datetime) -> Dict:
        """시장 조건별 성과 분석"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # 트렌드 강도별 분석
            cursor.execute("""
                SELECT 
                    CASE 
                        WHEN m.trend_strength >= 3 THEN 'strong_uptrend'
                        WHEN m.trend_strength >= 1 THEN 'uptrend'
                        WHEN m.trend_strength >= -1 THEN 'ranging'
                        WHEN m.trend_strength >= -3 THEN 'downtrend'
                        ELSE 'strong_downtrend'
                    END as market_regime,
                    COUNT(*) as count,
                    SUM(CASE WHEN t.outcome = 'WIN' THEN 1 ELSE 0 END) as wins,
                    AVG(t.pnl_percent) as avg_pnl
                FROM trade_records t
                JOIN market_context m ON t.trade_id = m.trade_id
                WHERE t.exit_time BETWEEN ? AND ?
                  AND t.outcome IS NOT NULL
                GROUP BY market_regime
            """, (start_date.isoformat(), end_date.isoformat()))
            
            market_regimes = {}
            for row in cursor.fetchall():
                regime = row[0]
                count = row[1]
                wins = row[2]
                
                market_regimes[regime] = {
                    'count': count,
                    'win_rate': round(wins / count * 100, 1) if count > 0 else 0,
                    'avg_pnl': round(row[3], 2) if row[3] else 0
                }
            
            # 구조적 위치별 분석
            cursor.execute("""
                SELECT 
                    m.structural_position,
                    COUNT(*) as count,
                    AVG(t.pnl_percent) as avg_pnl
                FROM trade_records t
                JOIN market_context m ON t.trade_id = m.trade_id
                WHERE t.exit_time BETWEEN ? AND ?
                  AND t.outcome IS NOT NULL
                  AND m.structural_position IS NOT NULL
                GROUP BY m.structural_position
            """, (start_date.isoformat(), end_date.isoformat()))
            
            structural_positions = {}
            for row in cursor.fetchall():
                structural_positions[row[0]] = {
                    'count': row[1],
                    'avg_pnl': round(row[2], 2) if row[2] else 0
                }
            
            return {
                'by_trend': market_regimes,
                'by_structure': structural_positions,
                'insights': self._generate_market_insights(market_regimes, structural_positions)
            }
            
        finally:
            conn.close()
    
    def _analyze_risk_metrics(self, start_date: datetime, end_date: datetime) -> Dict:
        """리스크 지표 분석"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # MDD 분포
            cursor.execute("""
                SELECT 
                    CASE 
                        WHEN max_adverse_excursion < 1 THEN '<1%'
                        WHEN max_adverse_excursion < 2 THEN '1-2%'
                        WHEN max_adverse_excursion < 3 THEN '2-3%'
                        WHEN max_adverse_excursion < 5 THEN '3-5%'
                        ELSE '>5%'
                    END as mdd_range,
                    COUNT(*) as count,
                    AVG(CASE WHEN outcome = 'WIN' THEN 1 ELSE 0 END) as win_rate
                FROM trade_records
                WHERE exit_time BETWEEN ? AND ?
                  AND outcome IS NOT NULL
                  AND max_adverse_excursion IS NOT NULL
                GROUP BY mdd_range
                ORDER BY max_adverse_excursion
            """, (start_date.isoformat(), end_date.isoformat()))
            
            mdd_distribution = {}
            for row in cursor.fetchall():
                mdd_distribution[row[0]] = {
                    'count': row[1],
                    'win_rate': round(row[2] * 100, 1)
                }
            
            # 리스크 조정 수익률
            cursor.execute("""
                SELECT 
                    AVG(pnl_percent) as avg_return,
                    STDEV(pnl_percent) as volatility,
                    MAX(max_adverse_excursion) as max_mdd,
                    COUNT(*) as trade_count
                FROM trade_records
                WHERE exit_time BETWEEN ? AND ?
                  AND outcome IS NOT NULL
            """, (start_date.isoformat(), end_date.isoformat()))
            
            row = cursor.fetchone()
            if row and row[0] is not None and row[1] is not None and row[1] > 0:
                sharpe_ratio = row[0] / row[1] * np.sqrt(252)  # 연환산
                calmar_ratio = row[0] / row[2] if row[2] > 0 else 0
                
                risk_metrics = {
                    'avg_return': round(row[0], 2),
                    'volatility': round(row[1], 2),
                    'max_mdd': round(row[2], 2) if row[2] else 0,
                    'sharpe_ratio': round(sharpe_ratio, 2),
                    'calmar_ratio': round(calmar_ratio, 2),
                    'mdd_distribution': mdd_distribution
                }
            else:
                risk_metrics = {
                    'message': '리스크 지표 계산을 위한 데이터 부족',
                    'mdd_distribution': mdd_distribution
                }
            
            return risk_metrics
            
        finally:
            conn.close()
    
    def _analyze_temporal_patterns(self, start_date: datetime, end_date: datetime) -> Dict:
        """시간대별 패턴 분석"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # 시간대별 성과
            cursor.execute("""
                SELECT 
                    m.hour_of_day,
                    COUNT(*) as count,
                    AVG(CASE WHEN t.outcome = 'WIN' THEN 1 ELSE 0 END) as win_rate,
                    AVG(t.pnl_percent) as avg_pnl
                FROM trade_records t
                JOIN market_context m ON t.trade_id = m.trade_id
                WHERE t.exit_time BETWEEN ? AND ?
                  AND t.outcome IS NOT NULL
                GROUP BY m.hour_of_day
                HAVING count >= 2
                ORDER BY m.hour_of_day
            """, (start_date.isoformat(), end_date.isoformat()))
            
            hourly_performance = {}
            best_hours = []
            worst_hours = []
            
            for row in cursor.fetchall():
                hour = row[0]
                win_rate = row[2] * 100
                avg_pnl = row[3]
                
                hourly_performance[hour] = {
                    'count': row[1],
                    'win_rate': round(win_rate, 1),
                    'avg_pnl': round(avg_pnl, 2) if avg_pnl else 0
                }
                
                if win_rate > 70 and row[1] >= 3:
                    best_hours.append(hour)
                elif win_rate < 30 and row[1] >= 3:
                    worst_hours.append(hour)
            
            # 요일별 성과
            cursor.execute("""
                SELECT 
                    m.day_of_week,
                    COUNT(*) as count,
                    AVG(t.pnl_percent) as avg_pnl
                FROM trade_records t
                JOIN market_context m ON t.trade_id = m.trade_id
                WHERE t.exit_time BETWEEN ? AND ?
                  AND t.outcome IS NOT NULL
                GROUP BY m.day_of_week
                ORDER BY m.day_of_week
            """, (start_date.isoformat(), end_date.isoformat()))
            
            daily_performance = {}
            day_names = ['월', '화', '수', '목', '금', '토', '일']
            
            for row in cursor.fetchall():
                day = row[0]
                if 0 <= day <= 6:
                    daily_performance[day_names[day]] = {
                        'count': row[1],
                        'avg_pnl': round(row[2], 2) if row[2] else 0
                    }
            
            return {
                'by_hour': hourly_performance,
                'by_day': daily_performance,
                'best_hours': best_hours,
                'worst_hours': worst_hours
            }
            
        finally:
            conn.close()
    
    def _calculate_performance_score(self, win_rate: float, avg_pnl: float, avg_mdd: float) -> float:
        """종합 성과 점수 계산"""
        # 승률 점수 (0-40점)
        win_score = win_rate * 40
        
        # 수익률 점수 (0-40점)
        pnl_score = min(40, max(0, (avg_pnl + 2) * 10))
        
        # MDD 점수 (0-20점)
        mdd_score = max(0, 20 - avg_mdd * 4)
        
        return round(win_score + pnl_score + mdd_score, 1)
    
    def _generate_market_insights(self, market_regimes: Dict, structural_positions: Dict) -> List[str]:
        """시장 조건 인사이트 생성"""
        insights = []
        
        # 트렌드별 성과
        best_regime = None
        best_pnl = -999
        
        for regime, stats in market_regimes.items():
            if stats['avg_pnl'] > best_pnl and stats['count'] >= 3:
                best_regime = regime
                best_pnl = stats['avg_pnl']
        
        if best_regime:
            insights.append(f"📈 {best_regime} 시장에서 최고 성과 (평균 {best_pnl:.1f}%)")
        
        # 구조적 위치별 성과
        if 'breakout' in structural_positions and structural_positions['breakout']['count'] >= 3:
            breakout_pnl = structural_positions['breakout']['avg_pnl']
            if breakout_pnl > 1:
                insights.append(f"🚀 돌파 거래 성과 우수 (평균 {breakout_pnl:.1f}%)")
        
        return insights
    
    def _generate_recommendations(self, summary: Dict, scenario_analysis: Dict, 
                                market_analysis: Dict, risk_analysis: Dict) -> List[str]:
        """주간 권장사항 생성"""
        recommendations = []
        
        # 1. 승률 기반 권장사항
        win_rate = summary.get('win_rate', 0)
        if win_rate < 40:
            recommendations.append("⚠️ 낮은 승률 - 진입 기준을 더 엄격하게 조정 필요")
        elif win_rate > 70:
            recommendations.append("✅ 높은 승률 유지 중 - 현재 전략 지속")
        
        # 2. MDD 기반 권장사항
        avg_mdd = summary.get('avg_mdd', 0)
        if avg_mdd > 3:
            recommendations.append("📉 높은 MDD - 손절 기준을 더 타이트하게 설정")
        
        # 3. 시나리오 기반 권장사항
        if 'best' in scenario_analysis:
            best = scenario_analysis['best']
            recommendations.append(f"🎯 '{best['name']}' 시나리오 집중 (승률 {best['win_rate']}%)")
        
        if 'worst' in scenario_analysis and scenario_analysis['worst']['count'] >= 3:
            worst = scenario_analysis['worst']
            if worst['win_rate'] < 30:
                recommendations.append(f"❌ '{worst['name']}' 시나리오 회피 권장")
        
        # 4. 시간대 기반 권장사항
        if 'temporal_analysis' in risk_analysis:
            best_hours = risk_analysis['temporal_analysis'].get('best_hours', [])
            if best_hours:
                recommendations.append(f"🕐 최적 거래 시간: {', '.join(map(str, best_hours))}시")
        
        # 5. 리스크 조정 수익률 기반
        if 'sharpe_ratio' in risk_analysis:
            sharpe = risk_analysis['sharpe_ratio']
            if sharpe < 0.5:
                recommendations.append("📊 낮은 샤프 비율 - 리스크 대비 수익률 개선 필요")
        
        return recommendations[:5]  # 최대 5개 권장사항
    
    def _save_report(self, report: Dict):
        """리포트를 파일로 저장"""
        filename = f"weekly_report_{report['week']}.json"
        filepath = os.path.join(self.report_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        self.logger.info(f"리포트 저장: {filepath}")
    
    def _save_report_summary(self, report: Dict):
        """리포트 요약을 DB에 저장"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            summary = report['summary']
            best_scenario = report.get('scenario_analysis', {}).get('best', {})
            
            cursor.execute("""
                INSERT INTO weekly_reports 
                (week_number, total_trades, win_rate, avg_mdd, 
                 best_scenario, worst_scenario, report_data)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                report['week'],
                summary.get('total_trades', 0),
                summary.get('win_rate', 0),
                summary.get('avg_mdd', 0),
                best_scenario.get('name', ''),
                report.get('scenario_analysis', {}).get('worst', {}).get('name', ''),
                json.dumps(report)
            ))
            
            conn.commit()
            
        except Exception as e:
            self.logger.error(f"리포트 요약 저장 실패: {e}")
            
        finally:
            conn.close()
    
    def get_historical_reports(self, weeks: int = 4) -> List[Dict]:
        """과거 주간 리포트 조회"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT week_number, total_trades, win_rate, avg_mdd, 
                       best_scenario, created_at
                FROM weekly_reports
                ORDER BY created_at DESC
                LIMIT ?
            """, (weeks,))
            
            reports = []
            for row in cursor.fetchall():
                reports.append({
                    'week': row[0],
                    'total_trades': row[1],
                    'win_rate': row[2],
                    'avg_mdd': row[3],
                    'best_scenario': row[4],
                    'created_at': row[5]
                })
            
            return reports
            
        finally:
            conn.close()