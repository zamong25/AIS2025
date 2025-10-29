"""
델파이 트레이딩 시스템 - Gemini API 클라이언트 유틸리티
AI 에이전트 호출을 위한 공통 클라이언트
"""

import os
import time
import json
import logging
import re
from pathlib import Path
import google.generativeai as genai
from dotenv import load_dotenv
from utils.performance_optimizer import performance_optimizer

# Load environment variables from config/.env
project_root = Path(__file__).parent.parent.parent
load_dotenv(project_root / "config" / ".env")


class GeminiClient:
    """Gemini API 호출을 위한 공통 클라이언트"""
    
    def __init__(self):
        self.api_key = os.getenv('GOOGLE_API_KEY')
        if not self.api_key:
            raise ValueError("❌ .env 파일에 GOOGLE_API_KEY가 없습니다.")
        
        # 클라이언트 재사용을 위한 인스턴스 변수
        self._client = None
    
    def get_client(self, timeout: int = 300):
        """클라이언트 인스턴스 반환 (재사용)"""
        if self._client is None:
            genai.configure(api_key=self.api_key)
            self._client = genai
        return self._client
    
    @performance_optimizer.retry_with_backoff(max_retries=3)
    @performance_optimizer.rate_limit(calls_per_second=0.5)  # API 호출 제한
    @performance_optimizer.circuit_breaker(failure_threshold=5, timeout_seconds=300)
    def invoke_agent_json(self, model_name: str, prompt: str, images=None, tools=None, 
                         retries: int = 3, timeout: int = 300) -> dict:
        """
        AI 에이전트를 호출하여 JSON 응답을 받는 공통 함수
        
        Args:
            model_name: 사용할 모델명
            prompt: 입력 프롬프트
            images: 이미지 목록 (옵션)
            tools: 도구 목록 (옵션)
            retries: 재시도 횟수
            timeout: 타임아웃 (초)
            
        Returns:
            파싱된 JSON 딕셔너리
        """
        client = self.get_client(timeout)
        
        contents = [prompt]
        if images:
            contents.extend(images)

        config = genai.GenerationConfig(
            temperature=0.2,
            response_mime_type="application/json"
        )

        for attempt in range(retries):
            try:
                logging.info(f"--- API 요청 전송 (시도 {attempt + 1}/{retries})... ---")
                logging.info(f"--- Timeout 설정: {timeout}초 ---")
                model = client.GenerativeModel(model_name)
                response = model.generate_content(
                    contents,
                    generation_config=config,
                    request_options={'timeout': timeout}
                )

                raw_block = self.clean_model_output(response.text)
                report_json = self.safe_json_loads(raw_block)
                logging.info("SUCCESS: JSON parsing completed")
                return report_json

            except json.JSONDecodeError as e:
                logging.warning(f"WARNING: JSON parsing failed - retrying. Error: {e}")
                logging.warning(f"[RAW Response]:\n{response.text}")
                logging.warning(f"[CLEANED Response]:\n{raw_block}")
            except Exception as e:
                logging.error(f"ERROR: API call failed: {e}")
                if attempt < retries - 1:
                    logging.info("... retrying in 5 seconds")
                    time.sleep(5)

        logging.error("ERROR: Failed to receive valid JSON response")
        return None
    
    @staticmethod
    def clean_model_output(raw: str) -> str:
        """모델 출력 정리"""
        if raw.startswith("```"):  # 백틱 제거
            raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.S)

        raw = re.sub(r"\[[0-9,\s]+\]", "", raw)                    # [12, 34] 출처 삭제
        # 스마트 따옴표 교정 (str.translate 대신 replace 사용)
        raw = raw.replace('"', '"').replace('"', '"')
        raw = raw.replace(''', '"').replace(''', '"')

        buf, in_str, prev = [], False, ""
        for ch in raw:                                             # 문자열 내부 \n → \\n
            if ch == '"' and prev != '\\':
                in_str = not in_str
            buf.append("\\n" if ch == '\n' and in_str else ch)
            prev = ch
        raw = "".join(buf)

        raw = re.sub(r",\s*([\}\]])", r"\1", raw)                  # trailing comma
        m = re.search(r"\{.*\}", raw, re.S)                        # JSON 본문만 추출
        return m.group(0) if m else raw
    
    @staticmethod
    def safe_json_loads(raw_block: str) -> dict:
        """JSON 문자열을 안전하게 파싱"""
        raw = raw_block.strip()

        # 백틱 블록 제거
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)

        # CR / LF 정규화
        raw = raw.replace("\r\n", "\n").replace("\r", "\n")

        return json.loads(raw)


# 전역 Gemini 클라이언트 인스턴스
gemini_client = GeminiClient()