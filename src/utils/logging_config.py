"""
델파이 트레이딩 시스템 - 통합 로깅 설정 모듈
모든 로깅을 중앙에서 관리하고 일관된 설정 제공
"""

import logging
import os
import sys
from datetime import datetime
from pathlib import Path

class DelphiLogger:
    """델파이 시스템 전용 로거 관리자"""
    
    _initialized = False
    _loggers = {}
    
    @classmethod
    def initialize(cls, log_level=logging.INFO):
        """로깅 시스템 초기화 (한 번만 호출)"""
        if cls._initialized:
            return
            
        # 프로젝트 루트 찾기
        current_file = Path(__file__)
        project_root = current_file.parent.parent.parent
        log_dir = project_root / 'logs'
        log_dir.mkdir(exist_ok=True)
        
        # 메인 로그 파일
        log_file = log_dir / 'delphi.log'
        
        # 기존 로깅 핸들러 모두 제거
        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        # 통합 로깅 설정
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s [%(levelname)s] [%(name)s] %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8', mode='a'),
                logging.StreamHandler(sys.stdout)
            ],
            force=True  # 기존 설정 강제 덮어쓰기
        )
        
        cls._initialized = True
        
        # 초기화 로그
        logger = cls.get_logger('DelphiLogger')
        logger.info("=" * 60)
        logger.info(f"델파이 트레이딩 시스템 로깅 초기화 완료")
        logger.info(f"로그 파일: {log_file}")
        logger.info(f"로그 레벨: {logging.getLevelName(log_level)}")
        logger.info("=" * 60)
    
    @classmethod
    def get_logger(cls, name: str = None):
        """로거 인스턴스 반환"""
        if not cls._initialized:
            cls.initialize()
        
        if name is None:
            name = 'delphi'
        
        if name not in cls._loggers:
            cls._loggers[name] = logging.getLogger(name)
        
        return cls._loggers[name]
    
    @classmethod
    def log_system_start(cls, module_name: str):
        """시스템/모듈 시작 로그"""
        logger = cls.get_logger(module_name)
        logger.info(f"🚀 {module_name} 시작")
        return logger
    
    @classmethod
    def log_system_complete(cls, module_name: str):
        """시스템/모듈 완료 로그"""
        logger = cls.get_logger(module_name)
        logger.info(f"✅ {module_name} 완료")
        return logger
    
    @classmethod
    def log_agent_start(cls, agent_name: str):
        """에이전트 시작 로그"""
        logger = cls.get_logger(f"agent.{agent_name}")
        logger.info(f"🤖 [{agent_name}] 에이전트 분석 시작")
        return logger
    
    @classmethod
    def log_agent_complete(cls, agent_name: str, success: bool = True):
        """에이전트 완료 로그"""
        logger = cls.get_logger(f"agent.{agent_name}")
        if success:
            logger.info(f"✅ [{agent_name}] 에이전트 분석 완료")
        else:
            logger.error(f"❌ [{agent_name}] 에이전트 분석 실패")
        return logger

# 편의 함수들
def get_logger(name: str = None):
    """로거 인스턴스 가져오기"""
    return DelphiLogger.get_logger(name)

def init_logging(log_level=logging.INFO):
    """로깅 초기화"""
    DelphiLogger.initialize(log_level)

def log_system_info(message: str, module_name: str = 'system'):
    """시스템 정보 로그"""
    logger = DelphiLogger.get_logger(module_name)
    logger.info(f"ℹ️ {message}")

def log_error(message: str, module_name: str = 'system'):
    """에러 로그"""
    logger = DelphiLogger.get_logger(module_name)
    logger.error(f"❌ {message}")

def log_warning(message: str, module_name: str = 'system'):
    """경고 로그"""
    logger = DelphiLogger.get_logger(module_name)
    logger.warning(f"⚠️ {message}")

# Phase 1 개선: 향상된 로깅 기능 추가
class EnhancedLogger:
    """에이전트 의사결정 및 시장 상태 상세 로깅"""
    
    @staticmethod
    def log_agent_decision(agent_name: str, decision_data: dict):
        """각 에이전트의 상세 의사결정 과정 기록"""
        logger = DelphiLogger.get_logger(f"agent.{agent_name}")
        
        # 신호 강도 로깅
        confidence = decision_data.get('confidence', 0)
        logger.info(f"[{agent_name}] 신호 강도: {confidence:.2f}")
        
        # 주요 근거 로깅
        rationale = decision_data.get('rationale', '')
        if rationale:
            logger.info(f"[{agent_name}] 주요 근거: {rationale}")
        
        # 추가 상세 정보 로깅
        if 'details' in decision_data:
            for key, value in decision_data['details'].items():
                logger.info(f"[{agent_name}] {key}: {value}")
    
    @staticmethod
    def log_market_state(market_data: dict):
        """시장 상태 스냅샷 자동 기록"""
        logger = DelphiLogger.get_logger("market.state")
        
        logger.info("=== 시장 상태 스냅샷 ===")
        
        # 변동성 로깅
        volatility = market_data.get('volatility', 0)
        logger.info(f"변동성: {volatility:.3f}")
        
        # 거래량 비율 로깅
        volume_ratio = market_data.get('volume_ratio', 0)
        logger.info(f"거래량 비율: {volume_ratio:.2f}")
        
        # 가격 정보 로깅
        if 'price' in market_data:
            logger.info(f"현재가: ${market_data['price']:,.2f}")
        
        # RSI 로깅
        if 'rsi' in market_data:
            logger.info(f"RSI: {market_data['rsi']:.1f}")
        
        # 추가 지표들
        for key, value in market_data.items():
            if key not in ['volatility', 'volume_ratio', 'price', 'rsi']:
                logger.info(f"{key}: {value}")
    
    @staticmethod
    def log_trade_analysis(trade_id: str, analysis_data: dict):
        """거래 분석 결과 상세 로깅"""
        logger = DelphiLogger.get_logger("trade.analysis")
        
        logger.info(f"=== 거래 분석: {trade_id} ===")
        
        # 각 에이전트별 기여도
        if 'agent_contributions' in analysis_data:
            for agent, contrib in analysis_data['agent_contributions'].items():
                logger.info(f"{agent} 기여도: {contrib:.1%}")
        
        # 시장 상황
        if 'market_context' in analysis_data:
            logger.info(f"시장 상황: {analysis_data['market_context']}")
        
        # 결정 요인
        if 'decision_factors' in analysis_data:
            logger.info("주요 결정 요인:")
            for factor in analysis_data['decision_factors']:
                logger.info(f"  - {factor}")

# 편의 함수 추가
def log_agent_decision(agent_name: str, decision_data: dict):
    """에이전트 의사결정 로깅 편의 함수"""
    EnhancedLogger.log_agent_decision(agent_name, decision_data)

def log_market_state(market_data: dict):
    """시장 상태 로깅 편의 함수"""
    EnhancedLogger.log_market_state(market_data)

def log_trade_analysis(trade_id: str, analysis_data: dict):
    """거래 분석 로깅 편의 함수"""
    EnhancedLogger.log_trade_analysis(trade_id, analysis_data)