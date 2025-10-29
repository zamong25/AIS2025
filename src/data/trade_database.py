"""
델파이 트레이딩 시스템 - 거래 기록 데이터베이스 관리
과거 거래 데이터를 축적하여 퀀트 에이전트의 통계적 분석을 지원
"""

import json
import sqlite3
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import os
import time

# 로거 설정
logger = logging.getLogger(__name__)

@dataclass
class TradeRecord:
    """단일 거래 기록을 나타내는 데이터 클래스"""
    trade_id: str
    asset: str
    entry_price: float
    exit_price: float
    direction: str  # "LONG" or "SHORT"
    leverage: float
    position_size_percent: float
    entry_time: str  # UTC ISO format
    exit_time: str   # UTC ISO format
    outcome: str     # "WIN" or "LOSS"
    rr_ratio: float  # Risk/Reward ratio achieved
    pnl_percent: float  # P&L as percentage
    market_conditions: Dict  # 진입 시점의 시장 상황
    agent_scores: Dict       # 4개 에이전트 점수
    stop_loss_price: float
    take_profit_price: float
    max_drawdown_percent: float

class TradeDatabase:
    """거래 기록 데이터베이스 관리 클래스"""
    
    def __init__(self, db_path: str = None):
        if db_path is None:
            # 기본 경로를 절대 경로로 설정
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            db_dir = os.path.join(base_dir, 'data', 'database')
            os.makedirs(db_dir, exist_ok=True)
            self.db_path = os.path.join(db_dir, 'delphi_trades.db')
        else:
            self.db_path = db_path
        self.init_database()
    
    def _get_connection(self, timeout: float = 10.0) -> sqlite3.Connection:
        """재시도 로직이 있는 DB 연결 획득"""
        retry_count = 0
        max_retries = 3
        
        while retry_count < max_retries:
            try:
                conn = sqlite3.connect(self.db_path, timeout=timeout)
                conn.row_factory = sqlite3.Row
                return conn
            except sqlite3.OperationalError as e:
                retry_count += 1
                if retry_count >= max_retries:
                    logger.error(f"DB 연결 실패 (재시도 {max_retries}회 초과): {e}")
                    raise
                
                wait_time = retry_count * 0.5  # 0.5초, 1초, 1.5초
                logger.warning(f"DB 연결 재시도 {retry_count}/{max_retries} ({wait_time}초 대기): {e}")
                time.sleep(wait_time)
    
    def init_database(self):
        """데이터베이스 초기화 및 테이블 생성"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            
            # WAL 모드 활성화
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA temp_store=MEMORY")
            cursor.execute("PRAGMA mmap_size=268435456")  # 256MB
            
            # 거래 기록 테이블
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS trade_records (
                    trade_id TEXT PRIMARY KEY,
                    asset TEXT NOT NULL,
                    entry_price REAL NOT NULL,
                    exit_price REAL NOT NULL,
                    direction TEXT NOT NULL,
                    leverage REAL NOT NULL,
                    position_size_percent REAL NOT NULL,
                    entry_time TEXT NOT NULL,
                    exit_time TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    rr_ratio REAL NOT NULL,
                    pnl_percent REAL NOT NULL,
                    market_conditions TEXT NOT NULL,
                    agent_scores TEXT NOT NULL,
                    stop_loss_price REAL NOT NULL,
                    take_profit_price REAL NOT NULL,
                    max_drawdown_percent REAL NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Phase 3: 향상된 데이터 라벨링을 위한 컬럼 추가
            # SQLite는 IF NOT EXISTS를 ALTER TABLE에서 지원하지 않음
            try:
                cursor.execute("ALTER TABLE trade_records ADD COLUMN strategy_mode TEXT")
            except sqlite3.OperationalError:
                pass
            try:
                cursor.execute("ALTER TABLE trade_records ADD COLUMN timeframe_alignment TEXT")
            except sqlite3.OperationalError:
                pass
            try:
                cursor.execute("ALTER TABLE trade_records ADD COLUMN updated_at TEXT")
            except sqlite3.OperationalError:
                pass
            try:
                cursor.execute("ALTER TABLE trade_records ADD COLUMN conflict_narrative TEXT")
            except sqlite3.OperationalError:
                pass
            try:
                cursor.execute("ALTER TABLE trade_records ADD COLUMN volatility_at_entry REAL")
            except sqlite3.OperationalError:
                pass
            try:
                cursor.execute("ALTER TABLE trade_records ADD COLUMN market_regime TEXT")
            except sqlite3.OperationalError:
                pass
            # exploration_trade 제거됨 (시나리오 시스템으로 대체)
            # try:
            #     cursor.execute("ALTER TABLE trade_records ADD COLUMN exploration_trade BOOLEAN DEFAULT 0")
            # except sqlite3.OperationalError:
            #     pass
            try:
                cursor.execute("ALTER TABLE trade_records ADD COLUMN adaptive_thresholds TEXT")
            except sqlite3.OperationalError:
                pass
            try:
                cursor.execute("ALTER TABLE trade_records ADD COLUMN auto_lesson TEXT")
            except sqlite3.OperationalError:
                pass
            
            # ATR 기반 리스크 관리를 위한 새 컬럼들
            try:
                cursor.execute("ALTER TABLE trade_records ADD COLUMN time_to_stop_minutes INTEGER")
            except sqlite3.OperationalError:
                pass
            try:
                cursor.execute("ALTER TABLE trade_records ADD COLUMN stop_loss_type TEXT")  # NOISE, QUICK, NORMAL, LATE
            except sqlite3.OperationalError:
                pass
            try:
                cursor.execute("ALTER TABLE trade_records ADD COLUMN position_management_quality TEXT")  # GOOD, POOR
            except sqlite3.OperationalError:
                pass
            try:
                cursor.execute("ALTER TABLE trade_records ADD COLUMN atr_at_entry REAL")
            except sqlite3.OperationalError:
                pass
            try:
                cursor.execute("ALTER TABLE trade_records ADD COLUMN stop_distance_percent REAL")
            except sqlite3.OperationalError:
                pass
            
            # 시장 상황 분류 테이블 (유사성 검색용)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS market_classifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trade_id TEXT NOT NULL,
                    trend_type TEXT NOT NULL,  -- "UPTREND", "DOWNTREND", "SIDEWAYS"
                    volatility_level TEXT NOT NULL,  -- "HIGH", "MEDIUM", "LOW"
                    volume_profile TEXT NOT NULL,    -- "HIGH", "NORMAL", "LOW"
                    chartist_score INTEGER NOT NULL,
                    journalist_score INTEGER NOT NULL,
                    FOREIGN KEY (trade_id) REFERENCES trade_records (trade_id)
                )
            """)
            
            # 인덱스 생성 (쿼리 성능 개선)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_trade_created_at ON trade_records(created_at)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_trade_outcome ON trade_records(outcome)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_trade_asset_direction ON trade_records(asset, direction)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_trade_status ON trade_records(outcome) WHERE outcome = 'PENDING'")
            
            conn.commit()
            logger.debug("거래 데이터베이스 초기화 완료")
        except Exception as e:
            logger.error(f"DB 초기화 실패: {e}")
            raise
        finally:
            conn.close()
    
    def save_trade_record(self, trade: TradeRecord) -> bool:
        """거래 기록을 데이터베이스에 저장"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO trade_records (
                    trade_id, asset, entry_price, exit_price, direction, leverage,
                    position_size_percent, entry_time, exit_time, outcome, rr_ratio,
                    pnl_percent, market_conditions, agent_scores, stop_loss_price,
                    take_profit_price, max_drawdown_percent
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    trade.trade_id, trade.asset, trade.entry_price, trade.exit_price,
                    trade.direction, trade.leverage, trade.position_size_percent,
                    trade.entry_time, trade.exit_time, trade.outcome, trade.rr_ratio,
                    trade.pnl_percent, json.dumps(trade.market_conditions),
                    json.dumps(trade.agent_scores), trade.stop_loss_price,
                    trade.take_profit_price, trade.max_drawdown_percent
                ))
            
            # 시장 상황 분류도 저장
            market_classification = self._classify_market_conditions(trade)
            cursor.execute("""
                INSERT INTO market_classifications (
                    trade_id, trend_type, volatility_level, volume_profile,
                    chartist_score, journalist_score
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, market_classification)
            
            conn.commit()
            logger.debug(f"거래 기록 저장 완료: {trade.trade_id}")
            return True
                
        except Exception as e:
            logger.error(f"거래 기록 저장 실패: {e}")
            if conn:
                conn.rollback()
            return False
        finally:
            conn.close()
    
    def _classify_market_conditions(self, trade: TradeRecord) -> tuple:
        """거래 시점의 시장 상황을 분류하여 유사성 검색에 활용"""
        conditions = trade.market_conditions
        
        # 추세 분류
        chartist_score = trade.agent_scores.get('chartist_score', 50)
        if chartist_score >= 65:
            trend_type = "UPTREND"
        elif chartist_score <= 35:
            trend_type = "DOWNTREND"
        else:
            trend_type = "SIDEWAYS"
        
        # 변동성 분류 (ATR 기준)
        atr_value = conditions.get('atr_1h', 1.0)
        current_price = conditions.get('current_price', 100)
        atr_percent = (atr_value / current_price) * 100
        
        if atr_percent >= 2.0:
            volatility_level = "HIGH"
        elif atr_percent >= 1.0:
            volatility_level = "MEDIUM"
        else:
            volatility_level = "LOW"
        
        # 거래량 프로파일
        volume_ratio = conditions.get('volume_ratio', 1.0)
        if volume_ratio >= 1.5:
            volume_profile = "HIGH"
        elif volume_ratio >= 0.8:
            volume_profile = "NORMAL"
        else:
            volume_profile = "LOW"
        
        return (
            trade.trade_id, trend_type, volatility_level, volume_profile,
            chartist_score, trade.agent_scores.get('journalist_score', 5)
        )
    
    def label_completed_trade(self, trade_id: str) -> bool:
        """
        완료된 거래에 스마트 라벨 추가
        
        Args:
            trade_id: 거래 ID
            
        Returns:
            성공 여부
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            
            # 거래 데이터 가져오기
            cursor.execute("""
                SELECT entry_time, exit_time, entry_price, exit_price, 
                       stop_loss_price, pnl_percent, direction, leverage
                FROM trade_records 
                WHERE trade_id = ?
            """, (trade_id,))
            
            trade_data = cursor.fetchone()
            if not trade_data:
                logger.error(f"거래 기록을 찾을 수 없음: {trade_id}")
                return False
            
            (entry_time, exit_time, entry_price, exit_price, 
             stop_loss_price, pnl_percent, direction, leverage) = trade_data
            
            # 1. 거래 시간 계산
            entry_dt = datetime.fromisoformat(entry_time.replace('Z', '+00:00'))
            exit_dt = datetime.fromisoformat(exit_time.replace('Z', '+00:00'))
            time_to_stop_minutes = int((exit_dt - entry_dt).total_seconds() / 60)
            
            # 2. 손절 유형 판단
            if time_to_stop_minutes < 15:
                stop_loss_type = 'NOISE'  # 노이즈 손절
            elif time_to_stop_minutes < 30:
                stop_loss_type = 'QUICK'  # 빠른 손절
            elif time_to_stop_minutes < 120:
                stop_loss_type = 'NORMAL'  # 정상 손절
            else:
                stop_loss_type = 'LATE'   # 늦은 손절
            
            # 3. 포지션 관리 품질 평가
            # 손절가 준수 여부 확인
            if direction == 'LONG':
                followed_stop = exit_price <= stop_loss_price * 1.01
            else:  # SHORT
                followed_stop = exit_price >= stop_loss_price * 0.99
            
            position_management_quality = 'GOOD' if followed_stop else 'POOR'
            
            # 4. ATR 정보 대체
            atr_at_entry = None
            if entry_price and stop_loss_price:
                stop_distance_percent = abs(entry_price - stop_loss_price) / entry_price * 100
            else:
                stop_distance_percent = None
            
            # 5. 라벨 업데이트
            cursor.execute("""
                UPDATE trade_records 
                SET time_to_stop_minutes = ?,
                    stop_loss_type = ?,
                    position_management_quality = ?,
                    atr_at_entry = ?,
                    stop_distance_percent = ?
                WHERE trade_id = ?
            """, (time_to_stop_minutes, stop_loss_type, position_management_quality,
                  atr_at_entry, stop_distance_percent, trade_id))
            
            conn.commit()
            
            logger.debug(f"거래 라벨링 완료: {trade_id}")
            logger.debug(f"   - 거래 시간: {time_to_stop_minutes}분")
            logger.debug(f"   - 손절 유형: {stop_loss_type}")
            logger.debug(f"   - 포지션 관리: {position_management_quality}")
            
            return True
                
        except Exception as e:
            logger.error(f"거래 라벨링 실패: {e}")
            if conn:
                conn.rollback()
            return False
        finally:
            conn.close()
    
    def find_similar_trades(self, current_conditions: Dict, current_scores: Dict, 
                          limit: int = 10) -> List[Dict]:
        """현재 시장 상황과 유사한 과거 거래를 검색"""
        try:
            # 현재 상황 분류
            current_chartist = current_scores.get('chartist_score', 50)
            current_journalist = current_scores.get('journalist_score', 5)
            
            if current_chartist >= 65:
                trend_type = "UPTREND"
            elif current_chartist <= 35:
                trend_type = "DOWNTREND"
            else:
                trend_type = "SIDEWAYS"
            
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                
                # 유사한 시장 상황의 거래 검색
                query = """
                    SELECT tr.*, mc.trend_type, mc.volatility_level
                    FROM trade_records tr
                    JOIN market_classifications mc ON tr.trade_id = mc.trade_id
                    WHERE mc.trend_type = ?
                    AND ABS(mc.chartist_score - ?) <= 15
                    AND ABS(mc.journalist_score - ?) <= 2
                    ORDER BY tr.created_at DESC
                    LIMIT ?
                """
                
                cursor.execute(query, (trend_type, current_chartist, current_journalist, limit))
                results = cursor.fetchall()
                
                # 결과를 딕셔너리 형태로 변환
                columns = [desc[0] for desc in cursor.description]
                similar_trades = [dict(zip(columns, row)) for row in results]
                
                return similar_trades
                
            except Exception as e:
                logger.error(f"유사 거래 검색 실패: {e}")
                return []
            finally:
                conn.close()
                
        except Exception as e:
            logger.error(f"유사 거래 검색 초기화 실패: {e}")
            return []
    
    def get_performance_statistics(self, conditions: Dict = None) -> Dict:
        """전체 또는 특정 조건의 성과 통계를 계산"""
        try:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                
                # 기본 통계 쿼리
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total_trades,
                        AVG(CASE WHEN outcome IN ('WIN', 'TP_HIT') THEN 1.0 ELSE 0.0 END) as win_rate,
                        AVG(rr_ratio) as avg_rr_ratio,
                        AVG(pnl_percent) as avg_pnl_percent,
                        MAX(max_drawdown_percent) as max_drawdown
                    FROM trade_records
                """)
                
                result = cursor.fetchone()
                
                if result and result[0] > 0:  # 거래 기록이 있는 경우
                    # 표준편차를 수동으로 계산
                    cursor.execute("SELECT pnl_percent FROM trade_records")
                    pnl_values = [row[0] for row in cursor.fetchall()]
                    pnl_mean = result[3]
                    
                    if len(pnl_values) > 1:
                        variance = sum((x - pnl_mean) ** 2 for x in pnl_values) / len(pnl_values)
                        pnl_std = variance ** 0.5
                    else:
                        pnl_std = 0
                    
                    stats = {
                        'total_trades': result[0],
                        'win_rate_percent': round(result[1] * 100, 2),
                        'average_rr_ratio': round(result[2], 2),
                        'average_pnl_percent': round(result[3], 2),
                        'pnl_standard_deviation': round(pnl_std, 2),
                        'max_drawdown_percent': round(result[4] or 0, 2),
                        'evaluation': 'sufficient_data' if result[0] >= 10 else 'limited_data'
                    }
                    
                    # 기대값 계산: E = (승률 × 평균승률) - (패률 × 평균패률)
                    if result[0] >= 5:  # 최소 5개 거래 이상
                        cursor.execute("""
                            SELECT AVG(pnl_percent) FROM trade_records WHERE outcome = 'WIN'
                        """)
                        avg_win = cursor.fetchone()[0] or 0
                        
                        cursor.execute("""
                            SELECT AVG(ABS(pnl_percent)) FROM trade_records WHERE outcome = 'LOSS'
                        """)
                        avg_loss = cursor.fetchone()[0] or 0
                        
                        expectancy = (result[1] * avg_win) - ((1 - result[1]) * avg_loss)
                        stats['expectancy'] = round(expectancy, 2)
                    else:
                        stats['expectancy'] = 0.0
                    
                    return stats
                else:
                    # 거래 기록이 없는 경우 기본값 반환
                    return self._get_default_statistics()
                    
            except Exception as e:
                logger.error(f"성과 통계 계산 실패: {e}")
                return self._get_default_statistics()
            finally:
                conn.close()
                
        except Exception as e:
            logger.error(f"성과 통계 초기화 실패: {e}")
            return self._get_default_statistics()
    
    def _get_default_statistics(self) -> Dict:
        """거래 기록이 없을 때 사용할 기본 통계값"""
        return {
            'total_trades': 0,
            'win_rate_percent': 45.0,  # 보수적 기본값
            'average_rr_ratio': 1.3,   # 보수적 기본값
            'average_pnl_percent': 0.0,
            'pnl_standard_deviation': 0.0,
            'max_drawdown_percent': 0.0,
            'expectancy': 0.1,  # 실제 트레이더 기준: 양수면 충분 (순환논리 해결)
            'evaluation': 'insufficient_data'
        }
    
    def get_trade_count(self) -> int:
        """총 거래 건수 반환"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM trade_records")
            return cursor.fetchone()[0]
        except Exception as e:
            logger.error(f"거래 수 조회 실패: {e}")
            return 0
        finally:
            conn.close()
    
    def get_outcome_statistics(self) -> Dict:
        """outcome별 상세 통계 반환"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            
            # outcome별 분포
            cursor.execute("""
                    SELECT 
                        outcome,
                        COUNT(*) as count,
                        COUNT(*) * 100.0 / (SELECT COUNT(*) FROM trade_records) as percentage,
                        AVG(pnl_percent) as avg_pnl
                    FROM trade_records
                    GROUP BY outcome
                """)
            
            outcome_stats = {}
            for row in cursor.fetchall():
                outcome, count, percentage, avg_pnl = row
                outcome_stats[outcome] = {
                    'count': count,
                    'percentage': round(percentage, 1),
                    'avg_pnl': round(avg_pnl, 2)
                }
            
            # 추가 분석
            analysis = {
                'tp_efficiency': outcome_stats.get('TP_HIT', {}).get('percentage', 0),
                'sl_efficiency': outcome_stats.get('SL_HIT', {}).get('percentage', 0),
                'time_exit_rate': outcome_stats.get('TIME_EXIT', {}).get('percentage', 0),
                'manual_exit_rate': outcome_stats.get('MANUAL_EXIT', {}).get('percentage', 0)
            }
            
            # 분석 메시지
            messages = []
            if analysis['tp_efficiency'] > 70:
                messages.append("익절 목표가가 너무 보수적일 수 있습니다")
            elif analysis['tp_efficiency'] < 30:
                messages.append("익절 목표가가 너무 공격적일 수 있습니다")
                
            if analysis['sl_efficiency'] > 60:
                messages.append("손절선이 너무 타이트할 수 있습니다")
                
            if analysis['time_exit_rate'] > 30:
                messages.append("포지션 보유 시간이 너무 길 수 있습니다")
                
            return {
                'outcome_distribution': outcome_stats,
                'analysis': analysis,
                'recommendations': messages
            }
            
        except Exception as e:
            logger.error(f"Outcome 통계 계산 실패: {e}")
            return {}
        finally:
            conn.close()
    
    def save_trade_with_metadata(self, trade_data: Dict, agent_signals: Dict) -> bool:
        """
        Phase 1: 거래 시 각 에이전트 신호와 시장 상태도 함께 저장
        
        Args:
            trade_data: 기본 거래 정보
            agent_signals: 각 에이전트의 신호 정보
            
        Returns:
            저장 성공 여부
        """
        try:
            # 기존 trade_data에 메타데이터 추가
            enhanced_data = {
                **trade_data,
                'metadata': {
                    'chartist_confidence': agent_signals.get('chartist', {}).get('confidence', 0),
                    'chartist_trend': agent_signals.get('chartist', {}).get('technical_indicators', {}).get('trend_direction', ''),
                    'chartist_key_levels': agent_signals.get('chartist', {}).get('key_levels', {}),
                    
                    'journalist_sentiment': agent_signals.get('journalist', {}).get('sentiment_analysis', {}).get('overall_sentiment', ''),
                    'journalist_impact': agent_signals.get('journalist', {}).get('impact_assessment', {}).get('market_impact', ''),
                    'journalist_events': agent_signals.get('journalist', {}).get('key_events', []),
                    
                    'quant_strength': agent_signals.get('quant', {}).get('quantitative_scorecard', {}).get('overall_score', 0),
                    'quant_momentum': agent_signals.get('quant', {}).get('technical_assessment', {}).get('momentum_status', ''),
                    'quant_volume': agent_signals.get('quant', {}).get('volume_analysis', {}).get('interpretation', ''),
                    
                    'stoic_risk_score': agent_signals.get('stoic', {}).get('risk_assessment', {}).get('overall_risk_score', 0),
                    'stoic_risk_factors': agent_signals.get('stoic', {}).get('risk_factors', []),
                    
                    'synthesizer_decision': agent_signals.get('synthesizer', {}).get('final_decision', {}).get('decision', ''),
                    'synthesizer_confidence': agent_signals.get('synthesizer', {}).get('final_decision', {}).get('confidence', 0),
                    
                    'market_volatility': self._get_current_volatility(),
                    'timestamp': datetime.now().isoformat()
                }
            }
            
            # TradeRecord 형식으로 변환
            trade_record = TradeRecord(
                trade_id=enhanced_data.get('trade_id'),
                asset=enhanced_data.get('asset'),
                entry_price=enhanced_data.get('entry_price'),
                exit_price=enhanced_data.get('exit_price', 0),
                direction=enhanced_data.get('direction'),
                leverage=enhanced_data.get('leverage', 1),
                position_size_percent=enhanced_data.get('position_size_percent', 5),
                entry_time=enhanced_data.get('entry_time'),
                exit_time=enhanced_data.get('exit_time', ''),
                outcome=enhanced_data.get('outcome', 'PENDING'),
                rr_ratio=enhanced_data.get('rr_ratio', 0),
                pnl_percent=enhanced_data.get('pnl_percent', 0),
                market_conditions=enhanced_data.get('market_conditions', {}),
                agent_scores=enhanced_data.get('agent_scores', {}),
                stop_loss_price=enhanced_data.get('stop_loss_price', 0),
                take_profit_price=enhanced_data.get('take_profit_price', 0),
                max_drawdown_percent=enhanced_data.get('max_drawdown_percent', 0)
            )
            
            # 메타데이터를 agent_scores에 포함
            trade_record.agent_scores['metadata'] = enhanced_data['metadata']
            
            # 거래 저장
            result = self.save_trade_record(trade_record)
            
            if result:
                logger.debug(f"✅ 상세 메타데이터 포함 거래 저장 완료: {trade_record.trade_id}")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ 메타데이터 포함 거래 저장 실패: {e}")
            return False
    
    def _get_current_volatility(self) -> float:
        """현재 시장 변동성 계산 (간단한 버전)"""
        try:
            # 실제로는 binance_connector에서 가져와야 하지만
            # 여기서는 간단히 처리
            return 0.0
        except:
            return 0.0
    
    def save_trade(self, trade_data: Dict) -> bool:
        """
        add_trade_record의 호환성 래퍼
        trade_executor 등에서 호출하는 save_trade 메서드 지원
        """
        try:
            logger.debug(f"[DEBUG] save_trade 호출됨: {trade_data.get('trade_id', 'NO_ID')}")
            # trade_data를 TradeRecord 형식으로 변환
            trade_record = self._convert_to_trade_record(trade_data)
            result = self.save_trade_record(trade_record)
            logger.debug(f"[DEBUG] save_trade 결과: {result}")
            return result
        except Exception as e:
            logger.error(f"[DEBUG] 거래 저장 실패: {e}", exc_info=True)
            return False
    
    def _convert_to_trade_record(self, trade_data: Dict) -> TradeRecord:
        """딕셔너리 형태의 거래 데이터를 TradeRecord 객체로 변환"""
        try:
            # 필수 필드 검증
            trade_id = trade_data.get('trade_id') or generate_trade_id()
            asset = trade_data.get('symbol') or trade_data.get('asset', 'SOLUSDT')
            
            # direction 처리 (action -> direction 변환)
            direction = trade_data.get('direction')
            if not direction:
                action = trade_data.get('action', '')
                if action == 'BUY':
                    direction = 'LONG'
                elif action == 'SELL':
                    direction = 'SHORT'
                else:
                    direction = 'LONG'  # 기본값
            
            # TradeRecord 생성
            return TradeRecord(
                trade_id=trade_id,
                asset=asset,
                entry_price=trade_data.get('entry_price', 0),
                exit_price=trade_data.get('exit_price', 0),
                direction=direction,
                leverage=trade_data.get('leverage', 1),
                position_size_percent=trade_data.get('position_size_percent', 5),
                entry_time=trade_data.get('entry_time', datetime.now(timezone.utc).isoformat()),
                exit_time=trade_data.get('exit_time', ''),
                outcome=trade_data.get('outcome', 'PENDING'),
                rr_ratio=trade_data.get('rr_ratio', 0),
                pnl_percent=trade_data.get('pnl_percent', 0),
                market_conditions=trade_data.get('market_conditions', {}),
                agent_scores=trade_data.get('agent_scores', {}),
                stop_loss_price=trade_data.get('stop_loss_price', 0),
                take_profit_price=trade_data.get('take_profit_price', 0),
                max_drawdown_percent=trade_data.get('max_drawdown_percent', 0)
            )
        except Exception as e:
            logger.error(f"TradeRecord 변환 실패: {e}")
            raise
    
    def cleanup_old_pending_trades(self, days: int = 7) -> int:
        """오래된 PENDING 거래 정리"""
        try:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                
                # 지정된 일수보다 오래된 PENDING 거래 삭제
                cutoff_date = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
                
                logger.debug(f"[DEBUG] PENDING 거래 정리 시작: {days}일 이전 (cutoff: {cutoff_date})")
                
                # trade_records 테이블에서 outcome이 PENDING인 것들 삭제
                cursor.execute("""
                    DELETE FROM trade_records 
                    WHERE outcome = 'PENDING' 
                    AND entry_time < ?
                """, (cutoff_date,))
                
                deleted_count = cursor.rowcount
                conn.commit()
                
                if deleted_count > 0:
                    logger.debug(f"[DEBUG] {deleted_count}개의 오래된 PENDING 거래 정리 완료")
                else:
                    logger.debug("[DEBUG] 정리할 PENDING 거래 없음")
                
                return deleted_count
                
            except Exception as e:
                logger.error(f"[DEBUG] PENDING 거래 정리 실패: {e}", exc_info=True)
                if conn:
                    conn.rollback()
                return 0
            finally:
                conn.close()
                
        except Exception as e:
            logger.error(f"[DEBUG] PENDING 거래 정리 초기화 실패: {e}")
            return 0

