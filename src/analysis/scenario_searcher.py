"""
델파이 트레이딩 시스템 - 시나리오 유사성 검색기
과거 유사한 시장 상황과 시나리오에서의 거래 결과를 검색하여 분석
"""

import os
import logging
from typing import Dict, List, Optional
import numpy as np
import sqlite3
import json
from datetime import datetime, timedelta


class ScenarioSimilaritySearcher:
    """시나리오와 시장 상황 기반 유사 거래 검색"""

    def __init__(self, db_path: str = None):
        # 절대 경로로 DB 경로 설정
        if db_path is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            db_dir = os.path.join(base_dir, 'data', 'database')
            self.db_path = os.path.join(db_dir, 'delphi_trades.db')
        else:
            self.db_path = db_path

        self.logger = logging.getLogger('ScenarioSearcher')
        self.logger.info(f"🔍 시나리오 검색기 초기화 (DB: {self.db_path})")
    
    def find_similar_trades(self, current_scenario: str, current_context: Dict, 
                          min_trades: int = 10) -> Dict:
        """현재와 유사한 과거 거래 검색"""
        try:
            # 1. 유사 거래 검색
            similar_trades = self._search_similar_trades(current_scenario, current_context)
            
            if len(similar_trades) < min_trades:
                # 검색 조건 완화
                self.logger.info(f"유사 거래 부족 ({len(similar_trades)}개), 조건 완화")
                similar_trades = self._search_similar_trades_relaxed(current_scenario, current_context)
            
            if len(similar_trades) < 5:
                return {
                    'status': 'insufficient_data',
                    'count': len(similar_trades),
                    'message': f'유사 거래가 {len(similar_trades)}개뿐입니다. 최소 5개 필요.'
                }
            
            # 2. 통계 계산
            statistics = self._calculate_statistics(similar_trades)
            
            # 3. 패턴 식별
            patterns = self._identify_patterns(similar_trades)
            
            # 4. 인사이트 생성
            insights = self._generate_insights(statistics, patterns, current_context)
            
            return {
                'status': 'success',
                'count': len(similar_trades),
                'statistics': statistics,
                'patterns': patterns,
                'insights': insights,
                'confidence': self._calculate_confidence(len(similar_trades)),
                'top_trades': similar_trades[:5]  # 상위 5개 유사 거래
            }
            
        except Exception as e:
            self.logger.error(f"❌ 유사 거래 검색 실패: {e}")
            return {'status': 'error', 'message': str(e)}
    
    def _search_similar_trades(self, scenario: str, context: Dict) -> List[Dict]:
        """SQL로 유사 거래 검색"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        try:
            query = """
            WITH scored_trades AS (
                SELECT 
                    t.*,
                    s.selected_scenario,
                    s.actual_outcome,
                    s.accuracy_score,
                    m.atr_value,
                    m.atr_percentile,
                    m.volume_ratio,
                    m.trend_strength,
                    m.structural_position,
                    m.hour_of_day,
                    m.day_of_week,
                    -- 유사도 점수 계산
                    (
                        ABS(m.trend_strength - ?) * 0.3 +
                        ABS(m.atr_percentile - ?) * 0.2 +
                        CASE WHEN m.structural_position = ? THEN 0 ELSE 0.5 END * 0.3 +
                        ABS(m.volume_ratio - ?) * 0.2
                    ) as similarity_score
                FROM trade_records t
                LEFT JOIN scenario_tracking s ON t.trade_id = s.trade_id
                LEFT JOIN market_context m ON t.trade_id = m.trade_id
                WHERE 
                    s.selected_scenario = ?
                    AND t.exit_time IS NOT NULL
                    AND t.outcome IS NOT NULL
            )
            SELECT * FROM scored_trades
            WHERE similarity_score < 1.0
            ORDER BY similarity_score
            LIMIT 50
            """
            
            params = [
                context.get('trend_strength', 0),
                context.get('atr_percentile', 50),
                context.get('structural_position', 'middle'),
                context.get('volume_ratio', 1),
                scenario
            ]
            
            cursor.execute(query, params)
            results = [dict(row) for row in cursor.fetchall()]
            
            return results
            
        finally:
            conn.close()
    
    def _search_similar_trades_relaxed(self, scenario: str, context: Dict) -> List[Dict]:
        """완화된 조건으로 유사 거래 검색"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        try:
            # 시나리오 조건 제외하고 시장 상황만으로 검색
            query = """
            WITH scored_trades AS (
                SELECT 
                    t.*,
                    s.selected_scenario,
                    s.actual_outcome,
                    m.trend_strength,
                    m.structural_position,
                    -- 더 관대한 유사도 계산
                    (
                        ABS(m.trend_strength - ?) * 0.5 +
                        CASE WHEN m.structural_position = ? THEN 0 ELSE 0.5 END * 0.5
                    ) as similarity_score
                FROM trade_records t
                LEFT JOIN scenario_tracking s ON t.trade_id = s.trade_id
                LEFT JOIN market_context m ON t.trade_id = m.trade_id
                WHERE 
                    t.exit_time IS NOT NULL
                    AND t.outcome IS NOT NULL
                    AND m.trend_strength IS NOT NULL
            )
            SELECT * FROM scored_trades
            WHERE similarity_score < 1.5
            ORDER BY similarity_score
            LIMIT 30
            """
            
            params = [
                context.get('trend_strength', 0),
                context.get('structural_position', 'middle')
            ]
            
            cursor.execute(query, params)
            results = [dict(row) for row in cursor.fetchall()]
            
            return results
            
        finally:
            conn.close()
    
    def _calculate_statistics(self, trades: List[Dict]) -> Dict:
        """거래 통계 계산"""
        if not trades:
            return {}
        
        wins = [t for t in trades if t.get('outcome') == 'WIN']
        losses = [t for t in trades if t.get('outcome') == 'LOSS']
        
        # PnL 통계
        pnls = [t.get('pnl_percent', 0) for t in trades]
        win_pnls = [t.get('pnl_percent', 0) for t in wins]
        loss_pnls = [t.get('pnl_percent', 0) for t in losses]
        
        # MDD 통계
        mdds = [t.get('max_adverse_excursion', 0) for t in trades if t.get('max_adverse_excursion')]
        
        # 보유 시간 통계
        durations = []
        for t in trades:
            if t.get('entry_time') and t.get('exit_time'):
                entry = datetime.fromisoformat(t['entry_time'].replace('Z', '+00:00'))
                exit = datetime.fromisoformat(t['exit_time'].replace('Z', '+00:00'))
                duration = (exit - entry).total_seconds() / 3600  # 시간 단위
                durations.append(duration)
        
        return {
            'total_trades': len(trades),
            'win_rate': len(wins) / len(trades) * 100 if trades else 0,
            'avg_pnl': np.mean(pnls) if pnls else 0,
            'avg_win': np.mean(win_pnls) if win_pnls else 0,
            'avg_loss': np.mean(loss_pnls) if loss_pnls else 0,
            'max_win': max(win_pnls) if win_pnls else 0,
            'max_loss': min(loss_pnls) if loss_pnls else 0,
            'avg_mdd': np.mean(mdds) if mdds else 0,
            'max_mdd': max(mdds) if mdds else 0,
            'avg_duration_hours': np.mean(durations) if durations else 0,
            'profit_factor': abs(sum(win_pnls) / sum(loss_pnls)) if loss_pnls and sum(loss_pnls) != 0 else 0
        }
    
    def _identify_patterns(self, trades: List[Dict]) -> Dict:
        """거래 패턴 식별"""
        patterns = {
            'by_hour': {},
            'by_day': {},
            'by_direction': {'LONG': [], 'SHORT': []},
            'by_market_regime': {},
            'consecutive_outcomes': []
        }
        
        # 시간대별 성과
        for t in trades:
            hour = t.get('hour_of_day', -1)
            if hour >= 0:
                if hour not in patterns['by_hour']:
                    patterns['by_hour'][hour] = {'wins': 0, 'losses': 0}
                if t.get('outcome') == 'WIN':
                    patterns['by_hour'][hour]['wins'] += 1
                else:
                    patterns['by_hour'][hour]['losses'] += 1
        
        # 요일별 성과
        for t in trades:
            day = t.get('day_of_week', -1)
            if day >= 0:
                if day not in patterns['by_day']:
                    patterns['by_day'][day] = {'wins': 0, 'losses': 0}
                if t.get('outcome') == 'WIN':
                    patterns['by_day'][day]['wins'] += 1
                else:
                    patterns['by_day'][day]['losses'] += 1
        
        # 방향별 성과
        for t in trades:
            direction = t.get('direction', '')
            if direction in patterns['by_direction']:
                patterns['by_direction'][direction].append({
                    'outcome': t.get('outcome'),
                    'pnl': t.get('pnl_percent', 0)
                })
        
        # 연속 결과 패턴
        if len(trades) >= 3:
            outcomes = [t.get('outcome') for t in sorted(trades, key=lambda x: x.get('exit_time', ''))]
            patterns['consecutive_outcomes'] = self._find_streaks(outcomes)
        
        return patterns
    
    def _find_streaks(self, outcomes: List[str]) -> Dict:
        """연속된 승/패 패턴 찾기"""
        streaks = {'max_win_streak': 0, 'max_loss_streak': 0, 'current_streak': 0}
        
        current_outcome = None
        current_count = 0
        
        for outcome in outcomes:
            if outcome == current_outcome:
                current_count += 1
            else:
                if current_outcome == 'WIN':
                    streaks['max_win_streak'] = max(streaks['max_win_streak'], current_count)
                elif current_outcome == 'LOSS':
                    streaks['max_loss_streak'] = max(streaks['max_loss_streak'], current_count)
                
                current_outcome = outcome
                current_count = 1
        
        # 마지막 연속 처리
        if current_outcome == 'WIN':
            streaks['max_win_streak'] = max(streaks['max_win_streak'], current_count)
        elif current_outcome == 'LOSS':
            streaks['max_loss_streak'] = max(streaks['max_loss_streak'], current_count)
        
        return streaks
    
    def _generate_insights(self, statistics: Dict, patterns: Dict, context: Dict) -> List[str]:
        """통계와 패턴에서 인사이트 생성"""
        insights = []
        
        # 승률 인사이트
        win_rate = statistics.get('win_rate', 0)
        if win_rate > 70:
            insights.append(f"✅ 높은 승률: {win_rate:.1f}% - 이 시나리오/상황은 신뢰할 만함")
        elif win_rate < 40:
            insights.append(f"⚠️ 낮은 승률: {win_rate:.1f}% - 주의가 필요한 상황")
        
        # 손익비 인사이트
        avg_win = statistics.get('avg_win', 0)
        avg_loss = abs(statistics.get('avg_loss', 0))
        if avg_loss > 0 and avg_win / avg_loss > 2:
            insights.append(f"💰 우수한 손익비: {avg_win/avg_loss:.1f}:1")
        
        # MDD 인사이트
        avg_mdd = statistics.get('avg_mdd', 0)
        if avg_mdd > 3:
            insights.append(f"📉 평균 MDD가 높음 ({avg_mdd:.1f}%) - 리스크 관리 강화 필요")
        
        # 시간대 패턴
        best_hours = []
        for hour, data in patterns.get('by_hour', {}).items():
            total = data['wins'] + data['losses']
            if total >= 3 and data['wins'] / total > 0.7:
                best_hours.append(hour)
        
        if best_hours:
            insights.append(f"🕐 최적 거래 시간: {', '.join(map(str, best_hours))}시")
        
        # 현재 상황과의 비교
        trend = context.get('trend_strength', 0)
        if trend > 2:
            strong_trend_wins = sum(1 for t in statistics.get('trades', []) 
                                  if t.get('trend_strength', 0) > 2 and t.get('outcome') == 'WIN')
            if strong_trend_wins > 5:
                insights.append(f"📈 강한 상승 트렌드에서 좋은 성과 기록")
        
        # 거래 수 경고
        total = statistics.get('total_trades', 0)
        if total < 20:
            insights.append(f"📊 샘플 수 부족 ({total}개) - 통계의 신뢰도 제한적")
        
        return insights[:5]  # 최대 5개 인사이트
    
    def _calculate_confidence(self, trade_count: int) -> float:
        """거래 수에 따른 신뢰도 계산"""
        if trade_count >= 50:
            return 95.0
        elif trade_count >= 30:
            return 85.0
        elif trade_count >= 20:
            return 75.0
        elif trade_count >= 10:
            return 60.0
        else:
            return 40.0
    
    def get_scenario_performance(self, scenario: str, days: int = 30) -> Dict:
        """특정 시나리오의 최근 성과 조회"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            since_date = (datetime.now() - timedelta(days=days)).isoformat()
            
            cursor.execute("""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN t.outcome = 'WIN' THEN 1 ELSE 0 END) as wins,
                    AVG(t.pnl_percent) as avg_pnl,
                    AVG(t.max_adverse_excursion) as avg_mdd
                FROM trade_records t
                JOIN scenario_tracking s ON t.trade_id = s.trade_id
                WHERE s.selected_scenario = ?
                  AND t.exit_time > ?
                  AND t.outcome IS NOT NULL
            """, (scenario, since_date))
            
            row = cursor.fetchone()
            if row and row[0] > 0:
                return {
                    'scenario': scenario,
                    'period_days': days,
                    'total_trades': row[0],
                    'win_rate': (row[1] / row[0] * 100) if row[0] > 0 else 0,
                    'avg_pnl': row[2] or 0,
                    'avg_mdd': row[3] or 0
                }
            
            return {'scenario': scenario, 'total_trades': 0, 'message': '해당 기간에 거래 없음'}
            
        finally:
            conn.close()