"""
델파이 트레이딩 시스템 - 거래 컨텍스트 관리
거래의 연속성을 위한 맥락 정보 저장 및 관리
"""

import json
import logging
from datetime import datetime
from typing import Dict, Optional, List
from dataclasses import dataclass, asdict
import os

@dataclass
class TradingThesis:
    """거래 진입 시점의 가설과 계획"""
    trade_id: str
    entry_time: str
    direction: str  # LONG/SHORT
    
    # 진입 정보
    entry_price: float
    entry_reason: str  # 신디사이저의 rationale
    
    # 핵심 시나리오
    primary_scenario: str  # "하락 돌파 후 145까지 하락 예상"
    target_price: float  # 1차 목표가
    stop_loss: float
    
    # 무효화 조건
    invalidation_condition: str  # "158 이상 상승 시 시나리오 무효"
    invalidation_price: float
    
    # 주요 관찰 포인트
    key_levels: List[float]  # [152, 147, 145] 등
    key_events: List[str]  # ["뉴스 발표", "FOMC" 등]
    
    # 초기 신뢰도
    initial_confidence: float
    initial_agent_scores: Dict[str, float]
    
    # 예상 보유 시간
    expected_duration: str  # "4-8시간"


@dataclass
class ContextUpdate:
    """매 실행 시점의 상황 업데이트"""
    update_time: str
    price_at_update: float
    
    # 진행 상황 평가
    scenario_progress: str  # "ON_TRACK", "DEVIATING", "INVALIDATED"
    progress_percentage: float  # 목표 달성률
    
    # 변화된 상황
    market_changes: List[str]  # ["거래량 급증", "저항선 돌파" 등]
    agent_score_changes: Dict[str, float]  # 에이전트별 점수 변화
    
    # AI 판단
    ai_assessment: str  # "계획대로 진행 중, 홀드 유지"
    confidence_change: float  # 신뢰도 변화


