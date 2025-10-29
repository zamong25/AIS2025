"""
델파이 트레이딩 시스템 - 슬리피지 및 수수료 계산기
정확한 거래 비용 계산으로 실제 수익성 분석
"""

import logging
import statistics
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timezone
from dataclasses import dataclass
from enum import Enum
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.discord_notifier import discord_notifier

class OrderType(Enum):
    """주문 유형"""
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP_LOSS = "STOP_LOSS"
    TAKE_PROFIT = "TAKE_PROFIT"
    OCO = "OCO"

class TradingSide(Enum):
    """거래 방향"""
    BUY = "BUY"
    SELL = "SELL"

@dataclass
class FeeStructure:
    """수수료 구조"""
    maker_fee: float  # 메이커 수수료 (%)
    taker_fee: float  # 테이커 수수료 (%)
    futures_maker_fee: float  # 선물 메이커 수수료 (%)
    futures_taker_fee: float  # 선물 테이커 수수료 (%)
    funding_fee: float  # 펀딩 수수료 (%)
    vip_level: int = 0  # VIP 레벨

@dataclass 
class SlippageConfig:
    """슬리피지 설정"""
    base_slippage: float  # 기본 슬리피지 (%)
    volatility_multiplier: float  # 변동성 승수
    volume_impact_factor: float  # 거래량 영향 계수
    liquidity_adjustment: float  # 유동성 조정 계수
    time_impact: float  # 시간 영향 계수

@dataclass
class TradeCost:
    """거래 비용 정보"""
    entry_fee: float  # 진입 수수료
    exit_fee: float  # 청산 수수료
    total_fees: float  # 총 수수료
    entry_slippage: float  # 진입 슬리피지
    exit_slippage: float  # 청산 슬리피지
    total_slippage: float  # 총 슬리피지
    funding_cost: float  # 펀딩 비용
    total_cost: float  # 총 거래 비용
    cost_percentage: float  # 비용 비율 (%)
    breakeven_move: float  # 손익분기점 이동폭 (%)