# 전역 데이터베이스 인스턴스
# 경로 문제 해결을 위해 lazy initialization 사용
_trade_db = None

def get_trade_db():
    """전역 TradeDatabase 인스턴스 반환 (lazy initialization)"""
    global _trade_db
    if _trade_db is None:
        # 데이터베이스 디렉토리 확인 및 생성
        import os
        db_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'data', 'database')
        os.makedirs(db_dir, exist_ok=True)
        _trade_db = TradeDatabase()
    return _trade_db

# 하위 호환성을 위한 프록시 객체
class TradeDBProxy:
    def __getattr__(self, name):
        return getattr(get_trade_db(), name)

trade_db = TradeDBProxy()

def get_trade_details(trade_id: str) -> Optional[Dict]:
    """거래 상세 정보 조회 (일일 리포터용)"""
    try:
        # 실제 구현시 데이터베이스에서 조회
        # 현재는 기본 구조만 반환
        return {
            'trade_id': trade_id,
            'timestamp': datetime.now().isoformat(),
            'symbol': 'SOLUSDT',
            'direction': 'BUY',
            'realized_pnl': 0,
            'realized_pnl_percent': 0,
            'analysis': {}
        }
    except Exception as e:
        logger.error(f"거래 상세 정보 조회 실패: {e}")
        return None

