"""설정 로더 - YAML 파일을 Python 객체로 변환"""

import os
import yaml
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Dict, Any


@dataclass
class CapitalConfig:
    """자본 설정"""
    initial_capital: float
    currency: str


@dataclass
class RiskManagementConfig:
    """리스크 관리 설정"""
    max_positions: int
    max_exposure_ratio: float
    max_loss_per_trade: float
    max_daily_loss: float
    stop_loss_ratio: float
    take_profit_ratio_1: float
    take_profit_ratio_2: float
    partial_close_ratio: float


@dataclass
class TradingSettings:
    """거래 설정"""
    default_symbol: str
    default_leverage: int
    min_trade_amount: float
    default_quantity: float


@dataclass
class FeeConfig:
    """수수료 설정"""
    futures_maker_fee: float
    futures_taker_fee: float
    spot_maker_fee: float
    spot_taker_fee: float


@dataclass
class MonitoringConfig:
    """모니터링 설정"""
    heartbeat_interval_seconds: int
    max_error_history: int
    performance_history_days: int


@dataclass
class ReportingConfig:
    """리포팅 설정"""
    daily_report_time: str
    weekly_report_day: str
    report_timezone: str


@dataclass
class DashboardConfig:
    """대시보드 설정"""
    session_timeout_hours: int
    max_websocket_connections: int
    update_interval_seconds: int


@dataclass
class SystemConfig:
    """시스템 설정"""
    log_level: str
    database_path: str
    cache_size_mb: int
    worker_threads: int


@dataclass
class TradingConfig:
    """전체 트레이딩 설정"""
    capital: CapitalConfig
    risk_management: RiskManagementConfig
    trading: TradingSettings
    fees: FeeConfig
    monitoring: MonitoringConfig
    reporting: ReportingConfig
    dashboard: DashboardConfig
    system: SystemConfig


class ConfigLoader:
    """설정 로더"""
    
    _instance: Optional['ConfigLoader'] = None
    _config: Optional[TradingConfig] = None
    _raw_config: Optional[Dict[str, Any]] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigLoader, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._config is None:
            self._load_config()
    
    def _load_config(self):
        """설정 파일 로드"""
        # 환경별 설정 파일 경로
        env = os.getenv('TRADING_ENV', 'production')
        
        # 기본 설정 파일
        base_path = Path(__file__).parent / 'trading_config.yaml'
        
        # 환경별 설정 파일 (있으면)
        env_path = Path(__file__).parent / f'trading_config.{env}.yaml'
        
        # 기본 설정 로드
        with open(base_path, 'r', encoding='utf-8') as f:
            config_dict = yaml.safe_load(f)
        
        # 환경별 설정으로 오버라이드
        if env_path.exists():
            with open(env_path, 'r', encoding='utf-8') as f:
                env_config = yaml.safe_load(f)
                self._deep_merge(config_dict, env_config)
        
        # 환경변수로 오버라이드
        self._override_with_env_vars(config_dict)
        
        # 원본 딕셔너리 저장 (load_config 메서드용)
        self._raw_config = config_dict.copy()
        
        # 객체로 변환
        self._config = self._dict_to_config(config_dict)
    
    def _deep_merge(self, base: Dict, override: Dict):
        """딕셔너리 깊은 병합"""
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = value
    
    def _override_with_env_vars(self, config: Dict):
        """환경변수로 설정 오버라이드"""
        # 예: TRADING_CAPITAL_INITIAL_CAPITAL=20000
        for env_key, env_value in os.environ.items():
            if env_key.startswith('TRADING_'):
                keys = env_key.lower().split('_')[1:]  # 'trading' 제거
                self._set_nested_value(config, keys, env_value)
    
    def _set_nested_value(self, config: Dict, keys: list, value: str):
        """중첩된 딕셔너리 값 설정"""
        current = config
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        
        # 타입 변환
        try:
            if value.lower() in ('true', 'false'):
                value = value.lower() == 'true'
            elif '.' in value:
                value = float(value)
            else:
                value = int(value)
        except ValueError:
            pass  # 문자열로 유지
        
        current[keys[-1]] = value
    
    def _dict_to_config(self, config_dict: Dict) -> TradingConfig:
        """딕셔너리를 설정 객체로 변환"""
        return TradingConfig(
            capital=CapitalConfig(**config_dict['capital']),
            risk_management=RiskManagementConfig(**config_dict['risk_management']),
            trading=TradingSettings(**config_dict['trading']),
            fees=FeeConfig(**config_dict['fees']),
            monitoring=MonitoringConfig(**config_dict['monitoring']),
            reporting=ReportingConfig(**config_dict['reporting']),
            dashboard=DashboardConfig(**config_dict['dashboard']),
            system=SystemConfig(**config_dict['system'])
        )
    
    @property
    def config(self) -> TradingConfig:
        """설정 반환"""
        if self._config is None:
            self._load_config()
        return self._config
    
    def reload(self):
        """설정 다시 로드"""
        self._config = None
        self._raw_config = None
        self._load_config()
    
    def load_config(self) -> Dict[str, Any]:
        """원본 설정 딕셔너리 반환 (리포팅 시스템용)"""
        if self._raw_config is None:
            self._load_config()
        return self._raw_config.copy()


# 싱글톤 인스턴스
config_loader = ConfigLoader()