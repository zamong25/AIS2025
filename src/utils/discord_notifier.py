"""
델파이 트레이딩 시스템 - Discord 알림 모듈
웹훅을 통한 실시간 Discord 알림 발송
"""

import os
import sys
import json
import requests
import logging
from datetime import datetime
from typing import Dict, Optional

# 프로젝트 루트를 Python 경로에 추가
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from src.utils.time_manager import TimeManager

class DiscordNotifier:
    """Discord 웹훅을 통한 알림 발송 클래스"""
    
    def __init__(self, webhook_url: str = None):
        """
        Discord 알림기 초기화
        Args:
            webhook_url: Discord 웹훅 URL
        """
        self.webhook_url = webhook_url or "https://discord.com/api/webhooks/1388683858777608294/xF7szKa8vNtyng7VOxmOrd-QF3mtJPJxPSShY4JIM2RX6ZEM9TfEegFQvLWWrJkxfUfx"
        self.logger = logging.getLogger(__name__)
        
        # 발송 성공 확인
        if self.webhook_url:
            self.logger.info("💬 Discord 알림 시스템 초기화 완료")
        else:
            self.logger.warning("⚠️ Discord 웹훅 URL이 설정되지 않음")
    
    def send_alert(self, title: str, message: str, level: str = "info") -> bool:
        """
        Discord 알림 발송
        Args:
            title: 알림 제목
            message: 알림 내용
            level: 알림 레벨 (info, warning, error, critical)
        Returns:
            발송 성공 여부
        """
        try:
            # 레벨별 색상 및 아이콘 설정
            level_config = {
                "info": {"color": 0x3498db, "icon": "ℹ️"},       # 파란색
                "warning": {"color": 0xf39c12, "icon": "⚠️"},   # 주황색
                "error": {"color": 0xe74c3c, "icon": "❌"},     # 빨간색
                "critical": {"color": 0x8b0000, "icon": "🚨"}   # 진한 빨간색
            }
            
            config = level_config.get(level, level_config["info"])
            
            # Discord 임베드 메시지 구성
            embed = {
                "title": f"{config['icon']} {title}",
                "description": message,
                "color": config["color"],
                "timestamp": TimeManager.utc_now().isoformat(),
                "footer": {
                    "text": "델파이 트레이딩 시스템",
                    "icon_url": "https://cdn.discordapp.com/emojis/845751449222578176.png"
                },
                "fields": [
                    {
                        "name": "📅 발생 시간",
                        "value": TimeManager.utc_now().strftime('%Y-%m-%d %H:%M:%S UTC'),
                        "inline": True
                    },
                    {
                        "name": "🏛️ 시스템",
                        "value": "Project Delphi",
                        "inline": True
                    }
                ]
            }
            
            # 웹훅 요청 데이터
            data = {
                "username": "델파이 알림봇",
                "avatar_url": "https://cdn.discordapp.com/emojis/845751449222578176.png",
                "embeds": [embed]
            }
            
            # Discord 웹훅으로 전송
            response = requests.post(
                self.webhook_url,
                json=data,
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            
            if response.status_code == 204:  # Discord 성공 응답
                self.logger.info(f"💬 Discord 알림 발송 성공: {title}")
                return True
            else:
                self.logger.error(f"❌ Discord 알림 발송 실패: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Discord 알림 발송 예외: {e}")
            return False
    
    def send_heartbeat_alert(self, risk_assessment: Dict, emergency_action: Dict) -> bool:
        """심장박동 체크 알림 전용"""
        try:
            risk_level = risk_assessment.get('risk_level', 'unknown')
            action = emergency_action.get('action', 'none')
            
            # 제목 구성
            if action == 'emergency_close':
                title = "🚨 긴급 청산 실행됨"
                level = "critical"
            elif action == 'emergency_close_failed':
                title = "💥 긴급 청산 실패"
                level = "critical"
            elif risk_level == 'critical':
                title = "🆘 위험도 CRITICAL"
                level = "critical"
            elif risk_level == 'high':
                title = "⚠️ 위험도 HIGH"
                level = "error"
            else:
                title = "📊 심장박동 체크 경고"
                level = "warning"
            
            # 메시지 구성
            message = f"**위험도**: {risk_level.upper()}\n"
            message += f"**위험 점수**: {risk_assessment.get('risk_score', 0)}/100\n\n"
            
            if risk_assessment.get('risk_factors'):
                message += "**🔍 위험 요인:**\n"
                for factor in risk_assessment['risk_factors'][:5]:  # 최대 5개만
                    message += f"• {factor}\n"
                message += "\n"
            
            message += f"**🎯 조치 사항**: {action}\n"
            if emergency_action.get('reason'):
                message += f"**📝 조치 이유**: {emergency_action['reason']}\n"
            
            if emergency_action.get('result'):
                result = emergency_action['result']
                if result.get('status') == 'emergency_closed':
                    message += f"\n✅ **긴급 청산 완료** (주문 ID: {result.get('order_id', 'N/A')})"
                elif 'error' in result:
                    message += f"\n❌ **긴급 청산 실패**: {result.get('error', 'Unknown error')}"
            
            return self.send_alert(title, message, level)
            
        except Exception as e:
            self.logger.error(f"❌ 심장박동 알림 생성 실패: {e}")
            return False
    
    def send_synthesizer_decision(self, playbook: Dict, agent_reports: Dict) -> bool:
        """신디사이저 거래 판단 알림"""
        try:
            # 신디사이저가 'action' 필드를 사용하므로 먼저 확인
            final_decision = playbook.get('final_decision', {})
            
            # 디버깅 로그 추가
            self.logger.debug(f"📋 Playbook keys: {list(playbook.keys())}")
            self.logger.debug(f"📋 Final decision keys: {list(final_decision.keys())}")
            self.logger.debug(f"📋 Final decision content: {final_decision}")
            
            decision = final_decision.get('action') or final_decision.get('decision', 'UNKNOWN')
            
            # 하락/매도 시나리오도 SELL로 매핑
            if decision == 'UNKNOWN' and final_decision.get('recommended_scenario') == '하락':
                decision = 'SELL'
                self.logger.debug("📋 Mapped '하락' scenario to SELL decision")
                
            rationale = final_decision.get('rationale', 'N/A')
            
            # 더 자세한 로깅
            self.logger.info(f"📋 Discord 알림 - 최종 결정: {decision}")
            if decision == 'UNKNOWN':
                self.logger.warning(f"⚠️ UNKNOWN 결정 감지 - final_decision 내용: {final_decision}")
            
            # 결정별 색상 및 아이콘 설정
            if decision == "BUY" or decision == "LONG":
                title = "🟢 신디사이저 결정: 매수"
                level = "info"
                color = 0x00ff00  # 녹색
            elif decision == "SELL" or decision == "SHORT":
                title = "🔴 신디사이저 결정: 매도"
                level = "warning"
                color = 0xff0000  # 빨간색
            elif decision == "ADJUST_STOP":
                title = "🛡️ 신디사이저 결정: 손절가 조정"
                level = "info"
                color = 0xff8c00  # 주황색
            elif decision == "CLOSE_POSITION":
                title = "🚪 신디사이저 결정: 포지션 청산"
                level = "warning"
                color = 0xffa500  # 오렌지색
            else:  # HOLD, HOLD_POSITION
                title = "⚪ 신디사이저 결정: 관망"
                level = "info"
                color = 0x808080  # 회색
            
            # 실행 계획 정보 추출 (V1, V2 호환)
            execution_plan = playbook.get('execution_plan', {})
            
            # V2 형식 체크 (직접적인 필드 접근)
            has_v2_format = 'entry_price' in execution_plan or 'stop_loss' in execution_plan
            
            message = f"**🎯 최종 결정**: {decision}\n\n"
            message += f"**📝 판단 근거**:\n{rationale}\n\n"
            
            # HOLD 결정 시 현재 포지션 정보 추가
            if decision in ["HOLD", "HOLD_POSITION"]:
                position_check = playbook.get('position_check', {})
                if position_check.get('has_position'):
                    message += f"**📊 현재 포지션**:\n"
                    message += f"• 방향: {position_check.get('current_position', 'N/A')}\n"
                    message += f"• 손익: {position_check.get('pnl_percent', 0):.2f}%\n\n"
            
            if decision in ["BUY", "SELL"]:
                message += f"**📊 거래 계획**:\n"
                
                if has_v2_format:
                    # V2 형식 처리
                    direction = execution_plan.get('trade_direction', 'LONG' if decision == 'BUY' else 'SHORT')
                    message += f"• 방향: {direction}\n"
                    message += f"• 진입가: ${execution_plan.get('entry_price', 'N/A')}\n"
                    message += f"• 손절가: ${execution_plan.get('stop_loss', 'N/A')}\n"
                    message += f"• 익절가: ${execution_plan.get('take_profit_1', 'N/A')}\n"
                    message += f"• 레버리지: {execution_plan.get('leverage', 'N/A')}x\n"
                    message += f"• 자본 비율: {execution_plan.get('position_size_percent', 'N/A')}%\n\n"
                else:
                    # V1 형식 처리 (기존 코드)
                    entry_strategy = execution_plan.get('entry_strategy', {})
                    risk_management = execution_plan.get('risk_management', {})
                    message += f"• 방향: {execution_plan.get('trade_direction', 'N/A')}\n"
                    message += f"• 진입가: {entry_strategy.get('price_range', 'N/A')}\n"
                    message += f"• 손절가: ${risk_management.get('stop_loss_price', 'N/A')}\n"
                    message += f"• 익절가: ${risk_management.get('take_profit_1_price', 'N/A')}\n"
                    message += f"• 레버리지: {execution_plan.get('position_sizing', {}).get('leverage', 'N/A')}x\n"
                    message += f"• 자본 비율: {execution_plan.get('position_sizing', {}).get('percent_of_capital', 'N/A')}%\n\n"
            
            # 에이전트별 핵심 정보 요약
            message += f"**🤖 에이전트 분석 요약**:\n"
            
            # 차티스트: 가장 높은 확률의 시나리오 표시
            chartist = agent_reports.get('chartist', {})
            if chartist and chartist.get('scenarios'):
                scenarios = chartist['scenarios']
                best_scenario = max(scenarios, key=lambda x: x.get('probability', 0))
                message += f"• 차티스트: {best_scenario.get('type', 'N/A')} {best_scenario.get('probability', 0)}%\n"
            
            # 저널리스트: 가장 높은 영향도의 뉴스
            journalist = agent_reports.get('journalist', {})
            if journalist:
                all_news = journalist.get('short_term_news', []) + journalist.get('long_term_news', [])
                if all_news:
                    max_impact = max((news.get('impact_level', 0) for news in all_news), default=0)
                    message += f"• 저널리스트: 최대 영향도 {max_impact}/10\n"
                else:
                    message += f"• 저널리스트: 뉴스 없음\n"
            
            # 퀀트: 전체 점수 또는 신뢰도
            quant = agent_reports.get('quant', {})
            if quant:
                # 기존 퀀트 (quantitative_scorecard 있는 경우)
                if 'quantitative_scorecard' in quant:
                    overall_score = quant['quantitative_scorecard'].get('overall_score', 'N/A')
                    if overall_score == 'N/A':
                        overall_score = quant['quantitative_scorecard'].get('overall_quant_score', 'N/A')
                    message += f"• 퀀트: 점수 {overall_score}/100\n"
                # 퀀트 v3 (integrated_analysis 있는 경우)
                elif 'integrated_analysis' in quant:
                    # 시나리오별 verdict 확인
                    scenarios = quant['integrated_analysis'].get('scenario_technical_view', {})
                    if scenarios:
                        verdicts = []
                        for scenario, data in scenarios.items():
                            verdict = data.get('verdict', '')
                            if '지지' in verdict:
                                verdicts.append(f"{scenario}:{verdict}")
                        if verdicts:
                            message += f"• 퀀트: {', '.join(verdicts[:2])}\n"
                        else:
                            message += f"• 퀀트: 분석 중\n"
                    else:
                        message += f"• 퀀트: 데이터 없음\n"
                else:
                    message += f"• 퀀트: N/A\n"
            else:
                message += f"• 퀀트: N/A\n"
            
            # 스토익: 리스크 레벨
            stoic = agent_reports.get('stoic', {})
            if stoic:
                # market_risk_state에서 overall_risk 찾기
                market_risk_state = stoic.get('market_risk_state', {})
                if market_risk_state:
                    risk_level = market_risk_state.get('overall_risk', 'N/A')
                    # 영어를 이모지로 변환
                    risk_emoji = {'LOW': '🟢', 'MODERATE': '🟡', 'HIGH': '🔴'}.get(risk_level, '⚪')
                    message += f"• 스토익: {risk_emoji} {risk_level} 리스크\n"
                else:
                    message += f"• 스토익: N/A\n"
            else:
                message += f"• 스토익: N/A\n"
            
            # 트리거 정보 추가 (HOLD, ADJUST_STOP 등에서)
            trigger_setup = playbook.get('trigger_setup', {})
            if trigger_setup and trigger_setup.get('trigger_price', 0) > 0:
                message += f"\n**🎯 설정된 트리거**:\n"
                trigger_price = trigger_setup.get('trigger_price', 'N/A')
                trigger_direction = trigger_setup.get('direction', 'UNKNOWN')
                trigger_reason = trigger_setup.get('reason', trigger_setup.get('condition', ''))
                
                direction_emoji = "🟢" if trigger_direction == "LONG" else "🔴" if trigger_direction == "SHORT" else "⚪"
                message += f"• {direction_emoji} {trigger_direction}: ${trigger_price}\n"
                if trigger_reason:
                    message += f"• 조건: {trigger_reason}\n"
                message += f"\n💡 **트리거 작동**: 해당 가격에 도달하면 자동으로 재분석이 실행됩니다.\n"
            
            # 구형 트리거 정보도 확인 (backward compatibility)
            elif decision == "HOLD":
                contingency_plan = playbook.get('contingency_plan', {}).get('if_hold_is_decided', {})
                price_triggers = contingency_plan.get('price_triggers', [])
                
                if price_triggers:
                    message += f"\n**🎯 설정된 가격 트리거**:\n"
                    for trigger in price_triggers:
                        direction = trigger.get('direction', 'UNKNOWN')
                        price = trigger.get('price', 'N/A')
                        confidence = trigger.get('confidence', 'N/A')
                        
                        direction_emoji = "🟢" if direction == "LONG" else "🔴" if direction == "SHORT" else "⚪"
                        message += f"• {direction_emoji} {direction}: ${price} (신뢰도: {confidence}%)\n"
                    
                    message += f"\n💡 **트리거 작동 방식**: 위 가격에 도달하면 자동으로 시스템이 재분석을 실행합니다.\n"
            
            # ADJUST_STOP의 경우 조정된 손절가 정보
            if decision == "ADJUST_STOP":
                stop_loss = execution_plan.get('stop_loss', 'N/A')
                message += f"\n**🛡️ 손절가 조정**: ${stop_loss}\n"
            
            # 커스텀 임베드로 전송
            embed = {
                "title": title,
                "description": message,
                "color": color,
                "timestamp": TimeManager.utc_now().isoformat(),
                "footer": {
                    "text": "델파이 신디사이저 (솔론)",
                    "icon_url": "https://cdn.discordapp.com/emojis/845751449222578176.png"
                },
                "fields": [
                    {
                        "name": "📅 분석 시간",
                        "value": TimeManager.utc_now().strftime('%Y-%m-%d %H:%M:%S UTC'),
                        "inline": True
                    },
                    {
                        "name": "⚖️ 신디사이저",
                        "value": "솔론 (Solon)",
                        "inline": True
                    }
                ]
            }
            
            data = {
                "username": "델파이 신디사이저",
                "avatar_url": "https://cdn.discordapp.com/emojis/845751449222578176.png",
                "embeds": [embed]
            }
            
            response = requests.post(
                self.webhook_url,
                json=data,
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            
            if response.status_code == 204:
                self.logger.info(f"💬 신디사이저 결정 알림 발송 성공: {decision} (제목: {title})")
                return True
            else:
                self.logger.error(f"❌ 신디사이저 결정 알림 발송 실패: {response.status_code}")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ 신디사이저 결정 알림 생성 실패: {e}")
            return False

    def send_trigger_activation(self, trigger_info: Dict, current_price: float) -> bool:
        """트리거 발동 알림"""
        try:
            trigger_id = trigger_info.get('trigger_id', 'UNKNOWN')
            direction = trigger_info.get('direction', 'UNKNOWN')
            target_price = trigger_info.get('price', 'N/A')
            rationale = trigger_info.get('rationale', 'N/A')
            confidence = trigger_info.get('confidence', 'N/A')
            
            # 방향별 색상 및 아이콘 설정
            if direction == "LONG":
                title = "🟢 트리거 발동: 매수 신호"
                color = 0x00ff00  # 녹색
                emoji = "🟢"
            elif direction == "SHORT":
                title = "🔴 트리거 발동: 매도 신호"
                color = 0xff0000  # 빨간색
                emoji = "🔴"
            else:
                title = "⚪ 트리거 발동"
                color = 0x808080  # 회색
                emoji = "⚪"
            
            message = f"**🎯 트리거 ID**: {trigger_id}\n"
            message += f"**{emoji} 방향**: {direction}\n"
            message += f"**💰 목표가**: ${target_price}\n"
            message += f"**📊 현재가**: ${current_price:.2f}\n"
            message += f"**🎲 신뢰도**: {confidence}%\n\n"
            message += f"**📝 발동 근거**:\n{rationale}\n\n"
            message += f"🔄 **시스템이 자동으로 재분석을 시작합니다...**"
            
            embed = {
                "title": title,
                "description": message,
                "color": color,
                "timestamp": TimeManager.utc_now().isoformat(),
                "footer": {
                    "text": "델파이 트리거 시스템",
                    "icon_url": "https://cdn.discordapp.com/emojis/845751449222578176.png"
                },
                "fields": [
                    {
                        "name": "⏰ 발동 시간",
                        "value": TimeManager.utc_now().strftime('%Y-%m-%d %H:%M:%S UTC'),
                        "inline": True
                    },
                    {
                        "name": "📈 자산",
                        "value": "SOL/USDT",
                        "inline": True
                    }
                ]
            }
            
            data = {
                "username": "델파이 트리거 시스템",
                "avatar_url": "https://cdn.discordapp.com/emojis/845751449222578176.png",
                "embeds": [embed]
            }
            
            response = requests.post(
                self.webhook_url,
                json=data,
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            
            if response.status_code == 204:
                self.logger.info(f"💬 트리거 발동 알림 발송 성공: {trigger_id}")
                return True
            else:
                self.logger.error(f"❌ 트리거 발동 알림 발송 실패: {response.status_code}")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ 트리거 발동 알림 생성 실패: {e}")
            return False

    def send_trade_alert(self, trade_info: Dict, alert_type: str = "execution") -> bool:
        """거래 관련 알림"""
        try:
            if alert_type == "execution":
                # 거래 방향에 따른 이모지와 색상 설정
                direction = trade_info.get('direction', 'N/A')
                if direction == "LONG":
                    title = "🟢 롱 포지션 진입"
                    color = 0x00ff00  # 녹색
                elif direction == "SHORT":
                    title = "🔴 숏 포지션 진입"
                    color = 0xff0000  # 빨간색
                else:
                    title = "💸 거래 실행"
                    color = 0x3498db  # 파란색
                
                # 탐험 모드 표시 제거됨 (더 이상 사용하지 않음)
                
                message = f"""
**📊 거래 정보**
• 방향: {direction}
• 심볼: {trade_info.get('symbol', 'N/A')}
• 진입가: ${trade_info.get('entry_price', 0):.2f}
• 수량: {trade_info.get('quantity', 0):.4f} {trade_info.get('symbol', '').replace('USDT', '')}
• 레버리지: {trade_info.get('leverage', 1)}x
• 포지션 크기: ${trade_info.get('position_value', 0):.2f} ({trade_info.get('position_size_percent', 0):.1f}%)

**🛡️ 리스크 관리**
• 손절가: ${trade_info.get('stop_loss', 0):.2f} ({trade_info.get('stop_loss_percent', 0):.2f}%)
• 익절가 1: ${trade_info.get('take_profit_1', 0):.2f} ({trade_info.get('take_profit_1_percent', 0):.2f}%)
• 익절가 2: ${trade_info.get('take_profit_2', 0):.2f} ({trade_info.get('take_profit_2_percent', 0):.2f}%)
• 최대 손실: ${trade_info.get('max_loss_usd', 0):.2f}

**📝 거래 ID**: {trade_info.get('trade_id', 'N/A')}
"""
                
            elif alert_type == "position_adjusted":
                # 포지션 크기 조정 알림
                title = f"📈 포지션 크기 조정: {trade_info.get('symbol', 'N/A')}"
                color = 0x00bfff  # 하늘색
                
                message = f"""
**📊 조정 내역**
• 방향: {trade_info.get('direction', 'N/A')}
• 기존 크기: {trade_info.get('original_size', 0):.4f}
• 새로운 크기: {trade_info.get('new_size', 0):.4f} (+{trade_info.get('additional_size', 0):.4f})
• 새 평균가: ${trade_info.get('new_avg_price', 0):.2f}

**🛡️ 리스크 관리**
• 새 손절가: ${trade_info.get('new_stop_loss', 0):.2f} (무손실 보장)
• 현재 수익률: +{trade_info.get('current_pnl_percent', 0):.2f}%

**📝 조정 사유**
{trade_info.get('rationale', 'N/A')}
"""
            
            elif alert_type == "position_closed":
                pnl_usd = trade_info.get('pnl_usd', 0)
                pnl_percent = trade_info.get('pnl_percent', 0)
                
                # 손익에 따른 제목과 색상
                if pnl_usd > 0:
                    title = f"💰 수익 실현 (+{pnl_percent:.2f}%)"
                    color = 0x00ff00  # 녹색
                else:
                    title = f"💸 손실 확정 ({pnl_percent:.2f}%)"
                    color = 0xff0000  # 빨간색
                
                message = f"""
**📊 포지션 요약**
• 방향: {trade_info.get('direction', 'N/A')}
• 심볼: {trade_info.get('symbol', 'N/A')}
• 진입가: ${trade_info.get('entry_price', 0):.2f}
• 청산가: ${trade_info.get('exit_price', 0):.2f}
• 수량: {trade_info.get('quantity', 0):.4f}

**💵 손익 정보**
• 실현 손익: ${pnl_usd:.2f} ({pnl_percent:+.2f}%)
• 종료 사유: {trade_info.get('exit_reason', 'N/A')}
• 거래 시간: {trade_info.get('duration', 'N/A')}
• 레버리지: {trade_info.get('leverage', 1)}x

**📈 거래 성과**
• 최대 상승: {trade_info.get('max_profit_percent', 0):+.2f}%
• 최대 하락: {trade_info.get('max_drawdown_percent', 0):+.2f}%

**📝 거래 ID**: {trade_info.get('trade_id', 'N/A')}
"""
            
            # 커스텀 임베드로 전송
            embed = {
                "title": title,
                "description": message,
                "color": color,
                "timestamp": TimeManager.utc_now().isoformat(),
                "footer": {
                    "text": "델파이 트레이딩 시스템",
                    "icon_url": "https://cdn.discordapp.com/emojis/845751449222578176.png"
                }
            }
            
            data = {
                "username": "델파이 거래 알림",
                "avatar_url": "https://cdn.discordapp.com/emojis/845751449222578176.png",
                "embeds": [embed]
            }
            
            response = requests.post(
                self.webhook_url,
                json=data,
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            
            if response.status_code == 204:
                self.logger.info(f"💬 거래 알림 발송 성공: {alert_type}")
                return True
            else:
                self.logger.error(f"❌ 거래 알림 발송 실패: {response.status_code}")
                return False
            
        except Exception as e:
            self.logger.error(f"❌ 거래 알림 생성 실패: {e}")
            return False
    
    def send_system_alert(self, message: str, level: str = "info") -> bool:
        """일반 시스템 알림"""
        return self.send_alert("🤖 시스템 알림", message, level)
    
    def send_test_alert(self) -> bool:
        """테스트 알림 발송"""
        test_message = f"""
🧪 **테스트 알림입니다**

시스템이 정상적으로 작동하고 있습니다.
- 현재 시간: {TimeManager.utc_now().strftime('%H:%M:%S')} UTC
- 상태: 모든 시스템 정상
- 테스트: Discord 웹훅 연결 성공 ✅

이 메시지가 보이면 알림 시스템이 올바르게 설정되었습니다!
"""
        return self.send_alert("🧪 델파이 시스템 테스트", test_message, "info")


# 전역 Discord 알림기 인스턴스
discord_notifier = DiscordNotifier()


def send_discord_alert(title: str, message: str, level: str = "info") -> bool:
    """간편한 Discord 알림 발송 함수"""
    return discord_notifier.send_alert(title, message, level)


def test_discord_notification() -> bool:
    """Discord 알림 테스트"""
    return discord_notifier.send_test_alert()


if __name__ == "__main__":
    # 테스트 실행
    print("Discord 알림 테스트 중...")
    if test_discord_notification():
        print("✅ Discord 알림 테스트 성공!")
    else:
        print("❌ Discord 알림 테스트 실패!")