def generate_trade_id() -> str:
    """고유한 거래 ID 생성"""
    return f"DELPHI_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"

def save_completed_trade(entry_data: Dict, exit_data: Dict, agent_reports: Dict, exit_reason: str = None) -> bool:
    """
    완료된 거래를 데이터베이스에 저장하는 헬퍼 함수
    
    Args:
        exit_reason: 'TP_HIT', 'SL_HIT', 'TIME_EXIT', 'MANUAL_EXIT'
    """
    try:
        trade_db = TradeDatabase()
        trade_id = entry_data.get('trade_id', generate_trade_id())
        
        # 먼저 PENDING 거래가 있는지 확인
        existing_trade = trade_db.get_trade_by_id(trade_id)
        if existing_trade and existing_trade.get('status') == 'PENDING':
            # PENDING 거래 업데이트
            update_data = {
                'exit_price': exit_data['price'],
                'exit_time': exit_data['timestamp'],
                'realized_pnl': 0,  # 아래에서 계산됨
                'status': exit_reason or 'COMPLETED',
                'exit_reason': exit_reason or '',
                'holding_time': 0  # 아래에서 계산될 수 있음
            }
            
            # PnL 계산
            entry_price = existing_trade['entry_price']
            exit_price = exit_data['price']
            direction = existing_trade['side']
            
            if direction == "LONG":
                pnl_percent = ((exit_price - entry_price) / entry_price) * 100
            else:  # SHORT
                pnl_percent = ((entry_price - exit_price) / entry_price) * 100
            
            # 레버리지 적용
            pnl_percent *= existing_trade.get('leverage', 1)
            update_data['realized_pnl'] = pnl_percent
            
            # 거래 업데이트
            return trade_db.update_trade(trade_id, update_data)
        # P&L 계산
        entry_price = entry_data['price']
        exit_price = exit_data['price']
        direction = entry_data['direction']
        
        if direction == "LONG":
            pnl_percent = ((exit_price - entry_price) / entry_price) * 100
        else:  # SHORT
            pnl_percent = ((entry_price - exit_price) / entry_price) * 100
        
        # 레버리지 적용
        pnl_percent *= entry_data['leverage']
        
        # 거래 결과 결정 (세분화)
        if exit_reason:
            outcome = exit_reason  # 명시적으로 전달된 종료 사유
        else:
            # 가격으로 종료 사유 추정
            tp_price = entry_data.get('take_profit', 0)
            sl_price = entry_data.get('stop_loss', 0)
            
            # 1% 오차 범위로 판별
            if tp_price > 0 and abs(exit_price - tp_price) / tp_price < 0.01:
                outcome = "TP_HIT"
            elif sl_price > 0 and abs(exit_price - sl_price) / sl_price < 0.01:
                outcome = "SL_HIT"
            else:
                # P&L로 폴백 (기존 호환성 유지)
                if pnl_percent > 0:
                    outcome = "WIN"  # 수익이지만 TP 도달 안 함
                else:
                    outcome = "LOSS"  # 손실이지만 SL 도달 안 함
        
        # R:R 비율 계산
        risk_percent = abs((entry_price - entry_data['stop_loss']) / entry_price) * 100
        reward_percent = abs(pnl_percent)
        rr_ratio = reward_percent / risk_percent if risk_percent > 0 else 0
        
        # TradeRecord 생성
        trade = TradeRecord(
            trade_id=generate_trade_id(),
            asset=entry_data['asset'],
            entry_price=entry_price,
            exit_price=exit_price,
            direction=direction,
            leverage=entry_data['leverage'],
            position_size_percent=entry_data['position_size_percent'],
            entry_time=entry_data['timestamp'],
            exit_time=exit_data['timestamp'],
            outcome=outcome,
            rr_ratio=rr_ratio,
            pnl_percent=pnl_percent,
            market_conditions=entry_data['market_conditions'],
            agent_scores=entry_data['agent_scores'],
            stop_loss_price=entry_data['stop_loss'],
            take_profit_price=entry_data['take_profit'],
            max_drawdown_percent=exit_data.get('max_drawdown', 0.0)
        )
        
        return trade_db.save_trade_record(trade)
        
    except Exception as e:
        logger.error(f"❌ 거래 저장 중 오류: {e}")
        return False