class TradingContextManager:
    """거래 맥락 관리자"""
    
    def __init__(self):
        self.logger = logging.getLogger('TradingContext')
        
        # 컨텍스트 저장 경로
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.context_file = os.path.join(project_root, 'data', 'active_trading_context.json')
        
        # 현재 활성 컨텍스트
        self.active_thesis: Optional[TradingThesis] = None
        self.context_history: List[ContextUpdate] = []
        
        # 기존 컨텍스트 로드
        self._load_active_context()
    
    def create_thesis_from_playbook(self, trade_id: str, playbook: Dict, 
                                   agent_reports: Dict) -> TradingThesis:
        """신디사이저 플레이북으로부터 Trading Thesis 생성"""
        
        decision = playbook.get('final_decision', {})
        execution = playbook.get('execution_plan', {})
        scenarios = playbook.get('scenario_planning', {})
        
        # 주요 가격 레벨 추출
        chartist = agent_reports.get('chartist', {})
        key_zones = chartist.get('key_price_zones', {})
        resistance_zones = key_zones.get('resistance_zones', [])
        support_zones = key_zones.get('support_zones', [])
        
        # 키 레벨 리스트 생성
        key_levels = []
        for zone in resistance_zones[:2]:  # 상위 2개 저항
            range_str = zone.get('range', '')
            if '$' in range_str:
                price = float(range_str.split('$')[1].split()[0])
                key_levels.append(price)
        
        for zone in support_zones[:2]:  # 상위 2개 지지
            range_str = zone.get('range', '')
            if '$' in range_str:
                price = float(range_str.split('$')[1].split()[0])
                key_levels.append(price)
        
        # 무효화 가격 파싱
        invalidation = key_zones.get('invalidation_point', {})
        invalidation_text = invalidation.get('condition', '')
        invalidation_price = self._extract_price_from_text(invalidation_text)
        
        thesis = TradingThesis(
            trade_id=trade_id,
            entry_time=datetime.utcnow().isoformat(),
            # V1/V2 형식 지원: V2에서는 final_decision.action으로부터 방향 추론
            direction=execution.get('trade_direction', 'LONG' if decision.get('action') == 'BUY' else 'SHORT'),
            
            # 진입 정보
            entry_price=0,  # 실제 체결가는 나중에 업데이트
            entry_reason=decision.get('rationale', ''),
            
            # 시나리오
            primary_scenario=scenarios.get('primary_scenario', {}).get('description', decision.get('scenario', '')),
            # V1/V2 형식 모두 지원
            target_price=execution.get('risk_management', {}).get('take_profit_1_price', execution.get('take_profit_1', 0)),
            stop_loss=execution.get('risk_management', {}).get('stop_loss_price', execution.get('stop_loss', 0)),
            
            # 무효화
            invalidation_condition=invalidation_text,
            invalidation_price=invalidation_price,
            
            # 관찰 포인트
            key_levels=sorted(key_levels),
            key_events=self._extract_key_events(agent_reports.get('journalist', {})),
            
            # 신뢰도
            initial_confidence=decision.get('confidence_score', 50),
            initial_agent_scores={
                'chartist': chartist.get('quantitative_scorecard', {}).get('overall_bias_score', 50),
                'journalist': agent_reports.get('journalist', {}).get('quantitative_scorecard', {}).get('overall_contextual_bias', {}).get('score', 5),
                'quant': agent_reports.get('quant', {}).get('quantitative_scorecard', {}).get('overall_score', 50),
                'stoic': agent_reports.get('stoic', {}).get('risk_assessment', {}).get('overall_risk_score', 5)
            },
            
            # 예상 시간
            expected_duration=self._map_urgency_to_duration(decision.get('urgency', '중간'))
        )
        
        # 활성화 및 저장
        self.active_thesis = thesis
        self.context_history = []  # 새 거래 시작 시 히스토리 초기화
        self._save_active_context()
        
        self.logger.info(f"✅ Trading Thesis 생성: {trade_id}")
        self.logger.info(f"   시나리오: {thesis.primary_scenario}")
        self.logger.info(f"   목표가: ${thesis.target_price}, 손절가: ${thesis.stop_loss}")
        
        return thesis
    
    def update_entry_price(self, actual_entry_price: float):
        """실제 체결가로 진입가 업데이트"""
        if self.active_thesis:
            self.active_thesis.entry_price = actual_entry_price
            self._save_active_context()
    
    def evaluate_position_progress(self, current_price: float, 
                                 new_agent_reports: Dict) -> Dict:
        """현재 포지션의 진행 상황 평가"""
        
        if not self.active_thesis:
            return None
        
        thesis = self.active_thesis
        
        # 1. 가격 진행률 계산
        if thesis.direction == "LONG":
            total_distance = thesis.target_price - thesis.entry_price
            current_distance = current_price - thesis.entry_price
        else:  # SHORT
            total_distance = thesis.entry_price - thesis.target_price
            current_distance = thesis.entry_price - current_price
        
        progress_pct = (current_distance / total_distance * 100) if total_distance != 0 else 0
        
        # 2. 시나리오 상태 판단
        scenario_status = self._determine_scenario_status(
            thesis, current_price, progress_pct
        )
        
        # 3. 에이전트 점수 변화 분석
        score_changes = {}
        new_scores = self._extract_agent_scores(new_agent_reports)
        
        for agent, initial_score in thesis.initial_agent_scores.items():
            new_score = new_scores.get(agent, initial_score)
            score_changes[agent] = new_score - initial_score
        
        # 4. 주요 변화 감지
        market_changes = self._detect_market_changes(
            thesis, current_price, new_agent_reports
        )
        
        # 5. 컨텍스트 업데이트 생성
        update = ContextUpdate(
            update_time=datetime.utcnow().isoformat(),
            price_at_update=current_price,
            scenario_progress=scenario_status,
            progress_percentage=progress_pct,
            market_changes=market_changes,
            agent_score_changes=score_changes,
            ai_assessment="",  # AI가 나중에 채움
            confidence_change=0  # AI가 나중에 채움
        )
        
        self.context_history.append(update)
        
        # 6. AI를 위한 요약 생성
        context_summary = self._generate_context_summary(thesis, update, current_price)
        
        return {
            'thesis': thesis,
            'latest_update': update,
            'context_summary': context_summary,
            'recommendation': self._generate_recommendation(scenario_status, progress_pct)
        }
    
    def get_position_context_for_ai(self) -> Optional[str]:
        """AI 프롬프트에 포함할 포지션 컨텍스트 생성"""
        
        if not self.active_thesis:
            return None
        
        thesis = self.active_thesis
        latest_update = self.context_history[-1] if self.context_history else None
        
        context = f"""
=== 현재 포지션 컨텍스트 ===
[거래 정보]
- 방향: {thesis.direction}
- 진입가: ${thesis.entry_price}
- 진입 시간: {thesis.entry_time}
- 진입 근거: {thesis.entry_reason}

[초기 계획]
- 시나리오: {thesis.primary_scenario}
- 목표가: ${thesis.target_price}
- 손절가: ${thesis.stop_loss}
- 무효화 조건: {thesis.invalidation_condition}
- 예상 보유 시간: {thesis.expected_duration}

[주요 관찰 레벨]
- {', '.join([f'${level}' for level in thesis.key_levels])}
"""
        
        if latest_update:
            context += f"""
[최근 상황]
- 현재가: ${latest_update.price_at_update}
- 진행 상태: {latest_update.scenario_progress}
- 목표 달성률: {latest_update.progress_percentage:.1f}%
- 주요 변화: {', '.join(latest_update.market_changes) if latest_update.market_changes else '없음'}

[에이전트 점수 변화]
"""
            for agent, change in latest_update.agent_score_changes.items():
                if abs(change) > 5:  # 5점 이상 변화만 표시
                    context += f"- {agent}: {'+' if change > 0 else ''}{change:.0f}점\n"
        
        context += """
[판단 요청]
위 컨텍스트를 바탕으로 다음을 판단해주세요:
1. 초기 시나리오대로 진행되고 있는가?
2. 계획을 유지할 것인가, 수정할 것인가?
3. 구체적인 액션 (홀드/청산/부분익절 등)
"""
        
        return context
    
    def clear_context(self):
        """포지션 종료 시 컨텍스트 클리어"""
        self.active_thesis = None
        self.context_history = []
        
        # 파일도 클리어
        if os.path.exists(self.context_file):
            os.remove(self.context_file)
        
        self.logger.info("✅ Trading Context 클리어됨")
    
    def _extract_price_from_text(self, text: str) -> float:
        """텍스트에서 가격 추출"""
        import re
        # "$155.00" 또는 "155" 형태의 숫자 찾기
        matches = re.findall(r'\$?([\d.]+)', text)
        return float(matches[0]) if matches else 0
    
    def _extract_key_events(self, journalist_report: Dict) -> List[str]:
        """저널리스트 리포트에서 주요 이벤트 추출"""
        events = []
        upcoming = journalist_report.get('detailed_analysis', {}).get('upcoming_events', [])
        
        for event in upcoming[:3]:  # 상위 3개만
            events.append(f"{event.get('event', '')} ({event.get('date', '')})")
        
        return events
    
    def _map_urgency_to_duration(self, urgency: str) -> str:
        """긴급도를 예상 보유 시간으로 매핑"""
        mapping = {
            '높음': '1-4시간',
            '중간': '4-12시간', 
            '낮음': '12-48시간'
        }
        return mapping.get(urgency, '4-12시간')
    
    def _determine_scenario_status(self, thesis: TradingThesis, 
                                 current_price: float, progress_pct: float) -> str:
        """시나리오 진행 상태 판단"""
        
        # 무효화 체크
        if thesis.direction == "LONG" and current_price <= thesis.invalidation_price:
            return "INVALIDATED"
        elif thesis.direction == "SHORT" and current_price >= thesis.invalidation_price:
            return "INVALIDATED"
        
        # 진행률 기반 판단
        if progress_pct >= 80:
            return "NEAR_TARGET"
        elif progress_pct >= 30:
            return "ON_TRACK"
        elif progress_pct >= 0:
            return "EARLY_STAGE"
        else:
            return "DEVIATING"
    
    def _extract_agent_scores(self, agent_reports: Dict) -> Dict[str, float]:
        """에이전트 리포트에서 점수 추출"""
        return {
            'chartist': agent_reports.get('chartist', {}).get('quantitative_scorecard', {}).get('overall_bias_score', 50),
            'journalist': agent_reports.get('journalist', {}).get('quantitative_scorecard', {}).get('overall_contextual_bias', {}).get('score', 5),
            'quant': agent_reports.get('quant', {}).get('quantitative_scorecard', {}).get('overall_score', 50),
            'stoic': agent_reports.get('stoic', {}).get('risk_assessment', {}).get('overall_risk_score', 5)
        }
    
    def _detect_market_changes(self, thesis: TradingThesis, 
                             current_price: float, new_reports: Dict) -> List[str]:
        """주요 시장 변화 감지"""
        changes = []
        
        # 주요 레벨 돌파 체크
        for level in thesis.key_levels:
            if thesis.entry_price < level < current_price:
                changes.append(f"${level} 저항 돌파")
            elif thesis.entry_price > level > current_price:
                changes.append(f"${level} 지지 하향 돌파")
        
        # 뉴스 이벤트 체크
        journalist = new_reports.get('journalist', {})
        if journalist.get('key_briefing', {}).get('most_imminent_event'):
            changes.append("중요 뉴스 이벤트 발생")
        
        return changes[:3]  # 최대 3개만
    
    def _generate_context_summary(self, thesis: TradingThesis, 
                                update: ContextUpdate, current_price: float) -> str:
        """AI를 위한 컨텍스트 요약"""
        
        # 손익 계산
        if thesis.direction == "LONG":
            pnl_pct = ((current_price - thesis.entry_price) / thesis.entry_price) * 100
        else:
            pnl_pct = ((thesis.entry_price - current_price) / thesis.entry_price) * 100
        
        summary = f"""
포지션: {thesis.direction} @ ${thesis.entry_price}
현재가: ${current_price} (손익: {pnl_pct:+.2f}%)
진행 상태: {update.scenario_progress} (목표 달성률: {update.progress_percentage:.0f}%)
초기 시나리오: {thesis.primary_scenario}
"""
        
        if update.market_changes:
            summary += f"주요 변화: {', '.join(update.market_changes)}\n"
        
        return summary
    
    def _generate_recommendation(self, scenario_status: str, progress_pct: float) -> str:
        """상황별 권고사항"""
        
        if scenario_status == "INVALIDATED":
            return "시나리오 무효화 - 포지션 재검토 필요"
        elif scenario_status == "NEAR_TARGET":
            return "목표 근접 - 익절 또는 추가 상승 가능성 검토"
        elif scenario_status == "ON_TRACK":
            return "계획대로 진행 중 - 홀드 유지"
        elif scenario_status == "DEVIATING":
            return "시나리오 이탈 - 손절 또는 전략 수정 검토"
        else:
            return "초기 단계 - 추이 관찰"
    
    def _save_active_context(self):
        """활성 컨텍스트를 파일로 저장"""
        if self.active_thesis:
            data = {
                'thesis': asdict(self.active_thesis),
                'history': [asdict(update) for update in self.context_history]
            }
            
            with open(self.context_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
    
    def _load_active_context(self):
        """저장된 컨텍스트 로드"""
        if os.path.exists(self.context_file):
            try:
                with open(self.context_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Thesis 복원
                thesis_data = data.get('thesis')
                if thesis_data:
                    self.active_thesis = TradingThesis(**thesis_data)
                
                # History 복원
                history_data = data.get('history', [])
                self.context_history = [ContextUpdate(**update) for update in history_data]
                
                self.logger.info(f"✅ 기존 Trading Context 로드됨: {self.active_thesis.trade_id if self.active_thesis else 'None'}")
                
            except Exception as e:
                self.logger.error(f"컨텍스트 로드 실패: {e}")
                self.active_thesis = None
                self.context_history = []
    
    def get_historical_contexts(self, limit: int = 10) -> List[Dict]:
        """히스토리 폴더에서 과거 거래 컨텍스트 조회"""
        historical_contexts = []
        history_base = os.path.join(os.path.dirname(self.context_file), 'history')
        
        if not os.path.exists(history_base):
            return historical_contexts
        
        # 연도/월 폴더 순회
        for year in sorted(os.listdir(history_base), reverse=True):
            year_path = os.path.join(history_base, year)
            if not os.path.isdir(year_path):
                continue
                
            for month in sorted(os.listdir(year_path), reverse=True):
                month_path = os.path.join(year_path, month)
                if not os.path.isdir(month_path):
                    continue
                
                # context 파일들 읽기
                for filename in sorted(os.listdir(month_path), reverse=True):
                    if filename.startswith('context_') and filename.endswith('.json'):
                        try:
                            filepath = os.path.join(month_path, filename)
                            with open(filepath, 'r', encoding='utf-8') as f:
                                context_data = json.load(f)
                                context_data['filename'] = filename
                                context_data['filepath'] = filepath
                                historical_contexts.append(context_data)
                                
                                if len(historical_contexts) >= limit:
                                    return historical_contexts
                        except Exception as e:
                            self.logger.warning(f"히스토리 파일 읽기 실패 {filename}: {e}")
        
        return historical_contexts
    
    def analyze_historical_performance(self) -> Dict:
        """과거 거래 성과 분석"""
        contexts = self.get_historical_contexts(limit=100)
        
        if not contexts:
            return {
                'total_trades': 0,
                'message': '분석할 거래 기록이 없습니다.'
            }
        
        stats = {
            'total_trades': len(contexts),
            'by_direction': {'LONG': 0, 'SHORT': 0},
            'avg_confidence': 0,
            'scenarios': {}
        }
        
        total_confidence = 0
        
        for context in contexts:
            thesis = context.get('thesis', {})
            direction = thesis.get('direction', 'UNKNOWN')
            confidence = thesis.get('initial_confidence', 50)
            scenario = thesis.get('primary_scenario', 'Unknown')[:50] + '...'
            
            stats['by_direction'][direction] = stats['by_direction'].get(direction, 0) + 1
            total_confidence += confidence
            
            if scenario not in stats['scenarios']:
                stats['scenarios'][scenario] = 0
            stats['scenarios'][scenario] += 1
        
        stats['avg_confidence'] = total_confidence / len(contexts) if contexts else 0
        
        return stats


# 전역 인스턴스
trading_context = TradingContextManager()