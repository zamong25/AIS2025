"""
델파이 트레이딩 시스템 - 거래 성과 분석 모듈
거래 완료 후 성공/실패 원인을 분석하여 학습 데이터로 활용
"""

import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional
from dataclasses import dataclass
from utils.openai_client import openai_client

@dataclass
class TradeAnalysis:
    """거래 분석 결과를 나타내는 데이터 클래스"""
    trade_id: str
    analysis_type: str  # "SUCCESS" or "FAILURE" 
    key_factors: List[str]  # 주요 성공/실패 요인
    agent_accuracy: Dict  # 각 에이전트 예측 정확도
    market_factor_impact: Dict  # 시장 요인별 영향도
    lessons_learned: str  # 학습된 교훈
    confidence_score: float  # 분석 신뢰도
    timestamp: str

class TradeAnalyzer:
    """거래 성과 분석기"""
    
    def __init__(self):
        self.logger = logging.getLogger('TradeAnalyzer')
    
    def analyze_completed_trade(self, trade_data: Dict, agent_reports: Dict) -> Optional[TradeAnalysis]:
        """
        완료된 거래를 분석하여 성공/실패 원인 파악
        
        Args:
            trade_data: 거래 완료 데이터 (진입/청산 정보 포함)
            agent_reports: 거래 당시 4개 에이전트 보고서
            
        Returns:
            TradeAnalysis 객체 또는 None
        """
        try:
            self.logger.info(f"📊 거래 성과 분석 시작: {trade_data.get('trade_id', 'UNKNOWN')}")
            
            # 성공/실패 여부 판단
            pnl_percent = trade_data.get('pnl_percent', 0)
            analysis_type = "SUCCESS" if pnl_percent > 0 else "FAILURE"
            
            # AI 분석 프롬프트 준비
            analysis_prompt = self._prepare_analysis_prompt(trade_data, agent_reports, analysis_type)
            
            # AI 분석 실행
            analysis_result = openai_client.invoke_agent_json("gpt-4o", analysis_prompt)
            
            if not analysis_result:
                self.logger.error("❌ AI 분석 실패")
                return None
            
            # TradeAnalysis 객체 생성
            trade_analysis = TradeAnalysis(
                trade_id=trade_data.get('trade_id', 'UNKNOWN'),
                analysis_type=analysis_type,
                key_factors=analysis_result.get('key_factors', []),
                agent_accuracy=analysis_result.get('agent_accuracy', {}),
                market_factor_impact=analysis_result.get('market_factor_impact', {}),
                lessons_learned=analysis_result.get('lessons_learned', ''),
                confidence_score=analysis_result.get('confidence_score', 0),
                timestamp=datetime.now(timezone.utc).isoformat()
            )
            
            self.logger.info(f"✅ 거래 분석 완료: {analysis_type} (신뢰도: {trade_analysis.confidence_score}%)")
            
            # 분석 결과를 별도 테이블에 저장
            self._save_analysis_to_db(trade_analysis)
            
            return trade_analysis
            
        except Exception as e:
            self.logger.error(f"❌ 거래 분석 실패: {e}")
            return None
    
    def _prepare_analysis_prompt(self, trade_data: Dict, agent_reports: Dict, analysis_type: str) -> str:
        """거래 분석용 AI 프롬프트 생성"""
        
        prompt_template = f"""
당신은 트레이딩 성과 분석 전문가입니다. 완료된 거래를 분석하여 {analysis_type.lower()} 원인을 파악하고 학습 가능한 인사이트를 제공해주세요.

## 거래 데이터
{json.dumps(trade_data, ensure_ascii=False, indent=2)}

## 거래 당시 에이전트 보고서
{json.dumps(agent_reports, ensure_ascii=False, indent=2)}

## 분석 요청사항
1. **주요 {analysis_type.lower()} 요인 3-5개 식별**
2. **각 에이전트 예측의 정확도 평가 (0-100점)**
3. **시장 요인별 영향도 분석**
4. **향후 유사 상황에서의 교훈**

다음 JSON 형식으로 응답해주세요:

{{
  "key_factors": [
    "구체적인 성공/실패 요인 1",
    "구체적인 성공/실패 요인 2",
    "구체적인 성공/실패 요인 3"
  ],
  "agent_accuracy": {{
    "chartist": 85,
    "journalist": 70,
    "quant": 90,
    "stoic": 75
  }},
  "market_factor_impact": {{
    "technical_signals": 40,
    "fundamental_news": 30,
    "market_sentiment": 20,
    "external_events": 10
  }},
  "lessons_learned": "향후 유사한 상황에서 적용할 수 있는 구체적인 교훈과 개선점",
  "confidence_score": 85
}}
"""
        return prompt_template.strip()
    
    def _save_analysis_to_db(self, analysis: TradeAnalysis) -> bool:
        """분석 결과를 데이터베이스에 저장"""
        try:
            import sqlite3
            
            # 데이터베이스 경로 (기존 trade_database와 동일한 DB 사용)
            db_path = "data/database/delphi_trades.db"
            
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                
                # 분석 결과 테이블 생성 (존재하지 않을 경우)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS trade_analyses (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        trade_id TEXT NOT NULL,
                        analysis_type TEXT NOT NULL,
                        key_factors TEXT NOT NULL,
                        agent_accuracy TEXT NOT NULL,
                        market_factor_impact TEXT NOT NULL,
                        lessons_learned TEXT NOT NULL,
                        confidence_score REAL NOT NULL,
                        timestamp TEXT NOT NULL,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (trade_id) REFERENCES trade_records (trade_id)
                    )
                """)
                
                # 분석 결과 저장
                cursor.execute("""
                    INSERT INTO trade_analyses (
                        trade_id, analysis_type, key_factors, agent_accuracy,
                        market_factor_impact, lessons_learned, confidence_score, timestamp
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    analysis.trade_id,
                    analysis.analysis_type,
                    json.dumps(analysis.key_factors, ensure_ascii=False),
                    json.dumps(analysis.agent_accuracy, ensure_ascii=False),
                    json.dumps(analysis.market_factor_impact, ensure_ascii=False),
                    analysis.lessons_learned,
                    analysis.confidence_score,
                    analysis.timestamp
                ))
                
                conn.commit()
                self.logger.info(f"✅ 거래 분석 결과 DB 저장 완료: {analysis.trade_id}")
                return True
                
        except Exception as e:
            self.logger.error(f"❌ 분석 결과 DB 저장 실패: {e}")
            return False
    
    def get_similar_trade_lessons(self, current_conditions: Dict, limit: int = 5) -> List[Dict]:
        """
        현재 상황과 유사한 과거 거래의 교훈 조회
        
        Args:
            current_conditions: 현재 시장 상황
            limit: 조회할 최대 건수
            
        Returns:
            유사한 거래의 분석 결과 리스트
        """
        try:
            import sqlite3
            
            db_path = "data/database/delphi_trades.db"
            
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                
                # 분석 결과 테이블 존재 확인 및 생성
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS trade_analyses (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        trade_id TEXT NOT NULL,
                        analysis_type TEXT NOT NULL,
                        key_factors TEXT NOT NULL,
                        agent_accuracy TEXT NOT NULL,
                        market_factor_impact TEXT NOT NULL,
                        lessons_learned TEXT NOT NULL,
                        confidence_score REAL NOT NULL,
                        timestamp TEXT NOT NULL,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (trade_id) REFERENCES trade_records (trade_id)
                    )
                """)
                
                # 최근 분석 결과 조회 (향후 더 정교한 유사성 검색 가능)
                query = """
                    SELECT ta.*, tr.outcome, tr.pnl_percent
                    FROM trade_analyses ta
                    LEFT JOIN trade_records tr ON ta.trade_id = tr.trade_id
                    ORDER BY ta.created_at DESC
                    LIMIT ?
                """
                
                cursor.execute(query, (limit,))
                results = cursor.fetchall()
                
                # 결과 정리
                lessons = []
                for row in results:
                    lessons.append({
                        'trade_id': row[1],
                        'analysis_type': row[2],
                        'key_factors': json.loads(row[3]),
                        'lessons_learned': row[6],
                        'confidence_score': row[7],
                        'outcome': row[9],
                        'pnl_percent': row[10]
                    })
                
                self.logger.info(f"📚 과거 거래 교훈 {len(lessons)}건 조회 완료")
                return lessons
                
        except Exception as e:
            self.logger.error(f"❌ 과거 교훈 조회 실패: {e}")
            return []

# 전역 거래 분석기 인스턴스
trade_analyzer = TradeAnalyzer()