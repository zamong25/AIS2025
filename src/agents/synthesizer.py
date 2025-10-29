"""
델파이 트레이딩 시스템 - 신디사이저 에이전트
최종 거래 결정을 담당하는 AI 에이전트
"""

import os
import json
import logging
from typing import Optional
from utils.openai_client import openai_client
from utils.time_manager import TimeManager


class SynthesizerAgent:
    """신디사이저 에이전트 - 솔론"""
    
    def __init__(self, prompt_path: str = None, use_v2: bool = True):
        if prompt_path is None:
            # 프로젝트 루트 기준으로 프롬프트 경로 설정
            import os
            current_file = os.path.abspath(__file__)
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_file)))
            # V2 프롬프트 사용 여부에 따라 경로 선택
            if use_v2:
                prompt_path = os.path.join(project_root, "prompts", "synthesizer_v2.txt")
            else:
                prompt_path = os.path.join(project_root, "prompts", "synthesizer_final.txt")
        self.prompt_path = prompt_path
        self.agent_name = "솔론"
        self.use_v2 = use_v2
    
    def synthesize(self, chartist_report: dict, journalist_report: dict,
                  quant_report: dict, stoic_report: dict,
                  execution_time: dict = None, current_position: dict = None,
                  trade_history: list = None, position_context: str = None,
                  chart_images: list = None, current_price: float = None,
                  triggered_by: dict = None) -> Optional[dict]:
        """
        4개 전문가 보고서를 종합하여 최종 거래 플레이북 생성
        
        개선된 접근법:
        1. 점수 표준화로 충돌 해결 개선
        2. 기존 플레이북 구조 완전 유지 (레버리지, 위험관리 등)
        3. SYNTHESIZER_RULES.md 규칙 준수
        """
        logging.info(f"\n--- [{self.agent_name}] 신디사이저 최종 종합 판단 시작 (v2.1 - Enhanced) ---")
        
        if execution_time is None:
            execution_time = TimeManager.get_execution_time()
        
        try:
            # V2 모드 체크
            if self.use_v2:
                logging.info(f"\n--- [{self.agent_name}] 신디사이저 v2 독립적 거래 판단 시작 ---")
                if not chart_images:
                    logging.error("❌ V2 모드에서는 차트 이미지가 필요합니다")
                    return None
                if current_price is None:
                    logging.warning("⚠️ 현재가 정보가 없습니다. 차티스트 가격 사용")
                    current_price = chartist_report.get('current_price', 0)
            
            
            # 4개 보고서를 하나의 JSON으로 구성
            enhanced_input = {
                "chartist_report": chartist_report,
                "journalist_report": journalist_report,
                "quant_report": quant_report,
                "stoic_report": stoic_report,
                "current_position": current_position or {"has_position": False},
                "trade_history": trade_history or [],
                "position_context": position_context,
                "triggered_by": triggered_by  # 트리거 정보 추가
            }
            
            logging.info("✅ 4개 전문가 보고서 통합 완료 (개선된 충돌 해결 포함)")
            
            # 트리거 정보 로깅
            if triggered_by:
                logging.info(f"🎯 트리거 발동으로 인한 재분석: {triggered_by.get('trigger_id', 'N/A')} - {triggered_by.get('direction', 'N/A')} ${triggered_by.get('price', 'N/A')}")
            
            # Phase 3: AI를 통한 최종 플레이북 생성
            if self.use_v2:
                # V2: 이미지 포함 분석
                prompt = self._prepare_v2_prompt(enhanced_input, execution_time, current_price)
                if not prompt:
                    return None
                
                # 이미지 파일 로드
                images = []
                try:
                    import PIL.Image
                    for img_path in chart_images:
                        if os.path.exists(img_path):
                            img = PIL.Image.open(img_path)
                            images.append(img)
                            logging.info(f"✅ 차트 이미지 로드: {os.path.basename(img_path)}")
                        else:
                            logging.warning(f"⚠️ 이미지 파일 없음: {img_path}")
                except Exception as e:
                    logging.error(f"❌ 이미지 로드 실패: {e}")
                    return None
                
                # AI 분석 실행 (이미지 포함)
                result = openai_client.invoke_agent_json("gpt-4o", prompt, images=images)
            else:
                # 기존 방식
                prompt = self._prepare_enhanced_prompt(enhanced_input, execution_time)
                if not prompt:
                    return None
                
                # AI 분석 실행
                result = openai_client.invoke_agent_json("gpt-4o", prompt)
            
            if result:
                logging.info("✅ 신디사이저 최종 플레이북 생성 완료")
                self._log_decision_summary(result)
                return result
            else:
                logging.error("❌ 신디사이저 플레이북 생성 실패")
                return None
                
        except Exception as e:
            logging.error(f"❌ 신디사이저 실행 중 오류: {e}")
            return None
    
    def _prepare_enhanced_prompt(self, enhanced_input: dict, execution_time: dict) -> Optional[str]:
        """개선된 데이터를 포함한 프롬프트 준비"""
        try:
            with open(self.prompt_path, 'r', encoding='utf-8') as f:
                template = f.read()
            
            # 기존 replacements + 새로운 데이터 추가
            replacements = {
                "입력받은 현재 시간 UTC ISO 형식": execution_time['utc_iso'],
                "입력받은 현재 시간 KST 형식": execution_time['kst_display'],
                "분석 대상 자산": "SOL/USDT"
            }
            
            for key, val in replacements.items():
                template = template.replace(key, str(val))
            
            # 입력 데이터를 프롬프트에 추가
            enhanced_prompt = f"{template}\n\n=== 입력 데이터 ===\n"
            enhanced_prompt += "\n[에이전트 보고서]\n"
            enhanced_prompt += json.dumps({
                "chartist_report": enhanced_input['chartist_report'],
                "journalist_report": enhanced_input['journalist_report'],
                "quant_report": enhanced_input['quant_report'],
                "stoic_report": enhanced_input['stoic_report'],
                "current_position": enhanced_input['current_position'],
                "trade_history": enhanced_input['trade_history']
            }, ensure_ascii=False, indent=2)
            
            # 포지션 컨텍스트 추가
            if enhanced_input['position_context']:
                enhanced_prompt += "\n\n[5. 현재 포지션 컨텍스트]\n"
                enhanced_prompt += enhanced_input['position_context']
            
            # 트리거 정보 추가 (트리거로 인한 재분석인 경우)
            if enhanced_input.get('triggered_by'):
                enhanced_prompt += "\n\n[6. 트리거 발동 정보]\n"
                enhanced_prompt += f"트리거 ID: {enhanced_input['triggered_by'].get('trigger_id', 'N/A')}\n"
                enhanced_prompt += f"방향: {enhanced_input['triggered_by'].get('direction', 'N/A')}\n"
                enhanced_prompt += f"트리거 가격: ${enhanced_input['triggered_by'].get('price', 'N/A')}\n"
                enhanced_prompt += f"발동 사유: {enhanced_input['triggered_by'].get('rationale', 'N/A')}\n"
                enhanced_prompt += f"신뢰도: {enhanced_input['triggered_by'].get('confidence', 'N/A')}%\n"
                enhanced_prompt += "\n❗ 이 분석은 트리거 발동으로 인한 재분석입니다. 트리거 조건을 고려하여 판단하세요.\n"
            
            # 추가 지시사항
            enhanced_prompt += "\n\n=== 중요 지시사항 ===\n"
            enhanced_prompt += "❗ 각 에이전트의 전체 보고서 내용을 깊이 있게 분석하세요.\n"
            enhanced_prompt += "❗ 특히 다음 항목들을 주의깊게 확인하세요:\n"
            enhanced_prompt += "   - 차티스트: 시간대별 신호 강도와 패턴의 신뢰도\n"
            enhanced_prompt += "   - 저널리스트: detailed_analysis.impact_timing의 immediate/short/long 구분\n"
            enhanced_prompt += "   - 퀀트: adaptive threshold와 실제 시장 상태\n"
            enhanced_prompt += "   - 스토익: 구체적 리스크 요인들\n"
            enhanced_prompt += "❗ 레버리지, 손절가, 진입가 등 실행 계획은 반드시 포함하세요.\n"
            enhanced_prompt += "❗ SYNTHESIZER_RULES.md 규칙을 철저히 준수하세요.\n"
            
            
            # 저널리스트 평가 가이드
            enhanced_prompt += "\n❗ 저널리스트 보고서 평가 가이드:\n"
            enhanced_prompt += "   - immediate_impact ≥ 8: 즉시 거래 신호로 활용 가능\n"
            enhanced_prompt += "   - immediate_impact 5-7: 보조 지표로 참고\n"
            enhanced_prompt += "   - immediate_impact ≤ 4: 단기 거래에서는 영향력 최소화\n"
            enhanced_prompt += "   - 단기 트레이딩(15분-4시간)에서는 long_term_impact보다 immediate_impact를 중시\n"
            
            if enhanced_input['position_context']:
                enhanced_prompt += "\n❗ 포지션 컨텍스트를 반드시 고려하여 거래 연속성을 유지하세요.\n"
            
            logging.info("📋 신디사이저 개선된 프롬프트 준비 완료")
            return enhanced_prompt
            
        except FileNotFoundError:
            logging.error(f"❌ 프롬프트 파일을 찾을 수 없습니다: {self.prompt_path}")
            return None
    
    def _prepare_v2_prompt(self, enhanced_input: dict, execution_time: dict, current_price: float) -> Optional[str]:
        """V2 프롬프트 준비 - 이미지 분석 포함"""
        try:
            with open(self.prompt_path, 'r', encoding='utf-8') as f:
                template = f.read()
            
            # 기본 replacements
            replacements = {
                "입력받은 현재 시간 UTC ISO 형식": execution_time['utc_iso'],
                "입력받은 현재 시간 KST 형식": execution_time['kst_display']
            }
            
            for key, val in replacements.items():
                template = template.replace(key, str(val))
            
            # V2 프롬프트에 필요한 데이터 구성
            v2_prompt = f"{template}\n\n=== 입력 데이터 ===\n"
            
            # 1. 현재가 정보
            v2_prompt += f"\n[현재가]\n{current_price:.2f}\n"
            
            # 2. 에이전트 보고서
            v2_prompt += "\n[에이전트 보고서]\n"
            v2_prompt += json.dumps({
                "chartist_report": enhanced_input['chartist_report'],
                "journalist_report": enhanced_input['journalist_report'],
                "quant_report": enhanced_input['quant_report'],
                "stoic_report": enhanced_input['stoic_report']
            }, ensure_ascii=False, indent=2)
            
            # 3. 포지션 정보
            v2_prompt += "\n\n[현재 포지션]\n"
            v2_prompt += json.dumps(enhanced_input['current_position'], ensure_ascii=False, indent=2)
            
            # 4. 거래 이력
            v2_prompt += "\n\n[최근 거래 이력]\n"
            v2_prompt += json.dumps(enhanced_input['trade_history'][-5:] if enhanced_input['trade_history'] else [], ensure_ascii=False, indent=2)
            
            # 5. 포지션 컨텍스트
            if enhanced_input.get('position_context'):
                v2_prompt += "\n\n[포지션 컨텍스트]\n"
                v2_prompt += enhanced_input['position_context']
            
            # 6. 트리거 정보 (트리거로 인한 재분석인 경우)
            if enhanced_input.get('triggered_by'):
                v2_prompt += "\n\n[트리거 발동 정보]\n"
                v2_prompt += f"트리거 ID: {enhanced_input['triggered_by'].get('trigger_id', 'N/A')}\n"
                v2_prompt += f"방향: {enhanced_input['triggered_by'].get('direction', 'N/A')}\n"
                v2_prompt += f"트리거 가격: ${enhanced_input['triggered_by'].get('price', 'N/A')}\n"
                v2_prompt += f"발동 사유: {enhanced_input['triggered_by'].get('rationale', 'N/A')}\n"
                v2_prompt += f"신뢰도: {enhanced_input['triggered_by'].get('confidence', 'N/A')}%\n"
                v2_prompt += "\n❗ 이 분석은 트리거 발동으로 인한 재분석입니다. 트리거 조건을 고려하여 판단하세요.\n"
            
            # 7. 중요 지시사항
            v2_prompt += "\n\n=== 중요 지시사항 ===\n"
            v2_prompt += "❗ 차트 이미지를 먼저 직접 분석하고, 당신만의 독립적 판단을 내리세요.\n"
            v2_prompt += "❗ 에이전트 보고서는 참고자료일 뿐, 최종 결정은 당신의 판단입니다.\n"
            v2_prompt += "❗ Lux Algo 오실레이터의 점 크기 변화를 주의깊게 확인하세요.\n"
            v2_prompt += "❗ 실행 가능한 구체적 계획을 제시하세요.\n"
            
            logging.info("📋 신디사이저 V2 프롬프트 준비 완료")
            return v2_prompt
            
        except FileNotFoundError:
            logging.error(f"❌ 프롬프트 파일을 찾을 수 없습니다: {self.prompt_path}")
            return None
    
    def _log_decision_summary(self, decision: dict):
        """투명한 결정 사항 요약 로그"""
        try:
            if self.use_v2:
                # V2 형식
                final_decision = decision.get('final_decision', {})
                action = final_decision.get('action', 'UNKNOWN')
                confidence = final_decision.get('confidence', 0)
                scenario = final_decision.get('scenario', '시나리오 없음')
                
                logging.info(f"🔥 최종 결정: {action} (신뢰도: {confidence}점)")
                logging.info(f"📈 시나리오: {scenario}")
                
                # 차트 인사이트
                chart_insights = decision.get('chart_insights', {})
                if chart_insights:
                    logging.info(f"👁️ 차트 발견: {chart_insights.get('hidden_pattern', 'N/A')}")
                    logging.info(f"📊 Lux Algo: {chart_insights.get('lux_algo_signal', 'N/A')}")
                
                # 실행 계획
                execution = decision.get('execution_plan', {})
                if execution.get('entry_price'):
                    logging.info(f"🎯 진입: ${execution.get('entry_price', 0):.2f} ({execution.get('order_type', 'N/A')})")
                    logging.info(f"🛡️ 손절: ${execution.get('stop_loss', 0):.2f}, 익절: ${execution.get('take_profit_1', 0):.2f}")
                
                # 근거
                rationale = final_decision.get('rationale', '사유 없음')
                logging.info(f"📝 결정 근거: {rationale}")
            else:
                # 기존 형식
                final_decision = decision.get('final_decision', {})
                decision_process = decision.get('decision_process', {})
                
                # 기본 정보
                action = final_decision.get('decision', 'UNKNOWN')
                confidence = final_decision.get('confidence_score', 0)
                urgency = final_decision.get('urgency', 'UNKNOWN')
                
                logging.info(f"🔥 최종 결정: {action} (신뢰도: {confidence}%, 긴급도: {urgency})")
                
                # 점수 정보
                scores = decision_process.get('step1_standardized_scores', {})
                if scores:
                    logging.info(f"📊 표준화된 점수: {', '.join([f'{k}: {v:.1f}' for k, v in scores.items()])}")
                
                # 충돌 해결 정보
                conflict_info = decision_process.get('step2_conflict_analysis', {})
                if conflict_info:
                    logging.info(f"🔄 충돌 해결: {conflict_info.get('resolution_strategy', 'N/A')} (범위: {conflict_info.get('score_range', 0):.1f}점)")
                
                # 최종 계산
                final_calc = decision_process.get('step3_final_calculation', {})
                if final_calc:
                    logging.info(f"🎯 최종 점수: {final_calc.get('calculated_score', 0):.1f}/100")
                    
                # 근거
                rationale = final_decision.get('rationale', '사유 없음')
                logging.info(f"📝 결정 근거: {rationale}")
                
        except Exception as e:
            logging.warning(f"⚠️ 결정 요약 로그 생성 실패: {e}")


# 전역 신디사이저 에이전트 인스턴스 (V2 모드 - 차트 이미지 포함 분석)
synthesizer_agent = SynthesizerAgent(use_v2=True)