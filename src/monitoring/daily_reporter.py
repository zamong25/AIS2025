"""
델파이 트레이딩 시스템 - 일일 성과 리포터
Phase 1: 매일 자동으로 성과 요약을 생성하고 기록
"""

import os
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass
from collections import defaultdict

# 프로젝트 루트를 Python path에 추가
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.logging_config import get_logger
from data.trade_database import get_trade_history, get_trade_details, trade_db
from utils.discord_notifier import DiscordNotifier

@dataclass
class DailyStats:
    """일일 통계 데이터"""
    date: str
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    total_pnl: float
    total_pnl_percent: float
    best_trade: Optional[Dict] = None
    worst_trade: Optional[Dict] = None
    agent_accuracy: Dict = None

class DailyPerformanceReporter:
    """일일 성과 리포터"""
    
    def __init__(self):
        self.logger = get_logger('DailyReporter')
        self.discord = DiscordNotifier()
        
    def generate_daily_summary(self, date: Optional[datetime] = None) -> Dict:
        """
        일일 성과 요약 생성
        
        Args:
            date: 분석할 날짜 (없으면 오늘)
            
        Returns:
            일일 성과 요약 데이터
        """
        if date is None:
            date = datetime.now()
            
        self.logger.info(f"=== 일일 성과 리포트 생성 시작: {date.strftime('%Y-%m-%d')} ===")
        
        # 오늘의 거래 데이터 수집
        today_trades = self._get_today_trades(date)
        
        # 통계 계산
        stats = self._calculate_daily_stats(today_trades, date)
        
        # 에이전트별 정확도 계산
        agent_accuracy = self._calculate_agent_accuracy(today_trades)
        stats.agent_accuracy = agent_accuracy
        
        # 리포트 생성
        report = self._format_report(stats)
        
        # 로그 출력
        self.logger.info(report)
        
        # 파일 저장
        self._save_report(stats, report)
        
        # Discord 알림 (선택적)
        if stats.total_trades > 0:
            self._send_discord_summary(stats)
        
        return {
            'stats': stats,
            'report': report,
            'success': True
        }
    
    def _get_today_trades(self, date: datetime) -> List[Dict]:
        """오늘의 거래 데이터 조회"""
        # 하루의 시작과 끝
        start_of_day = date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)
        
        # 거래 이력 조회
        all_trades = get_trade_history(limit=100)  # 최근 100개
        
        # 오늘 거래만 필터링
        today_trades = []
        for trade in all_trades:
            trade_time = datetime.fromisoformat(trade['timestamp'])
            if start_of_day <= trade_time < end_of_day:
                # 상세 정보 조회
                details = get_trade_details(trade['trade_id'])
                if details:
                    today_trades.append(details)
        
        return today_trades
    
    def _calculate_daily_stats(self, trades: List[Dict], date: datetime) -> DailyStats:
        """일일 통계 계산"""
        stats = DailyStats(
            date=date.strftime('%Y-%m-%d'),
            total_trades=len(trades),
            winning_trades=0,
            losing_trades=0,
            win_rate=0.0,
            total_pnl=0.0,
            total_pnl_percent=0.0
        )
        
        if not trades:
            return stats
        
        # 승패 계산
        for trade in trades:
            pnl = trade.get('realized_pnl', 0)
            pnl_percent = trade.get('realized_pnl_percent', 0)
            
            stats.total_pnl += pnl
            stats.total_pnl_percent += pnl_percent
            
            if pnl > 0:
                stats.winning_trades += 1
                if not stats.best_trade or pnl_percent > stats.best_trade.get('realized_pnl_percent', 0):
                    stats.best_trade = trade
            elif pnl < 0:
                stats.losing_trades += 1
                if not stats.worst_trade or pnl_percent < stats.worst_trade.get('realized_pnl_percent', 0):
                    stats.worst_trade = trade
        
        # 승률 계산
        if stats.total_trades > 0:
            stats.win_rate = (stats.winning_trades / stats.total_trades) * 100
        
        return stats
    
    def _calculate_agent_accuracy(self, trades: List[Dict]) -> Dict[str, float]:
        """에이전트별 예측 정확도 계산"""
        agent_scores = defaultdict(lambda: {'correct': 0, 'total': 0})
        
        for trade in trades:
            # 각 에이전트의 예측과 실제 결과 비교
            analysis = trade.get('analysis', {})
            direction = trade.get('direction', '')
            pnl = trade.get('realized_pnl', 0)
            
            # 거래 성공 여부
            trade_success = (direction == 'BUY' and pnl > 0) or (direction == 'SELL' and pnl < 0)
            
            # 차티스트 정확도
            if 'chartist' in analysis:
                agent_scores['chartist']['total'] += 1
                chartist_signal = analysis['chartist'].get('overall_assessment', {}).get('recommendation', '')
                if (chartist_signal == 'BUY' and direction == 'BUY' and trade_success) or \
                   (chartist_signal == 'SELL' and direction == 'SELL' and trade_success):
                    agent_scores['chartist']['correct'] += 1
            
            # 저널리스트 정확도
            if 'journalist' in analysis:
                agent_scores['journalist']['total'] += 1
                journalist_sentiment = analysis['journalist'].get('sentiment_analysis', {}).get('overall_sentiment', '')
                if (journalist_sentiment == 'BULLISH' and direction == 'BUY' and trade_success) or \
                   (journalist_sentiment == 'BEARISH' and direction == 'SELL' and trade_success):
                    agent_scores['journalist']['correct'] += 1
            
            # 퀀트 정확도
            if 'quant' in analysis:
                agent_scores['quant']['total'] += 1
                quant_score = analysis['quant'].get('quantitative_scorecard', {}).get('overall_score', 0)
                if (quant_score > 0 and direction == 'BUY' and trade_success) or \
                   (quant_score < 0 and direction == 'SELL' and trade_success):
                    agent_scores['quant']['correct'] += 1
        
        # 정확도 계산
        accuracy = {}
        for agent, scores in agent_scores.items():
            if scores['total'] > 0:
                accuracy[agent] = (scores['correct'] / scores['total']) * 100
            else:
                accuracy[agent] = 0.0
        
        return accuracy
    
    def _format_report(self, stats: DailyStats) -> str:
        """리포트 포맷팅"""
        # Outcome 통계 가져오기
        outcome_stats = trade_db.get_outcome_statistics()
        
        report = f"""
📊 일일 성과 요약 ({stats.date})
================================

📈 거래 통계
- 총 거래 횟수: {stats.total_trades}
- 승리: {stats.winning_trades} / 패배: {stats.losing_trades}
- 승률: {stats.win_rate:.1f}%
- 총 수익/손실: ${stats.total_pnl:,.2f} ({stats.total_pnl_percent:+.2f}%)

🏆 최고/최악 거래
"""
        
        if stats.best_trade:
            report += f"- 최고: {stats.best_trade['symbol']} {stats.best_trade['direction']} "
            report += f"(+{stats.best_trade['realized_pnl_percent']:.2f}%)\n"
        
        if stats.worst_trade:
            report += f"- 최악: {stats.worst_trade['symbol']} {stats.worst_trade['direction']} "
            report += f"({stats.worst_trade['realized_pnl_percent']:.2f}%)\n"
        
        report += "\n🤖 에이전트별 정확도\n"
        for agent, accuracy in stats.agent_accuracy.items():
            report += f"- {agent.capitalize()}: {accuracy:.1f}%\n"
        
        # Outcome 분석 추가
        if outcome_stats and outcome_stats.get('outcome_distribution'):
            report += "\n\n🎯 거래 종료 유형 분석\n"
            for outcome, data in outcome_stats['outcome_distribution'].items():
                report += f"- {outcome}: {data['count']}건 ({data['percentage']:.1f}%) | 평균 P&L: {data['avg_pnl']:+.2f}%\n"
            
            # 추천사항
            if outcome_stats.get('recommendations'):
                report += "\n💡 개선 권고사항\n"
                for rec in outcome_stats['recommendations']:
                    report += f"- {rec}\n"
        
        report += "\n================================"
        
        return report
    
    def _save_report(self, stats: DailyStats, report: str):
        """리포트를 파일로 저장"""
        # 리포트 디렉토리
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        report_dir = os.path.join(project_root, 'reports', 'daily')
        os.makedirs(report_dir, exist_ok=True)
        
        # 파일명
        filename = f"daily_report_{stats.date}.json"
        filepath = os.path.join(report_dir, filename)
        
        # 데이터 저장
        data = {
            'date': stats.date,
            'stats': {
                'total_trades': stats.total_trades,
                'winning_trades': stats.winning_trades,
                'losing_trades': stats.losing_trades,
                'win_rate': stats.win_rate,
                'total_pnl': stats.total_pnl,
                'total_pnl_percent': stats.total_pnl_percent,
                'agent_accuracy': stats.agent_accuracy
            },
            'report': report,
            'timestamp': datetime.now().isoformat()
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        self.logger.info(f"일일 리포트 저장: {filepath}")
    
    def _send_discord_summary(self, stats: DailyStats):
        """Discord로 요약 전송"""
        try:
            message = f"📊 **일일 성과 요약** ({stats.date})\n"
            message += f"• 거래: {stats.total_trades}건\n"
            message += f"• 승률: {stats.win_rate:.1f}%\n"
            message += f"• 손익: ${stats.total_pnl:,.2f} ({stats.total_pnl_percent:+.2f}%)"
            
            self.discord.send_notification(message, "일일 성과")
        except Exception as e:
            self.logger.warning(f"Discord 알림 실패: {e}")

# 편의 함수
def generate_daily_report(date: Optional[datetime] = None) -> Dict:
    """일일 리포트 생성 편의 함수"""
    reporter = DailyPerformanceReporter()
    return reporter.generate_daily_summary(date)

if __name__ == "__main__":
    # 테스트 실행
    result = generate_daily_report()
    if result['success']:
        print(result['report'])