class SlippageFeeCalculator:
    """슬리피지 및 수수료 계산기"""
    
    def __init__(self):
        """슬리피지 수수료 계산기 초기화"""
        
        # 바이낸스 수수료 구조 (2024년 기준)
        self.fee_structure = FeeStructure(
            maker_fee=0.1,           # 0.1% 메이커
            taker_fee=0.1,           # 0.1% 테이커
            futures_maker_fee=0.02,  # 0.02% 선물 메이커
            futures_taker_fee=0.04,  # 0.04% 선물 테이커
            funding_fee=0.01,        # 0.01% 펀딩 수수료 (8시간마다)
            vip_level=0
        )
        
        # 슬리피지 기본 설정
        self.slippage_config = SlippageConfig(
            base_slippage=0.05,        # 0.05% 기본 슬리피지
            volatility_multiplier=1.5,  # 변동성 1.5배 승수
            volume_impact_factor=0.02,  # 거래량 영향 2%
            liquidity_adjustment=1.0,   # 유동성 조정 1.0
            time_impact=0.01           # 시간 영향 1%
        )
        
        # 거래 히스토리 (슬리피지 학습용)
        self.trade_history = []
        self.symbol_slippage_data = {}
        
        # 시장 상황별 슬리피지 조정
        self.market_condition_multipliers = {
            'normal': 1.0,
            'volatile': 2.0,
            'low_liquidity': 1.5,
            'high_volume': 0.8,
            'asian_session': 1.2,
            'us_session': 0.9,
            'european_session': 1.0
        }
        
        logging.info("슬리피지 및 수수료 계산기 초기화")
    
    def calculate_trade_costs(self, 
                            symbol: str,
                            side: TradingSide,
                            quantity: float,
                            entry_price: float,
                            exit_price: float,
                            order_type: OrderType = OrderType.MARKET,
                            holding_time_hours: float = 24.0,
                            market_condition: str = 'normal') -> TradeCost:
        """
        거래 비용 종합 계산
        
        Args:
            symbol: 거래 심볼
            side: 거래 방향
            quantity: 거래량
            entry_price: 진입 가격
            exit_price: 청산 가격
            order_type: 주문 타입
            holding_time_hours: 보유 시간 (시간)
            market_condition: 시장 상황
            
        Returns:
            TradeCost: 거래 비용 정보
        """
        try:
            logging.info(f"💰 거래 비용 계산 시작: {symbol} {side.value} {quantity}")
            
            # 1. 거래 규모 계산
            notional_value = quantity * entry_price
            
            # 2. 수수료 계산
            entry_fee = self._calculate_fee(notional_value, order_type, is_futures=True)
            exit_fee = self._calculate_fee(quantity * exit_price, order_type, is_futures=True)
            total_fees = entry_fee + exit_fee
            
            # 3. 슬리피지 계산
            entry_slippage = self._calculate_slippage(
                symbol, quantity, entry_price, side, market_condition
            )
            exit_slippage = self._calculate_slippage(
                symbol, quantity, exit_price, 
                TradingSide.SELL if side == TradingSide.BUY else TradingSide.BUY,
                market_condition
            )
            total_slippage = entry_slippage + exit_slippage
            
            # 4. 펀딩 비용 계산
            funding_cost = self._calculate_funding_cost(
                notional_value, holding_time_hours, symbol
            )
            
            # 5. 총 비용 계산
            total_cost = total_fees + total_slippage + funding_cost
            cost_percentage = (total_cost / notional_value) * 100
            
            # 6. 손익분기점 계산
            breakeven_move = self._calculate_breakeven_move(
                total_cost, notional_value, side
            )
            
            # 7. 거래 비용 객체 생성
            trade_cost = TradeCost(
                entry_fee=entry_fee,
                exit_fee=exit_fee,
                total_fees=total_fees,
                entry_slippage=entry_slippage,
                exit_slippage=exit_slippage,
                total_slippage=total_slippage,
                funding_cost=funding_cost,
                total_cost=total_cost,
                cost_percentage=cost_percentage,
                breakeven_move=breakeven_move
            )
            
            # 8. 결과 로깅
            logging.info(f"✅ 거래 비용 계산 완료: 총 ${total_cost:.2f} ({cost_percentage:.2f}%)")
            
            return trade_cost
            
        except Exception as e:
            logging.error(f"❌ 거래 비용 계산 실패: {e}")
            raise
    
    def _calculate_fee(self, notional_value: float, order_type: OrderType, 
                      is_futures: bool = True) -> float:
        """수수료 계산"""
        try:
            # 주문 타입별 수수료 결정
            if order_type == OrderType.LIMIT:
                # 리미트 주문은 메이커 수수료 적용 (대부분의 경우)
                fee_rate = (self.fee_structure.futures_maker_fee if is_futures 
                           else self.fee_structure.maker_fee) / 100
            else:
                # 마켓 주문은 테이커 수수료 적용
                fee_rate = (self.fee_structure.futures_taker_fee if is_futures 
                           else self.fee_structure.taker_fee) / 100
            
            fee = notional_value * fee_rate
            
            logging.debug(f"💳 수수료 계산: ${notional_value:.2f} × {fee_rate:.4f} = ${fee:.2f}")
            return fee
            
        except Exception as e:
            logging.error(f"❌ 수수료 계산 실패: {e}")
            return 0.0
    
    def _calculate_slippage(self, symbol: str, quantity: float, price: float,
                           side: TradingSide, market_condition: str) -> float:
        """슬리피지 계산"""
        try:
            # 1. 기본 슬리피지
            base_slippage = self.slippage_config.base_slippage / 100
            
            # 2. 시장 상황 조정
            market_multiplier = self.market_condition_multipliers.get(market_condition, 1.0)
            
            # 3. 거래량 영향 계산
            notional_value = quantity * price
            volume_impact = min(notional_value / 100000, 0.5) * self.slippage_config.volume_impact_factor
            
            # 4. 심볼별 과거 슬리피지 데이터 반영
            historical_adjustment = self._get_historical_slippage_adjustment(symbol)
            
            # 5. 방향별 조정 (매도시 슬리피지가 일반적으로 더 큼)
            side_multiplier = 1.1 if side == TradingSide.SELL else 1.0
            
            # 6. 총 슬리피지 계산
            total_slippage_rate = (
                base_slippage * 
                market_multiplier * 
                side_multiplier * 
                (1 + volume_impact) * 
                (1 + historical_adjustment)
            )
            
            # 7. 금액으로 변환
            slippage_amount = notional_value * total_slippage_rate
            
            logging.debug(f"📊 슬리피지 계산: {symbol} {side.value} - {total_slippage_rate:.4f}% (${slippage_amount:.2f})")
            
            return slippage_amount
            
        except Exception as e:
            logging.error(f"❌ 슬리피지 계산 실패: {e}")
            return 0.0
    
    def _calculate_funding_cost(self, notional_value: float, 
                               holding_time_hours: float, symbol: str) -> float:
        """펀딩 비용 계산 (선물 거래)"""
        try:
            # 펀딩 수수료는 8시간마다 부과
            funding_periods = holding_time_hours / 8.0
            
            # 현재 펀딩 비율 (실제로는 API에서 조회해야 함)
            funding_rate = self._get_current_funding_rate(symbol)
            
            # 펀딩 비용 계산
            funding_cost = notional_value * (funding_rate / 100) * funding_periods
            
            logging.debug(f"💸 펀딩 비용: ${notional_value:.2f} × {funding_rate:.4f}% × {funding_periods:.1f} = ${funding_cost:.2f}")
            
            return abs(funding_cost)  # 절대값으로 비용 계산
            
        except Exception as e:
            logging.error(f"❌ 펀딩 비용 계산 실패: {e}")
            return 0.0
    
    def _calculate_breakeven_move(self, total_cost: float, notional_value: float,
                                 side: TradingSide) -> float:
        """손익분기점 계산"""
        try:
            # 총 비용을 극복하기 위해 필요한 가격 이동률
            breakeven_percentage = (total_cost / notional_value) * 100
            
            logging.debug(f"⚖️ 손익분기점: {breakeven_percentage:.2f}% 가격 이동 필요")
            
            return breakeven_percentage
            
        except Exception as e:
            logging.error(f"❌ 손익분기점 계산 실패: {e}")
            return 0.0
    
    def _get_historical_slippage_adjustment(self, symbol: str) -> float:
        """과거 슬리피지 데이터 기반 조정"""
        try:
            if symbol not in self.symbol_slippage_data:
                return 0.0
            
            historical_data = self.symbol_slippage_data[symbol]
            if len(historical_data) < 5:
                return 0.0
            
            # 최근 10회 평균 슬리피지 계산
            recent_slippages = historical_data[-10:]
            avg_slippage = statistics.mean(recent_slippages)
            
            # 기본 슬리피지 대비 조정률 계산
            base_slippage = self.slippage_config.base_slippage / 100
            adjustment = (avg_slippage - base_slippage) / base_slippage
            
            # 조정률 제한 (-50% ~ +100%)
            adjustment = max(-0.5, min(1.0, adjustment))
            
            return adjustment
            
        except Exception as e:
            logging.error(f"❌ 과거 슬리피지 조정 계산 실패: {e}")
            return 0.0
    
    def _get_current_funding_rate(self, symbol: str) -> float:
        """현재 펀딩 비율 조회 (시뮬레이션)"""
        try:
            # 실제로는 바이낸스 API에서 조회해야 함
            # 여기서는 심볼별 평균 펀딩 비율 시뮬레이션
            funding_rates = {
                'BTCUSDT': 0.01,
                'ETHUSDT': 0.005,
                'SOLUSDT': 0.02,
                'ADAUSDT': 0.015,
                'DOTUSDT': 0.01
            }
            
            return funding_rates.get(symbol, 0.01)  # 기본 0.01%
            
        except Exception as e:
            logging.error(f"❌ 펀딩 비율 조회 실패: {e}")
            return 0.01
    
    def update_slippage_data(self, symbol: str, expected_price: float, 
                           actual_price: float, side: TradingSide):
        """실제 거래 결과로 슬리피지 데이터 업데이트"""
        try:
            # 실제 슬리피지 계산
            if side == TradingSide.BUY:
                # 매수시: 실제가격이 예상가격보다 높으면 슬리피지
                slippage_rate = (actual_price - expected_price) / expected_price
            else:
                # 매도시: 실제가격이 예상가격보다 낮으면 슬리피지
                slippage_rate = (expected_price - actual_price) / expected_price
            
            # 슬리피지 데이터 저장
            if symbol not in self.symbol_slippage_data:
                self.symbol_slippage_data[symbol] = []
            
            self.symbol_slippage_data[symbol].append(abs(slippage_rate))
            
            # 최근 100개만 유지
            if len(self.symbol_slippage_data[symbol]) > 100:
                self.symbol_slippage_data[symbol] = self.symbol_slippage_data[symbol][-100:]
            
            logging.info(f"📊 슬리피지 데이터 업데이트: {symbol} {slippage_rate:.4f}%")
            
        except Exception as e:
            logging.error(f"❌ 슬리피지 데이터 업데이트 실패: {e}")
    
    def analyze_cost_efficiency(self, trade_cost: TradeCost, 
                               expected_profit_pct: float) -> Dict:
        """거래 비용 효율성 분석"""
        try:
            analysis = {
                'is_cost_efficient': False,
                'profit_to_cost_ratio': 0.0,
                'recommendation': '',
                'risk_level': 'HIGH',
                'breakeven_probability': 0.0
            }
            
            # 수익 대비 비용 비율 계산
            if trade_cost.cost_percentage > 0:
                analysis['profit_to_cost_ratio'] = expected_profit_pct / trade_cost.cost_percentage
            
            # 비용 효율성 판단
            if analysis['profit_to_cost_ratio'] >= 3.0:
                analysis['is_cost_efficient'] = True
                analysis['recommendation'] = '높은 비용 효율성 - 거래 권장'
                analysis['risk_level'] = 'LOW'
            elif analysis['profit_to_cost_ratio'] >= 2.0:
                analysis['is_cost_efficient'] = True
                analysis['recommendation'] = '적정 비용 효율성 - 신중한 거래'
                analysis['risk_level'] = 'MEDIUM'
            else:
                analysis['recommendation'] = '낮은 비용 효율성 - 거래 재고 필요'
                analysis['risk_level'] = 'HIGH'
            
            # 손익분기점 돌파 확률 추정 (단순화된 모델)
            if trade_cost.breakeven_move <= 1.0:
                analysis['breakeven_probability'] = 0.8
            elif trade_cost.breakeven_move <= 2.0:
                analysis['breakeven_probability'] = 0.6
            elif trade_cost.breakeven_move <= 3.0:
                analysis['breakeven_probability'] = 0.4
            else:
                analysis['breakeven_probability'] = 0.2
            
            return analysis
            
        except Exception as e:
            logging.error(f"❌ 비용 효율성 분석 실패: {e}")
            return {}
    
    def get_cost_summary(self, trade_cost: TradeCost) -> str:
        """거래 비용 요약 보고서"""
        try:
            summary = f"""
💰 거래 비용 분석 보고서
{'='*50}
📊 수수료:
   진입 수수료: ${trade_cost.entry_fee:.2f}
   청산 수수료: ${trade_cost.exit_fee:.2f}
   총 수수료: ${trade_cost.total_fees:.2f}

📈 슬리피지:
   진입 슬리피지: ${trade_cost.entry_slippage:.2f}
   청산 슬리피지: ${trade_cost.exit_slippage:.2f}
   총 슬리피지: ${trade_cost.total_slippage:.2f}

💸 기타 비용:
   펀딩 비용: ${trade_cost.funding_cost:.2f}

💯 총 거래 비용:
   금액: ${trade_cost.total_cost:.2f}
   비율: {trade_cost.cost_percentage:.2f}%
   손익분기점: {trade_cost.breakeven_move:.2f}% 가격 이동 필요

"""
            return summary
            
        except Exception as e:
            logging.error(f"❌ 비용 요약 생성 실패: {e}")
            return "비용 요약 생성 실패"
    
    def optimize_order_strategy(self, symbol: str, target_quantity: float,
                               current_price: float, side: TradingSide) -> Dict:
        """주문 전략 최적화 (비용 최소화)"""
        try:
            strategies = {}
            
            # 1. 단일 마켓 주문
            market_cost = self._calculate_slippage(
                symbol, target_quantity, current_price, side, 'normal'
            ) + self._calculate_fee(
                target_quantity * current_price, OrderType.MARKET, True
            )
            
            strategies['single_market'] = {
                'cost': market_cost,
                'execution_time': '즉시',
                'risk': '높음 (큰 슬리피지)'
            }
            
            # 2. 단일 리미트 주문
            limit_cost = self._calculate_fee(
                target_quantity * current_price, OrderType.LIMIT, True
            )
            
            strategies['single_limit'] = {
                'cost': limit_cost,
                'execution_time': '불확실',
                'risk': '낮음 (체결 위험)'
            }
            
            # 3. 분할 주문 (TWAP 방식)
            splits = [2, 3, 5]
            for split in splits:
                split_quantity = target_quantity / split
                split_cost = 0
                
                for _ in range(split):
                    split_cost += self._calculate_slippage(
                        symbol, split_quantity, current_price, side, 'normal'
                    ) * 0.7  # 분할로 인한 슬리피지 감소
                    split_cost += self._calculate_fee(
                        split_quantity * current_price, OrderType.LIMIT, True
                    )
                
                strategies[f'split_{split}'] = {
                    'cost': split_cost,
                    'execution_time': f'{split*2}분 예상',
                    'risk': '중간'
                }
            
            # 최적 전략 선택
            best_strategy = min(strategies.items(), key=lambda x: x[1]['cost'])
            
            return {
                'strategies': strategies,
                'recommended': best_strategy[0],
                'cost_savings': market_cost - best_strategy[1]['cost']
            }
            
        except Exception as e:
            logging.error(f"❌ 주문 전략 최적화 실패: {e}")
            return {}
    
    def send_cost_alert(self, trade_cost: TradeCost, symbol: str, 
                       notional_value: float):
        """높은 거래 비용 알림"""
        try:
            # 높은 비용 기준 (2% 이상)
            if trade_cost.cost_percentage >= 2.0:
                discord_notifier.send_alert(
                    f"⚠️ 높은 거래 비용 경고\n"
                    f"심볼: {symbol}\n"
                    f"거래 규모: ${notional_value:,.2f}\n"
                    f"총 비용: ${trade_cost.total_cost:.2f} ({trade_cost.cost_percentage:.2f}%)\n"
                    f"손익분기점: {trade_cost.breakeven_move:.2f}% 가격 이동 필요\n"
                    f"권장: 거래 규모 축소 또는 전략 재검토",
                    level="warning"
                )
                
        except Exception as e:
            logging.error(f"❌ 비용 알림 전송 실패: {e}")


# 전역 슬리피지 수수료 계산기 인스턴스
slippage_fee_calculator = SlippageFeeCalculator()