"""
델파이 트레이딩 시스템 - 시나리오 학습 시스템 통합
메인 시스템에 시나리오 추적, MDD 모니터링, 유사 거래 검색 기능 통합
"""

import logging
from typing import Dict, Optional
from data.scenario_collector import ScenarioDataCollector
from data.market_analyzer import MarketContextAnalyzer
from monitoring.mdd_tracker import MDDTracker
from analysis.scenario_searcher import ScenarioSimilaritySearcher
from analysis.weekly_analyzer import WeeklyPerformanceAnalyzer


class ScenarioSystemIntegration:
    """시나리오 학습 시스템 통합 클래스"""
    
    def __init__(self, db_path: str = "data/database/delphi_trades.db"):
        self.logger = logging.getLogger('ScenarioIntegration')
        
        # 컴포넌트 초기화
        self.scenario_collector = ScenarioDataCollector(db_path)
        self.mdd_tracker = MDDTracker(db_path)
        self.scenario_searcher = ScenarioSimilaritySearcher(db_path)
        self.weekly_analyzer = WeeklyPerformanceAnalyzer(db_path)
        self.market_analyzer = MarketContextAnalyzer()
        
        self.logger.info("✅ 시나리오 학습 시스템 통합 초기화 완료")
    
    def enhance_agent_reports(self, reports: Dict, target_asset: str) -> Dict:
        """에이전트 리포트에 유사 거래 분석 추가"""
        try:
            # Chartist에서 시나리오 추출
            chartist_report = reports.get('chartist', {})
            scenarios = chartist_report.get('scenario_analysis', {}).get('scenarios', [])
            
            if not scenarios:
                self.logger.debug("시나리오 정보 없음, 유사 거래 검색 스킵")
                return reports
            
            # 가장 가능성 높은 시나리오
            primary_scenario = scenarios[0] if scenarios else {}
            scenario_type = primary_scenario.get('type', '')
            
            # 현재 시장 컨텍스트 분석
            market_data = self._extract_market_data(reports)
            current_context = self.market_analyzer.analyze(market_data)
            
            # 유사 거래 검색
            similar_trades = self.scenario_searcher.find_similar_trades(
                scenario_type,
                current_context
            )
            
            # Quant 리포트에 추가
            if similar_trades.get('status') == 'success':
                if 'quant' not in reports:
                    reports['quant'] = {}
                
                reports['quant']['historical_analysis'] = {
                    'similar_trades': similar_trades,
                    'confidence': similar_trades.get('confidence', 0),
                    'insights': similar_trades.get('insights', [])
                }
                
                self.logger.info(f"📊 유사 거래 {similar_trades['count']}개 발견, Quant 리포트에 추가")
            
            return reports
            
        except Exception as e:
            self.logger.error(f"리포트 강화 실패: {e}")
            return reports
    
    def collect_trade_entry_data(self, trade_id: str, playbook: Dict, reports: Dict):
        """거래 진입 시 시나리오 데이터 수집"""
        try:
            # 에이전트 데이터 구성
            agent_data = {
                'chartist': reports.get('chartist', {}),
                'journalist': reports.get('journalist', {}),
                'quant': reports.get('quant', {}),
                'stoic': reports.get('stoic', {}),
                'market_data': self._extract_market_data(reports)
            }
            
            # 결정 정보 구성
            decision = {
                'action': playbook.get('final_decision', {}).get('action'),
                'scenario': playbook.get('scenario_planning', {}).get('primary_scenario', {}),
                'rationale': playbook.get('final_decision', {}).get('rationale', ''),
                'confidence_score': playbook.get('final_decision', {}).get('confidence_score', 50),
                'risk_management': playbook.get('execution_plan', {}).get('risk_management', {})
            }
            
            # 데이터 수집
            self.scenario_collector.collect_entry_data(trade_id, agent_data, decision)
            
            self.logger.info(f"✅ 거래 진입 데이터 수집 완료: {trade_id}")
            
        except Exception as e:
            self.logger.error(f"거래 진입 데이터 수집 실패: {e}")
    
    def update_position_mdd(self, trade_id: str, current_price: float) -> Dict:
        """포지션 MDD 업데이트 (15분마다 호출)"""
        try:
            position_data = self.mdd_tracker.update_position(trade_id, current_price)
            
            if position_data:
                self.logger.debug(
                    f"MDD 업데이트: {trade_id} - "
                    f"MDD: {position_data.get('current_mdd', 0):.2f}%, "
                    f"MFE: {position_data.get('current_mfe', 0):.2f}%"
                )
            
            return position_data
            
        except Exception as e:
            self.logger.error(f"MDD 업데이트 실패: {e}")
            return {}
    
    def update_trade_exit_data(self, trade_id: str, outcome: str, actual_scenario: str = None):
        """거래 종료 시 결과 업데이트"""
        try:
            # 시나리오 정확도 계산
            accuracy_score = 0
            if actual_scenario:
                # 실제 시나리오와 예측 시나리오 비교
                tracking = self.scenario_collector.get_scenario_tracking(trade_id)
                if tracking and tracking.get('selected_scenario') == actual_scenario:
                    accuracy_score = 100
                else:
                    accuracy_score = 0
            
            # 결과 업데이트
            self.scenario_collector.update_scenario_outcome(
                trade_id,
                actual_scenario or outcome,
                accuracy_score
            )
            
            # MDD 캐시 클리어
            self.mdd_tracker.clear_position_cache(trade_id)
            
            self.logger.info(f"✅ 거래 종료 데이터 업데이트: {trade_id}")
            
        except Exception as e:
            self.logger.error(f"거래 종료 데이터 업데이트 실패: {e}")
    
    def generate_weekly_report_if_needed(self, current_hour: int, current_day: int):
        """필요시 주간 리포트 생성 (일요일 23시)"""
        try:
            # 일요일(6) 23시에 실행
            if current_day == 6 and current_hour == 23:
                self.logger.info("📊 주간 성과 리포트 생성 시작...")
                
                report = self.weekly_analyzer.generate_weekly_report()
                
                if report.get('status') != 'error':
                    self.logger.info(f"✅ 주간 리포트 생성 완료: {report['week']}")
                    
                    # 주요 지표 로깅
                    summary = report.get('summary', {})
                    self.logger.info(
                        f"주간 성과: 거래 {summary.get('total_trades', 0)}건, "
                        f"승률 {summary.get('win_rate', 0):.1f}%, "
                        f"평균 PnL {summary.get('avg_pnl', 0):.2f}%"
                    )
                    
                    # 권장사항 로깅
                    recommendations = report.get('recommendations', [])
                    if recommendations:
                        self.logger.info("💡 주간 권장사항:")
                        for rec in recommendations:
                            self.logger.info(f"   - {rec}")
                else:
                    self.logger.error("주간 리포트 생성 실패")
                    
        except Exception as e:
            self.logger.error(f"주간 리포트 생성 중 오류: {e}")
    
    def _extract_market_data(self, reports: Dict) -> Dict:
        """리포트에서 시장 데이터 추출"""
        market_data = {}
        
        # Quant 리포트에서 데이터 추출
        quant = reports.get('quant', {})
        if quant:
            quant_data = quant.get('market_data', {})
            market_data.update({
                'prices': quant_data.get('prices', []),
                'atr_14': quant_data.get('volatility', 0),
                'volume': quant_data.get('volume_24h', 0),
                'avg_volume_20': quant_data.get('avg_volume_20', 0)
            })
        
        # Chartist에서 추가 정보
        chartist = reports.get('chartist', {})
        if chartist:
            indicators = chartist.get('technical_indicators', {})
            market_data['rsi'] = indicators.get('rsi', {}).get('value', 50)
        
        return market_data
    
    def get_mdd_statistics(self) -> Dict:
        """전체 MDD 통계 조회"""
        try:
            return self.mdd_tracker.analyze_mdd_patterns()
        except Exception as e:
            self.logger.error(f"MDD 통계 조회 실패: {e}")
            return {}


# 싱글톤 인스턴스
scenario_integration = ScenarioSystemIntegration()