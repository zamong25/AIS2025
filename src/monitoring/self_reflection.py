"""
델파이 트레이딩 시스템 - 자기성찰 루프
주기적으로 거래 기록을 분석하여 시스템 개선사항을 제안하는 모듈
"""

import os
import sys
import json
import sqlite3
import logging
import yaml
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

# 프로젝트 루트를 Python 경로에 추가
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from src.utils.time_manager import get_current_time
from src.utils.gemini_client import GeminiClient

@dataclass
class TradeAnalysis:
    """거래 분석 결과"""
    trade_id: str
    entry_date: str
    asset: str
    direction: str
    pnl_usd: float
    pnl_percent: float
    duration_hours: float
    agent_scores: Dict
    market_conditions: Dict
    success: bool
    failure_reason: Optional[str] = None

@dataclass
class PerformanceMetrics:
    """성과 지표"""
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    avg_win: float
    avg_loss: float
    profit_factor: float
    max_drawdown: float
    total_pnl: float
    sharpe_ratio: float

@dataclass
class ImprovementProposal:
    """개선 제안"""
    category: str  # 'entry_rules', 'exit_rules', 'risk_management', 'agent_weights'
    priority: str  # 'high', 'medium', 'low'
    title: str
    description: str
    proposed_changes: Dict
    expected_impact: str
    confidence_score: float  # 0-1
    supporting_evidence: List[str]

