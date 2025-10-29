"""
델파이 트레이딩 시스템 - OpenAI GPT API 클라이언트 유틸리티
AI 에이전트 호출을 위한 공통 클라이언트 (Gemini → GPT 마이그레이션)
"""

import os
import time
import json
import logging
import re
import base64
from pathlib import Path
from openai import OpenAI, APITimeoutError, APIConnectionError
from dotenv import load_dotenv
from utils.performance_optimizer import performance_optimizer

# Load environment variables from config/.env
project_root = Path(__file__).parent.parent.parent
load_dotenv(project_root / "config" / ".env")


class OpenAIClient:
    """OpenAI GPT API 호출을 위한 공통 클라이언트"""

    def __init__(self):
        # OPEN_API_KEY 또는 OPENAI_API_KEY 모두 지원
        self.api_key = os.getenv('OPEN_API_KEY') or os.getenv('OPENAI_API_KEY')
        if not self.api_key:
            raise ValueError("❌ .env 파일에 OPEN_API_KEY 또는 OPENAI_API_KEY가 없습니다.")

        # 클라이언트 재사용을 위한 인스턴스 변수
        self._client = None

    def get_client(self, timeout: int = 60):
        """클라이언트 인스턴스 반환 (재사용)"""
        # 매번 새 클라이언트 생성하여 timeout 정확히 적용
        return OpenAI(
            api_key=self.api_key,
            timeout=timeout,  # OpenAI SDK timeout 설정
            max_retries=2  # 재시도 횟수 제한
        )

    @performance_optimizer.retry_with_backoff(max_retries=3)
    @performance_optimizer.rate_limit(calls_per_second=0.5)  # API 호출 제한
    @performance_optimizer.circuit_breaker(failure_threshold=5, timeout_seconds=60)
    def invoke_agent_json(self, model_name: str, prompt: str, images=None, tools=None,
                         retries: int = 3, timeout: int = 60) -> dict:
        """
        AI 에이전트를 호출하여 JSON 응답을 받는 공통 함수

        Args:
            model_name: 사용할 모델명 (기본: gpt-4o)
            prompt: 입력 프롬프트
            images: 이미지 목록 (PIL Image 객체)
            tools: 도구 목록 (옵션, 현재 미사용)
            retries: 재시도 횟수
            timeout: 타임아웃 (초)

        Returns:
            파싱된 JSON 딕셔너리
        """
        client = self.get_client(timeout)

        # 기본 모델은 gpt-4o
        if not model_name or 'gemini' in model_name.lower():
            model_name = 'gpt-4o'

        # 메시지 구성 - OpenAI JSON mode requires "json" word in messages
        messages = [
            {
                "role": "system",
                "content": "You are a helpful assistant. Always respond in valid JSON format."
            }
        ]

        # 이미지가 있는 경우 (Vision API)
        if images and len(images) > 0:
            content = [{"type": "text", "text": prompt}]

            # 이미지를 base64로 인코딩
            for img in images:
                # PIL Image를 base64로 변환
                import io
                buffer = io.BytesIO()
                img.save(buffer, format='PNG')
                img_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')

                content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{img_base64}"
                    }
                })

            messages.append({
                "role": "user",
                "content": content
            })
        else:
            # 텍스트만 있는 경우
            messages.append({
                "role": "user",
                "content": prompt
            })

        for attempt in range(retries):
            try:
                logging.info(f"--- OpenAI API 요청 전송 (시도 {attempt + 1}/{retries})... ---")
                logging.info(f"--- Model: {model_name}, Timeout: {timeout}초 ---")

                response = client.chat.completions.create(
                    model=model_name,
                    messages=messages,
                    temperature=0.2,
                    response_format={"type": "json_object"},  # JSON 응답 강제
                    timeout=timeout
                )

                raw_text = response.choices[0].message.content
                raw_block = self.clean_model_output(raw_text)
                report_json = self.safe_json_loads(raw_block)
                logging.info("✅ SUCCESS: JSON parsing completed")
                return report_json

            except APITimeoutError as e:
                logging.error(f"[ERROR] OpenAI API timeout after {timeout}s: {e}")
                if attempt < retries - 1:
                    logging.info(f"... retrying in 5 seconds (attempt {attempt + 2}/{retries})")
                    time.sleep(5)
                else:
                    logging.error(f"[ERROR] All {retries} attempts timed out")
                    return None
            except APIConnectionError as e:
                logging.error(f"[ERROR] OpenAI API connection error: {e}")
                if attempt < retries - 1:
                    logging.info(f"... retrying in 5 seconds (attempt {attempt + 2}/{retries})")
                    time.sleep(5)
                else:
                    return None
            except json.JSONDecodeError as e:
                logging.warning(f"[WARNING] JSON parsing failed - retrying. Error: {e}")
                logging.warning(f"[RAW Response]:\n{raw_text}")
                logging.warning(f"[CLEANED Response]:\n{raw_block}")
            except Exception as e:
                logging.error(f"[ERROR] API call failed: {e}")
                if attempt < retries - 1:
                    logging.info(f"... retrying in 5 seconds (attempt {attempt + 2}/{retries})")
                    time.sleep(5)
                else:
                    return None

        logging.error("❌ ERROR: Failed to receive valid JSON response")
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


# 전역 OpenAI 클라이언트 인스턴스
openai_client = OpenAIClient()