def get_trade_history(limit=100):
    """Get recent trade history"""
    try:
        trade_db = TradeDatabase()
        
        with sqlite3.connect(trade_db.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT * FROM trade_records 
                ORDER BY entry_time DESC 
                LIMIT ?
            """, (limit,))
            
            columns = [desc[0] for desc in cursor.description]
            trades = [dict(zip(columns, row)) for row in cursor.fetchall()]
            
            return trades
            
    except Exception as e:
        logger.error(f"Error getting trade history: {e}")
        return []


# EnhancedTradeDatabase 클래스는 시나리오 학습 시스템으로 대체되어 제거됨
    """Phase 3: 향상된 거래 데이터베이스"""
    
    def save_enhanced_record(self, trade_data: Dict, decision_context: Dict) -> bool:
        """향상된 거래 기록 저장"""
        try:
            # 자동 교훈 생성
            lesson = self._generate_auto_lesson(trade_data, decision_context)
            
            # 시장 체제 분류
            market_regime = self._classify_market_regime(decision_context)
            
            # 향상된 데이터 구성
            enhanced_data = {
                **trade_data,
                'strategy_mode': decision_context.get('strategy', {}).get('mode'),
                'timeframe_alignment': decision_context.get('timeframe_signals', {}).get('strongest_timeframe'),
                'conflict_narrative': decision_context.get('narrative', ''),
                'volatility_at_entry': decision_context.get('market_data', {}).get('volatility', 0),
                'market_regime': market_regime,
                # 'exploration_trade': 제거됨 (시나리오 시스템으로 대체)
                'adaptive_thresholds': json.dumps(decision_context.get('thresholds', {})),
                'auto_lesson': lesson
            }
            
            # 기본 TradeRecord 생성
            trade = TradeRecord(
                trade_id=enhanced_data.get('trade_id', generate_trade_id()),
                asset=enhanced_data.get('asset', 'SOLUSDT'),
                entry_price=enhanced_data.get('entry_price'),
                exit_price=enhanced_data.get('exit_price', 0),
                direction=enhanced_data.get('direction'),
                leverage=enhanced_data.get('leverage', 1),
                position_size_percent=enhanced_data.get('position_size_percent', 5),
                entry_time=enhanced_data.get('entry_time', datetime.now().isoformat()),
                exit_time=enhanced_data.get('exit_time', ''),
                outcome=enhanced_data.get('outcome', 'PENDING'),
                rr_ratio=enhanced_data.get('rr_ratio', 0),
                pnl_percent=enhanced_data.get('pnl_percent', 0),
                market_conditions=enhanced_data.get('market_conditions', {}),
                agent_scores=enhanced_data.get('agent_scores', {}),
                stop_loss_price=enhanced_data.get('stop_loss_price', 0),
                take_profit_price=enhanced_data.get('take_profit_price', 0),
                max_drawdown_percent=enhanced_data.get('max_drawdown_percent', 0)
            )
            
            # 향상된 필드들을 별도로 저장
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                
                # 먼저 기본 레코드 저장
                self.save_trade_record(trade)
                
                # 향상된 필드 업데이트
                cursor.execute("""
                    UPDATE trade_records 
                    SET strategy_mode = ?,
                        timeframe_alignment = ?,
                        conflict_narrative = ?,
                        volatility_at_entry = ?,
                        market_regime = ?,
                        adaptive_thresholds = ?,
                        auto_lesson = ?
                    WHERE trade_id = ?
                """, (
                    enhanced_data['strategy_mode'],
                    enhanced_data['timeframe_alignment'],
                    enhanced_data['conflict_narrative'],
                    enhanced_data['volatility_at_entry'],
                    enhanced_data['market_regime'],
                    enhanced_data['adaptive_thresholds'],
                    enhanced_data['auto_lesson'],
                    trade.trade_id
                ))
                
                conn.commit()
                
                logger.debug(f"✅ 향상된 거래 기록 저장 완료: {trade.trade_id}")
                return True
            finally:
                conn.close()
            
        except Exception as e:
            logger.error(f"❌ 향상된 거래 기록 저장 실패: {e}")
            return False
    
    def _generate_auto_lesson(self, result: Dict, context: Dict) -> str:
        """자동 교훈 생성"""
        outcome = result.get('outcome', 'PENDING')
        strategy_mode = context.get('strategy', {}).get('mode', 'UNKNOWN')
        volatility = context.get('market_data', {}).get('volatility', 0)
        
        if outcome == 'WIN':
            if strategy_mode == 'SHORT_TERM':
                return f"변동성 {volatility:.1f}% + TF 괴리 시 단기 반전 성공"
            elif strategy_mode == 'SWING':
                return f"스윙 전략 성공, 변동성 {volatility:.1f}%"
            elif strategy_mode == 'POSITION':
                return f"포지션 트레이딩 성공, 추세 추종 효과적"
            else:
                return f"{strategy_mode} 전략 성공"
        elif outcome == 'LOSS':
            return f"{strategy_mode} 전략 실패, 원인 분석 필요"
        else:
            return "거래 진행 중"
    
    def _classify_market_regime(self, context: Dict) -> str:
        """시장 체제 분류"""
        volatility = context.get('market_data', {}).get('volatility', 0)
        trend_strength = context.get('market_data', {}).get('trend_strength', 0)
        
        if volatility > 5:
            return "HIGH_VOLATILITY"
        elif volatility < 2:
            return "LOW_VOLATILITY"
        elif trend_strength > 70:
            return "STRONG_TREND"
        elif trend_strength < 30:
            return "RANGE_BOUND"
        else:
            return "NORMAL"
    
    def find_similar_enhanced_trades(self, similarity_criteria: Dict, limit: int = 5) -> List[Dict]:
        """향상된 유사 거래 검색"""
        try:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                
                # 유사 거래 검색 쿼리
                query = """
                    SELECT * FROM trade_records
                    WHERE market_regime = ?
                    AND ABS(volatility_at_entry - ?) <= ?
                    ORDER BY created_at DESC
                    LIMIT ?
                """
                
                cursor.execute(query, (
                    similarity_criteria.get('market_regime', 'NORMAL'),
                    similarity_criteria.get('volatility_range', [0, 0])[0],
                    similarity_criteria.get('volatility_range', [0, 0])[1] - similarity_criteria.get('volatility_range', [0, 0])[0],
                    limit
                ))
                
                columns = [desc[0] for desc in cursor.description]
                trades = [dict(zip(columns, row)) for row in cursor.fetchall()]
                
                # JSON 필드 파싱
                for trade in trades:
                    if trade.get('market_conditions'):
                        trade['market_conditions'] = json.loads(trade['market_conditions'])
                    if trade.get('agent_scores'):
                        trade['agent_scores'] = json.loads(trade['agent_scores'])
                    if trade.get('adaptive_thresholds'):
                        trade['adaptive_thresholds'] = json.loads(trade['adaptive_thresholds'])
                
                return trades
            finally:
                conn.close()
                
        except Exception as e:
            logger.error(f"❌ 향상된 유사 거래 검색 실패: {e}")
            return []
    
    
    def save_trade(self, trade_data: Dict) -> bool:
        """
        add_trade_record의 호환성 래퍼
        trade_executor 등에서 호출하는 save_trade 메서드 지원
        """
        try:
            logger.debug(f"[DEBUG] save_trade 호출됨: {trade_data.get('trade_id', 'NO_ID')}")
            # trade_data를 TradeRecord 형식으로 변환
            trade_record = self._convert_to_trade_record(trade_data)
            result = self.save_trade_record(trade_record)
            logger.debug(f"[DEBUG] save_trade 결과: {result}")
            return result
        except Exception as e:
            logger.error(f"[DEBUG] 거래 저장 실패: {e}", exc_info=True)
            return False
    
    def _convert_to_trade_record(self, trade_data: Dict) -> TradeRecord:
        """딕셔너리 형태의 거래 데이터를 TradeRecord 객체로 변환"""
        try:
            # 필수 필드 검증
            trade_id = trade_data.get('trade_id') or generate_trade_id()
            asset = trade_data.get('symbol') or trade_data.get('asset', 'SOLUSDT')
            
            # direction 처리 (action -> direction 변환)
            direction = trade_data.get('direction')
            if not direction:
                action = trade_data.get('action', '')
                if action == 'BUY':
                    direction = 'LONG'
                elif action == 'SELL':
                    direction = 'SHORT'
                else:
                    direction = 'LONG'  # 기본값
            
            # TradeRecord 생성
            return TradeRecord(
                trade_id=trade_id,
                asset=asset,
                entry_price=trade_data.get('entry_price', 0),
                exit_price=trade_data.get('exit_price', 0),
                direction=direction,
                leverage=trade_data.get('leverage', 1),
                position_size_percent=trade_data.get('position_size_percent', 5),
                entry_time=trade_data.get('entry_time', datetime.now(timezone.utc).isoformat()),
                exit_time=trade_data.get('exit_time', ''),
                outcome=trade_data.get('outcome', 'PENDING'),
                rr_ratio=trade_data.get('rr_ratio', 0),
                pnl_percent=trade_data.get('pnl_percent', 0),
                market_conditions=trade_data.get('market_conditions', {}),
                agent_scores=trade_data.get('agent_scores', {}),
                stop_loss_price=trade_data.get('stop_loss_price', 0),
                take_profit_price=trade_data.get('take_profit_price', 0),
                max_drawdown_percent=trade_data.get('max_drawdown_percent', 0)
            )
        except Exception as e:
            logger.error(f"TradeRecord 변환 실패: {e}")
            raise
    
    def cleanup_old_pending_trades(self, days: int = 7) -> int:
        """오래된 PENDING 거래 정리"""
        try:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                
                # 지정된 일수보다 오래된 PENDING 거래 삭제
                cutoff_date = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
                
                logger.debug(f"[DEBUG] PENDING 거래 정리 시작: {days}일 이전 (cutoff: {cutoff_date})")
                
                # trade_records 테이블에서 outcome이 PENDING인 것들 삭제
                cursor.execute("""
                    DELETE FROM trade_records 
                    WHERE outcome = 'PENDING' 
                    AND entry_time < ?
                """, (cutoff_date,))
                
                deleted_count = cursor.rowcount
                conn.commit()
                
                if deleted_count > 0:
                    logger.debug(f"[DEBUG] {deleted_count}개의 오래된 PENDING 거래 정리 완료")
                else:
                    logger.debug("[DEBUG] 정리할 PENDING 거래 없음")
                
                return deleted_count
                
            except Exception as e:
                logger.error(f"[DEBUG] PENDING 거래 정리 실패: {e}", exc_info=True)
                if conn:
                    conn.rollback()
                return 0
            finally:
                conn.close()
                
        except Exception as e:
            logger.error(f"[DEBUG] PENDING 거래 정리 초기화 실패: {e}")
            return 0
    
    def get_trade_by_id(self, trade_id: str) -> Optional[Dict]:
        """거래 ID로 거래 정보 조회"""
        try:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM trade_records WHERE trade_id = ?", (trade_id,))
                row = cursor.fetchone()
                
                if row:
                    columns = [desc[0] for desc in cursor.description]
                    trade_dict = dict(zip(columns, row))
                    
                    # JSON 필드 파싱
                    if trade_dict.get('market_conditions'):
                        try:
                            trade_dict['market_conditions'] = json.loads(trade_dict['market_conditions'])
                        except:
                            pass
                    if trade_dict.get('agent_scores'):
                        try:
                            trade_dict['agent_scores'] = json.loads(trade_dict['agent_scores'])
                        except:
                            pass
                    
                    return trade_dict
                return None
            finally:
                conn.close()
                
        except Exception as e:
            logger.error(f"거래 조회 실패: {e}")
            return None
    
    def update_trade(self, trade_id: str, update_data: Dict) -> bool:
        """거래 정보 업데이트"""
        try:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                
                # 업데이트할 필드와 값 준비
                fields = []
                values = []
                for key, value in update_data.items():
                    fields.append(f"{key} = ?")
                    values.append(value)
                
                # updated_at 추가
                fields.append("updated_at = ?")
                values.append(datetime.now(timezone.utc).isoformat())
                
                # trade_id를 마지막에 추가
                values.append(trade_id)
                
                query = f"UPDATE trade_records SET {', '.join(fields)} WHERE trade_id = ?"
                cursor.execute(query, values)
                conn.commit()
                
                logger.debug(f"거래 업데이트 완료: {trade_id}")
                return True
                
            except Exception as e:
                logger.error(f"거래 업데이트 실패: {e}")
                if conn:
                    conn.rollback()
                return False
            finally:
                conn.close()
                
        except Exception as e:
            logger.error(f"거래 업데이트 초기화 실패: {e}")
            return False

# 전역 향상된 데이터베이스 인스턴스 제거 (시나리오 시스템으로 대체됨)
# enhanced_trade_db = EnhancedTradeDatabase()