class SelfReflectionAgent:
    """자기성찰 에이전트 - 시스템 성과 분석 및 개선 제안"""
    
    def __init__(self, config_path: str = None):
        """
        자기성찰 에이전트 초기화
        Args:
            config_path: 설정 파일 경로
        """
        self.config_path = config_path or os.path.join(project_root, 'config', 'config.yaml')
        self.config = self._load_config()
        self.db_path = os.path.join(project_root, 'data', 'database', 'delphi_trades.db')
        
        # Gemini 클라이언트 초기화
        self.gemini_client = GeminiClient()
        
        # 로깅 설정
        logging.basicConfig(
            level=getattr(logging, self.config.get('system', {}).get('log_level', 'INFO')),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(os.path.join(project_root, 'logs', 'self_reflection.log')),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
        self.logger.info("🤔 델파이 자기성찰 에이전트 초기화 완료")
    
    def _load_config(self) -> Dict:
        """설정 파일 로드"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as file:
                return yaml.safe_load(file)
        except Exception as e:
            print(f"❌ 설정 파일 로드 실패: {e}")
            return {}
    
    def run_weekly_reflection(self, days_to_analyze: int = 7) -> Dict:
        """주간 자기성찰 실행"""
        try:
            self.logger.info(f"🤔 주간 자기성찰 시작 (분석 기간: {days_to_analyze}일)")
            
            # 1. 거래 데이터 수집 및 분석
            trades = self._collect_trade_data(days_to_analyze)
            trade_analyses = self._analyze_individual_trades(trades)
            
            # 2. 성과 지표 계산
            performance_metrics = self._calculate_performance_metrics(trade_analyses)
            
            # 3. 패턴 분석
            pattern_analysis = self._analyze_patterns(trade_analyses)
            
            # 4. 에이전트별 성과 분석
            agent_performance = self._analyze_agent_performance(trade_analyses)
            
            # 5. 시장 조건별 분석
            market_condition_analysis = self._analyze_market_conditions(trade_analyses)
            
            # 6. AI 기반 개선 제안 생성
            improvement_proposals = self._generate_improvement_proposals(
                performance_metrics, pattern_analysis, agent_performance, market_condition_analysis
            )
            
            # 7. 보고서 생성
            reflection_report = self._create_reflection_report(
                days_to_analyze, performance_metrics, pattern_analysis, 
                agent_performance, market_condition_analysis, improvement_proposals
            )
            
            # 8. 보고서 저장
            self._save_reflection_report(reflection_report)
            
            self.logger.info("✅ 주간 자기성찰 완료")
            return reflection_report
            
        except Exception as e:
            self.logger.error(f"❌ 자기성찰 실행 실패: {e}")
            return {'status': 'error', 'error': str(e)}
    
    def _collect_trade_data(self, days: int) -> List[Dict]:
        """거래 데이터 수집"""
        try:
            end_date = get_current_time()
            start_date = end_date - timedelta(days=days)
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            query = """
            SELECT trade_id, entry_timestamp, exit_timestamp, asset, direction, 
                   entry_price, exit_price, quantity, leverage, pnl_usd, pnl_percent,
                   stop_loss_hit, take_profit_hit, max_drawdown, agent_reports
            FROM trades 
            WHERE entry_timestamp >= ?
            ORDER BY entry_timestamp DESC
            """
            
            cursor.execute(query, (start_date.isoformat(),))
            trades_data = cursor.fetchall()
            conn.close()
            
            # 딕셔너리 형태로 변환
            trades = []
            columns = ['trade_id', 'entry_timestamp', 'exit_timestamp', 'asset', 'direction',
                      'entry_price', 'exit_price', 'quantity', 'leverage', 'pnl_usd', 'pnl_percent',
                      'stop_loss_hit', 'take_profit_hit', 'max_drawdown', 'agent_reports']
            
            for trade_data in trades_data:
                trade = dict(zip(columns, trade_data))
                # JSON 문자열인 agent_reports 파싱
                if trade['agent_reports']:
                    try:
                        trade['agent_reports'] = json.loads(trade['agent_reports'])
                    except:
                        trade['agent_reports'] = {}
                trades.append(trade)
            
            self.logger.info(f"📊 {len(trades)}개 거래 데이터 수집 완료 ({days}일간)")
            return trades
            
        except Exception as e:
            self.logger.error(f"❌ 거래 데이터 수집 실패: {e}")
            return []
    
    def _analyze_individual_trades(self, trades: List[Dict]) -> List[TradeAnalysis]:
        """개별 거래 분석"""
        trade_analyses = []
        
        for trade in trades:
            try:
                # 거래 기간 계산
                entry_time = datetime.fromisoformat(trade['entry_timestamp'].replace('Z', '+00:00'))
                exit_time = datetime.fromisoformat(trade['exit_timestamp'].replace('Z', '+00:00')) if trade['exit_timestamp'] else get_current_time()
                duration_hours = (exit_time - entry_time).total_seconds() / 3600
                
                # 에이전트 점수 추출
                agent_reports = trade.get('agent_reports', {})
                agent_scores = {}
                if isinstance(agent_reports, dict):
                    agent_scores = {
                        'chartist': agent_reports.get('chartist', {}).get('technical_score', 0),
                        'journalist': agent_reports.get('journalist', {}).get('sentiment_score', 0),
                        'quant': agent_reports.get('quant', {}).get('expectancy', 0),
                        'stoic': agent_reports.get('stoic', {}).get('risk_score', 0)
                    }
                
                # 성공/실패 판단
                pnl_usd = trade.get('pnl_usd', 0)
                success = pnl_usd > 0
                failure_reason = None
                
                if not success:
                    if trade.get('stop_loss_hit'):
                        failure_reason = 'stop_loss'
                    elif duration_hours > 24:
                        failure_reason = 'timeout'
                    else:
                        failure_reason = 'adverse_movement'
                
                analysis = TradeAnalysis(
                    trade_id=trade['trade_id'],
                    entry_date=trade['entry_timestamp'],
                    asset=trade.get('asset', ''),
                    direction=trade.get('direction', ''),
                    pnl_usd=pnl_usd,
                    pnl_percent=trade.get('pnl_percent', 0),
                    duration_hours=duration_hours,
                    agent_scores=agent_scores,
                    market_conditions={},  # 추후 확장
                    success=success,
                    failure_reason=failure_reason
                )
                
                trade_analyses.append(analysis)
                
            except Exception as e:
                self.logger.warning(f"⚠️ 거래 {trade.get('trade_id', 'unknown')} 분석 실패: {e}")
                continue
        
        return trade_analyses
    
    def _calculate_performance_metrics(self, trades: List[TradeAnalysis]) -> PerformanceMetrics:
        """성과 지표 계산"""
        if not trades:
            return PerformanceMetrics(0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
        
        total_trades = len(trades)
        winning_trades = sum(1 for t in trades if t.success)
        losing_trades = total_trades - winning_trades
        
        win_rate = winning_trades / total_trades if total_trades > 0 else 0
        
        # 평균 수익/손실
        wins = [t.pnl_usd for t in trades if t.success]
        losses = [abs(t.pnl_usd) for t in trades if not t.success]
        
        avg_win = sum(wins) / len(wins) if wins else 0
        avg_loss = sum(losses) / len(losses) if losses else 0
        
        # 수익 팩터
        total_wins = sum(wins)
        total_losses = sum(losses)
        profit_factor = total_wins / total_losses if total_losses > 0 else float('inf')
        
        # 총 수익
        total_pnl = sum(t.pnl_usd for t in trades)
        
        # 최대 낙폭 (단순화)
        cumulative_pnl = 0
        peak_pnl = 0
        max_drawdown = 0
        
        for trade in trades:
            cumulative_pnl += trade.pnl_usd
            peak_pnl = max(peak_pnl, cumulative_pnl)
            drawdown = peak_pnl - cumulative_pnl
            max_drawdown = max(max_drawdown, drawdown)
        
        # 샤프 비율 (단순화)
        pnl_values = [t.pnl_usd for t in trades]
        avg_return = sum(pnl_values) / len(pnl_values) if pnl_values else 0
        
        if len(pnl_values) > 1:
            variance = sum((x - avg_return) ** 2 for x in pnl_values) / (len(pnl_values) - 1)
            std_dev = variance ** 0.5
            sharpe_ratio = avg_return / std_dev if std_dev > 0 else 0
        else:
            sharpe_ratio = 0
        
        return PerformanceMetrics(
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            win_rate=win_rate,
            avg_win=avg_win,
            avg_loss=avg_loss,
            profit_factor=profit_factor,
            max_drawdown=max_drawdown,
            total_pnl=total_pnl,
            sharpe_ratio=sharpe_ratio
        )
    
    def _analyze_patterns(self, trades: List[TradeAnalysis]) -> Dict:
        """패턴 분석"""
        if not trades:
            return {}
        
        # 시간대별 성과
        hourly_performance = {}
        for trade in trades:
            hour = datetime.fromisoformat(trade.entry_date.replace('Z', '+00:00')).hour
            if hour not in hourly_performance:
                hourly_performance[hour] = {'trades': 0, 'wins': 0, 'total_pnl': 0}
            
            hourly_performance[hour]['trades'] += 1
            if trade.success:
                hourly_performance[hour]['wins'] += 1
            hourly_performance[hour]['total_pnl'] += trade.pnl_usd
        
        # 방향별 성과
        direction_performance = {}
        for trade in trades:
            direction = trade.direction
            if direction not in direction_performance:
                direction_performance[direction] = {'trades': 0, 'wins': 0, 'total_pnl': 0}
            
            direction_performance[direction]['trades'] += 1
            if trade.success:
                direction_performance[direction]['wins'] += 1
            direction_performance[direction]['total_pnl'] += trade.pnl_usd
        
        # 거래 기간별 성과
        duration_buckets = {'<1h': [], '1-4h': [], '4-12h': [], '12-24h': [], '>24h': []}
        for trade in trades:
            if trade.duration_hours < 1:
                duration_buckets['<1h'].append(trade)
            elif trade.duration_hours < 4:
                duration_buckets['1-4h'].append(trade)
            elif trade.duration_hours < 12:
                duration_buckets['4-12h'].append(trade)
            elif trade.duration_hours < 24:
                duration_buckets['12-24h'].append(trade)
            else:
                duration_buckets['>24h'].append(trade)
        
        duration_performance = {}
        for bucket, bucket_trades in duration_buckets.items():
            if bucket_trades:
                wins = sum(1 for t in bucket_trades if t.success)
                total_pnl = sum(t.pnl_usd for t in bucket_trades)
                duration_performance[bucket] = {
                    'trades': len(bucket_trades),
                    'wins': wins,
                    'win_rate': wins / len(bucket_trades),
                    'total_pnl': total_pnl
                }
        
        return {
            'hourly_performance': hourly_performance,
            'direction_performance': direction_performance,
            'duration_performance': duration_performance
        }
    
    def _analyze_agent_performance(self, trades: List[TradeAnalysis]) -> Dict:
        """에이전트별 성과 분석"""
        agent_analysis = {
            'chartist': {'high_confidence_trades': [], 'low_confidence_trades': []},
            'journalist': {'high_confidence_trades': [], 'low_confidence_trades': []},
            'quant': {'high_confidence_trades': [], 'low_confidence_trades': []},
            'stoic': {'high_confidence_trades': [], 'low_confidence_trades': []}
        }
        
        for trade in trades:
            for agent, score in trade.agent_scores.items():
                if agent in agent_analysis:
                    if isinstance(score, (int, float)):
                        if score >= 70:  # 높은 신뢰도
                            agent_analysis[agent]['high_confidence_trades'].append(trade)
                        elif score <= 30:  # 낮은 신뢰도
                            agent_analysis[agent]['low_confidence_trades'].append(trade)
        
        # 각 에이전트의 예측 정확도 계산
        agent_performance = {}
        for agent, data in agent_analysis.items():
            high_conf_trades = data['high_confidence_trades']
            low_conf_trades = data['low_confidence_trades']
            
            # 높은 신뢰도 거래의 성공률
            high_conf_wins = sum(1 for t in high_conf_trades if t.success)
            high_conf_win_rate = high_conf_wins / len(high_conf_trades) if high_conf_trades else 0
            
            # 낮은 신뢰도 거래의 성공률 (이론적으로 낮아야 함)
            low_conf_wins = sum(1 for t in low_conf_trades if t.success)
            low_conf_win_rate = low_conf_wins / len(low_conf_trades) if low_conf_trades else 0
            
            agent_performance[agent] = {
                'high_confidence_win_rate': high_conf_win_rate,
                'high_confidence_trades': len(high_conf_trades),
                'low_confidence_win_rate': low_conf_win_rate,
                'low_confidence_trades': len(low_conf_trades),
                'prediction_accuracy': high_conf_win_rate - low_conf_win_rate  # 차이가 클수록 좋음
            }
        
        return agent_performance
    
    def _analyze_market_conditions(self, trades: List[TradeAnalysis]) -> Dict:
        """시장 조건별 분석 (추후 확장)"""
        # 현재는 단순한 분석, 향후 시장 데이터와 연계 확장 예정
        return {
            'volatility_analysis': 'Not implemented yet',
            'trend_analysis': 'Not implemented yet',
            'correlation_analysis': 'Not implemented yet'
        }
    
    def _generate_improvement_proposals(self, performance: PerformanceMetrics, 
                                     patterns: Dict, agent_perf: Dict, 
                                     market_analysis: Dict) -> List[ImprovementProposal]:
        """AI 기반 개선 제안 생성"""
        proposals = []
        
        try:
            # AI에게 분석 데이터를 제공하고 개선안 요청
            analysis_data = {
                'performance_metrics': {
                    'total_trades': performance.total_trades,
                    'win_rate': performance.win_rate,
                    'profit_factor': performance.profit_factor,
                    'avg_win': performance.avg_win,
                    'avg_loss': performance.avg_loss,
                    'max_drawdown': performance.max_drawdown,
                    'total_pnl': performance.total_pnl,
                    'sharpe_ratio': performance.sharpe_ratio
                },
                'patterns': patterns,
                'agent_performance': agent_perf
            }
            
            prompt = f"""
델파이 트레이딩 시스템의 성과 분석 데이터를 바탕으로 구체적인 개선 제안을 해주세요.

## 분석 데이터:
{json.dumps(analysis_data, indent=2, ensure_ascii=False)}

## 개선 제안 요청:
다음 카테고리별로 개선 제안을 작성해주세요:

1. entry_rules (진입 규칙)
2. exit_rules (청산 규칙) 
3. risk_management (리스크 관리)
4. agent_weights (에이전트 가중치)

각 제안은 다음 형식으로 작성해주세요:
- 제목: 간단한 제안 제목
- 설명: 상세한 개선 방안
- 우선순위: high/medium/low
- 예상 효과: 구체적인 개선 효과
- 신뢰도: 0.0-1.0 점수
- 근거: 분석 데이터에서 도출된 근거

JSON 형식으로 응답해주세요.
"""
            
            response = self.gemini_client.generate_content_with_retry(prompt)
            
            if response and 'text' in response:
                try:
                    # JSON 응답 파싱
                    ai_proposals = json.loads(response['text'])
                    
                    # ImprovementProposal 객체로 변환
                    for proposal_data in ai_proposals.get('proposals', []):
                        proposal = ImprovementProposal(
                            category=proposal_data.get('category', 'general'),
                            priority=proposal_data.get('priority', 'medium'),
                            title=proposal_data.get('title', ''),
                            description=proposal_data.get('description', ''),
                            proposed_changes=proposal_data.get('proposed_changes', {}),
                            expected_impact=proposal_data.get('expected_impact', ''),
                            confidence_score=proposal_data.get('confidence_score', 0.5),
                            supporting_evidence=proposal_data.get('supporting_evidence', [])
                        )
                        proposals.append(proposal)
                
                except json.JSONDecodeError:
                    self.logger.warning("⚠️ AI 응답 JSON 파싱 실패 - 기본 제안 생성")
                    proposals = self._generate_default_proposals(performance, patterns, agent_perf)
            
        except Exception as e:
            self.logger.error(f"❌ AI 개선 제안 생성 실패: {e}")
            proposals = self._generate_default_proposals(performance, patterns, agent_perf)
        
        return proposals
    
    def _generate_default_proposals(self, performance: PerformanceMetrics,
                                  patterns: Dict, agent_perf: Dict) -> List[ImprovementProposal]:
        """기본 개선 제안 생성 (AI 실패시 사용)"""
        proposals = []
        
        # 승률 기반 제안
        if performance.win_rate < 0.5:
            proposals.append(ImprovementProposal(
                category='entry_rules',
                priority='high',
                title='진입 기준 강화',
                description=f'현재 승률 {performance.win_rate:.2%}로 낮음. 진입 기준을 더 엄격하게 적용 필요',
                proposed_changes={'min_agent_consensus': 3, 'min_confidence_threshold': 70},
                expected_impact='승률 10-15% 향상 예상',
                confidence_score=0.8,
                supporting_evidence=[f'승률 {performance.win_rate:.2%}', '거래 빈도 vs 품질 트레이드오프']
            ))
        
        # 리스크 관리 제안
        if performance.max_drawdown > 100:  # $100 초과
            proposals.append(ImprovementProposal(
                category='risk_management',
                priority='high', 
                title='최대 낙폭 제한 강화',
                description=f'최대 낙폭 ${performance.max_drawdown:.2f} 과도함. 포지션 크기 축소 필요',
                proposed_changes={'max_position_size_percent': 2, 'daily_loss_limit_percent': 3},
                expected_impact='낙폭 50% 감소',
                confidence_score=0.9,
                supporting_evidence=[f'최대낙폭 ${performance.max_drawdown:.2f}']
            ))
        
        return proposals
    
    def _create_reflection_report(self, days_analyzed: int, performance: PerformanceMetrics,
                                patterns: Dict, agent_perf: Dict, market_analysis: Dict,
                                proposals: List[ImprovementProposal]) -> Dict:
        """자기성찰 보고서 생성"""
        return {
            'report_metadata': {
                'generated_at': get_current_time().isoformat(),
                'analysis_period_days': days_analyzed,
                'report_type': 'weekly_reflection',
                'version': '1.0'
            },
            'performance_summary': {
                'total_trades': performance.total_trades,
                'win_rate': performance.win_rate,
                'profit_factor': performance.profit_factor,
                'total_pnl_usd': performance.total_pnl,
                'max_drawdown_usd': performance.max_drawdown,
                'sharpe_ratio': performance.sharpe_ratio,
                'avg_win_usd': performance.avg_win,
                'avg_loss_usd': performance.avg_loss
            },
            'pattern_analysis': patterns,
            'agent_performance': agent_perf,
            'market_conditions': market_analysis,
            'improvement_proposals': [
                {
                    'category': p.category,
                    'priority': p.priority,
                    'title': p.title,
                    'description': p.description,
                    'proposed_changes': p.proposed_changes,
                    'expected_impact': p.expected_impact,
                    'confidence_score': p.confidence_score,
                    'supporting_evidence': p.supporting_evidence
                } for p in proposals
            ],
            'recommendations': {
                'immediate_actions': [p.title for p in proposals if p.priority == 'high'],
                'monitoring_focus': ['승률 추이', '에이전트 신뢰도', '리스크 관리 효과'],
                'next_review_date': (get_current_time() + timedelta(days=7)).isoformat()
            }
        }
    
    def _save_reflection_report(self, report: Dict):
        """자기성찰 보고서 저장"""
        try:
            # 보고서 저장 경로
            reports_dir = os.path.join(project_root, 'data', 'reports')
            os.makedirs(reports_dir, exist_ok=True)
            
            timestamp = get_current_time().strftime('%Y%m%d_%H%M%S')
            report_file = os.path.join(reports_dir, f'reflection_report_{timestamp}.json')
            
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"📄 자기성찰 보고서 저장 완료: {report_file}")
            
            # 최신 보고서 링크 생성
            latest_report_file = os.path.join(reports_dir, 'latest_reflection_report.json')
            with open(latest_report_file, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            
        except Exception as e:
            self.logger.error(f"❌ 보고서 저장 실패: {e}")


def run_weekly_reflection():
    """주간 자기성찰 실행 (스크립트 실행용)"""
    agent = SelfReflectionAgent()
    report = agent.run_weekly_reflection()
    
    if 'status' in report and report['status'] == 'error':
        print(f"❌ 자기성찰 실패: {report['error']}")
        return False
    
    print("✅ 주간 자기성찰 완료")
    print(f"📊 분석 거래 수: {report['performance_summary']['total_trades']}")
    print(f"📈 승률: {report['performance_summary']['win_rate']:.2%}")
    print(f"💰 총 수익: ${report['performance_summary']['total_pnl_usd']:.2f}")
    print(f"🎯 개선 제안: {len(report['improvement_proposals'])}개")
    
    # 높은 우선순위 제안 출력
    high_priority = [p for p in report['improvement_proposals'] if p['priority'] == 'high']
    if high_priority:
        print("\n🚨 즉시 조치 필요:")
        for proposal in high_priority:
            print(f"  • {proposal['title']}")
    
    return True


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="델파이 트레이딩 시스템 자기성찰 에이전트")
    parser.add_argument('--days', type=int, default=7,
                       help='분석할 기간 (일수)')
    
    args = parser.parse_args()
    
    success = run_weekly_reflection()
    exit(0 if success else 1)