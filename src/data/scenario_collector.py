"""
델파이 트레이딩 시스템 - 시나리오 데이터 수집기
거래 진입 시 시나리오 정보와 시장 컨텍스트를 수집하여 저장
"""

import json
import logging
import os
from datetime import datetime
from typing import Dict, Any, Optional, List
import sqlite3


class ScenarioDataCollector:
    """시나리오 기반 데이터 수집"""

    def __init__(self, db_path: str = None):
        # db_path가 None이면 절대 경로로 설정
        if db_path is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            db_dir = os.path.join(base_dir, 'data', 'database')
            self.db_path = os.path.join(db_dir, 'delphi_trades.db')
        else:
            self.db_path = db_path

        self.logger = logging.getLogger('ScenarioCollector')
        
        # MarketContextAnalyzer 임포트
        try:
            from .market_analyzer import MarketContextAnalyzer
            self.market_analyzer = MarketContextAnalyzer()
        except ImportError:
            self.logger.warning("MarketContextAnalyzer 임포트 실패, 기본값 사용")
            self.market_analyzer = None
        
        self.logger.info("📊 시나리오 데이터 수집기 초기화")
    
    def collect_entry_data(self, trade_id: str, agent_data: Dict, decision: Dict):
        """거래 진입 시 데이터 수집"""
        try:
            # 1. 시나리오 정보 저장
            self._save_scenario_tracking(trade_id, agent_data, decision)
            
            # 2. 시장 컨텍스트 저장
            self._save_market_context(trade_id, agent_data)
            
            # 3. trade_records 업데이트
            self._update_trade_record(trade_id, decision)
            
            self.logger.info(f"✅ {trade_id} 진입 데이터 수집 완료")
            
        except Exception as e:
            self.logger.error(f"❌ 데이터 수집 실패 ({trade_id}): {e}")
            # 실패해도 거래는 계속 진행
    
    def _save_scenario_tracking(self, trade_id: str, agent_data: Dict, decision: Dict):
        """시나리오 추적 정보 저장"""
        chartist_data = agent_data.get('chartist', {})
        
        # 시나리오 데이터 추출
        scenarios = chartist_data.get('scenario_analysis', {}).get('scenarios', [])
        if not scenarios:
            # 구버전 호환성
            scenarios = self._extract_scenarios_from_old_format(chartist_data)
        
        # 선택된 시나리오 찾기
        selected_scenario = ""
        if decision.get('scenario'):
            selected_scenario = decision['scenario'].get('type', '')
        elif decision.get('trade_scenario'):
            selected_scenario = decision['trade_scenario']
        
        # 무효화 가격 추출
        invalidation_price = 0
        risk_mgmt = decision.get('risk_management', {})
        if risk_mgmt:
            invalidation_price = risk_mgmt.get('stop_loss', 0)
        
        # 목표가 추출
        target_prices = []
        if risk_mgmt:
            tp1 = risk_mgmt.get('take_profit_1', 0)
            tp2 = risk_mgmt.get('take_profit_2', 0)
            if tp1:
                target_prices.append(tp1)
            if tp2:
                target_prices.append(tp2)
        
        scenario_data = {
            'trade_id': trade_id,
            'chartist_scenarios': json.dumps(scenarios),
            'selected_scenario': selected_scenario,
            'selection_reason': decision.get('rationale', ''),
            'invalidation_price': invalidation_price,
            'target_prices': json.dumps(target_prices)
        }
        
        # DB에 저장
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO scenario_tracking 
                (trade_id, chartist_scenarios, selected_scenario, selection_reason, 
                 invalidation_price, target_prices)
                VALUES (?, ?, ?, ?, ?, ?)
            """, list(scenario_data.values()))
            
            conn.commit()
            self.logger.debug(f"시나리오 추적 정보 저장: {trade_id}")
            
        finally:
            conn.close()
    
    def _save_market_context(self, trade_id: str, agent_data: Dict):
        """시장 컨텍스트 저장"""
        # MarketContextAnalyzer가 구현되면 사용
        if self.market_analyzer is None:
            # 임시로 기본값 저장
            self._save_default_market_context(trade_id, agent_data)
            return
        
        market_data = agent_data.get('market_data', {})
        context = self.market_analyzer.analyze(market_data)
        context['trade_id'] = trade_id
        
        # DB에 저장
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO market_context
                (trade_id, atr_value, atr_percentile, volume_ratio,
                 trend_strength, ma20_slope, price_vs_ma20,
                 distance_from_high20, distance_from_low20, structural_position,
                 hour_of_day, day_of_week)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, list(context.values()))
            
            conn.commit()
            
        finally:
            conn.close()
    
    def _save_default_market_context(self, trade_id: str, agent_data: Dict):
        """기본 시장 컨텍스트 저장 (임시)"""
        # Chartist 데이터에서 일부 정보 추출
        chartist = agent_data.get('chartist', {})
        market_structure = chartist.get('market_structure_analysis', {})
        
        # 트렌드 강도 계산
        trend_bias = chartist.get('quantitative_scorecard', {}).get('overall_bias_score', 50)
        trend_strength = int((trend_bias - 50) / 12.5)  # -4 to 4로 변환
        
        # 구조적 위치 판단
        structural_position = "middle"
        if market_structure.get('key_breakout_levels'):
            structural_position = "near_resistance"
        elif market_structure.get('key_support_levels'):
            structural_position = "near_support"
        
        # 현재 시간
        now = datetime.now()
        
        context = {
            'trade_id': trade_id,
            'atr_value': 0,  # 나중에 계산
            'atr_percentile': 50,
            'volume_ratio': 1.0,
            'trend_strength': trend_strength,
            'ma20_slope': 0,
            'price_vs_ma20': 0,
            'distance_from_high20': 0,
            'distance_from_low20': 0,
            'structural_position': structural_position,
            'hour_of_day': now.hour,
            'day_of_week': now.weekday()
        }
        
        # DB에 저장
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO market_context
                (trade_id, atr_value, atr_percentile, volume_ratio,
                 trend_strength, ma20_slope, price_vs_ma20,
                 distance_from_high20, distance_from_low20, structural_position,
                 hour_of_day, day_of_week)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, list(context.values()))
            
            conn.commit()
            
        finally:
            conn.close()
    
    def _update_trade_record(self, trade_id: str, decision: Dict):
        """trade_records 테이블에 시나리오 정보 업데이트"""
        # 시나리오 정보 추출
        selected_scenario = ""
        if decision.get('scenario'):
            selected_scenario = decision['scenario'].get('type', '')
        elif decision.get('trade_scenario'):
            selected_scenario = decision['trade_scenario']
        
        confidence = decision.get('confidence_score', 50)
        
        # DB 업데이트
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                UPDATE trade_records
                SET selected_scenario = ?,
                    scenario_confidence = ?
                WHERE trade_id = ?
            """, (selected_scenario, confidence, trade_id))
            
            conn.commit()
            
        except Exception as e:
            self.logger.warning(f"trade_records 업데이트 실패 ({trade_id}): {e}")
            
        finally:
            conn.close()
    
    def _extract_scenarios_from_old_format(self, chartist_data: Dict) -> List[Dict]:
        """구버전 Chartist 데이터에서 시나리오 추출"""
        scenarios = []
        
        # Technical Summary에서 시나리오 추출 시도
        tech_summary = chartist_data.get('technical_summary', {})
        if tech_summary:
            primary = tech_summary.get('primary_scenario', '')
            if primary:
                scenarios.append({
                    'type': 'primary',
                    'description': primary,
                    'probability': 0.6
                })
            
            alternative = tech_summary.get('alternative_scenario', '')
            if alternative:
                scenarios.append({
                    'type': 'alternative', 
                    'description': alternative,
                    'probability': 0.3
                })
        
        return scenarios
    
    def update_scenario_outcome(self, trade_id: str, actual_outcome: str, accuracy_score: float):
        """거래 종료 시 실제 결과 업데이트"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                UPDATE scenario_tracking
                SET actual_outcome = ?,
                    accuracy_score = ?
                WHERE trade_id = ?
            """, (actual_outcome, accuracy_score, trade_id))
            
            conn.commit()
            self.logger.info(f"시나리오 결과 업데이트: {trade_id} -> {actual_outcome}")
            
        finally:
            conn.close()
    
    def get_scenario_tracking(self, trade_id: str) -> Optional[Dict]:
        """특정 거래의 시나리오 추적 정보 조회"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT * FROM scenario_tracking WHERE trade_id = ?
            """, (trade_id,))
            
            row = cursor.fetchone()
            if row:
                columns = [desc[0] for desc in cursor.description]
                return dict(zip(columns, row))
            
            return None
            
        finally:
            conn.close()


# MarketContextAnalyzer가 구현되면 임포트
def set_market_analyzer(collector: ScenarioDataCollector, analyzer):
    """MarketContextAnalyzer 설정"""
    collector.market_analyzer = analyzer