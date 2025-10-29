import os
import json
import pandas as pd
import pandas_ta as ta
import requests
import logging
from binance.client import Client
from dotenv import load_dotenv
from datetime import datetime, timedelta
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.performance_optimizer import performance_optimizer
from utils.data_quality import data_quality_manager, DataQuality

# Load environment variables from correct path
from pathlib import Path
project_root = Path(__file__).parent.parent.parent
load_dotenv(project_root / "config" / ".env")

# Initialize client based on testnet mode
testnet_mode = os.getenv('TESTNET_MODE', 'false').lower() == 'true'

if testnet_mode:
    api_key = os.getenv('BINANCE_TESTNET_API_KEY')
    api_secret = os.getenv('BINANCE_TESTNET_SECRET_KEY')
    client = Client(api_key, api_secret, testnet=True)
else:
    api_key = os.getenv('BINANCE_API_KEY')
    api_secret = os.getenv('BINANCE_API_SECRET')
    client = Client(api_key, api_secret)

# recvWindow 설정 (timestamp 에러 방지 - 기본 5초 → 60초)
client.recvWindow = 60000  # 60초

# Binance 서버 시간 동기화 (timestamp 에러 방지)
def _sync_binance_time(client):
    """
    Binance 서버 시간과 로컬 시간 동기화
    3번 측정하여 중간값 사용 (네트워크 지연 보정)
    """
    try:
        import time
        from datetime import datetime, timezone

        offsets = []
        for i in range(3):
            # 요청 전 시간 기록
            before_request = int(datetime.now(timezone.utc).timestamp() * 1000)

            # 서버 시간 조회
            server_time = client.get_server_time()
            server_time_ms = server_time['serverTime']

            # 요청 후 시간 기록
            after_request = int(datetime.now(timezone.utc).timestamp() * 1000)

            # 중간 시간 계산 (네트워크 지연 보정)
            local_time_ms = (before_request + after_request) // 2
            time_offset = server_time_ms - local_time_ms

            offsets.append(time_offset)

            # 마지막 측정이 아니면 짧은 대기
            if i < 2:
                time.sleep(0.1)

        # 중간값 사용 (극단값 제거)
        offsets.sort()
        time_offset = offsets[1]  # 3개 중 중간값

        # Binance client의 timestamp_offset 설정
        client.timestamp_offset = time_offset

        logging.info(f"[TIME_SYNC] Binance 시간 동기화 완료: offset = {time_offset}ms ({time_offset/1000:.2f}초)")
        logging.debug(f"[TIME_SYNC] 측정된 offset 값들: {offsets}")

    except Exception as e:
        logging.warning(f"[TIME_SYNC] 시간 동기화 실패, offset=0 사용: {e}")
        client.timestamp_offset = 0

# 시간 동기화 실행
_sync_binance_time(client)

def get_current_price(symbol='SOLUSDT'):
    """Get current price for a symbol"""
    try:
        ticker = client.get_symbol_ticker(symbol=symbol)
        return float(ticker['price'])
    except Exception as e:
        logging.error(f"Error getting price for {symbol}: {e}")
        return None

def get_market_data(symbol='SOLUSDT'):
    """Get comprehensive market data"""
    try:
        # Current price
        price = get_current_price(symbol)
        
        # 24hr statistics  
        stats = client.get_ticker(symbol=symbol)
        
        # Recent candles
        klines = client.get_klines(symbol=symbol, interval='1h', limit=24)
        
        return {
            'price': price,
            'change_24h': float(stats['priceChangePercent']),
            'volume_24h': float(stats['volume']),
            'high_24h': float(stats['highPrice']),
            'low_24h': float(stats['lowPrice']),
            'candles': klines
        }
    except Exception as e:
        logging.error(f"Error getting market data for {symbol}: {e}")
        return None

def get_account_info():
    """Get account information"""
    try:
        return client.get_account()
    except Exception as e:
        logging.error(f"Error getting account info: {e}")
        return None

def get_additional_market_data(symbol):
    """
    Open Interest, Funding Rate, BTC 도미넌스 등 추가 시장 데이터 수집
    데이터 품질 관리 적용
    """
    quality_data = {}
    
    try:
        # 1. Open Interest 데이터 (선물 시장) - API 문제로 임시 비활성화
        if symbol.endswith('USDT'):
            futures_symbol = symbol
            try:
                # Open Interest 데이터 수집 (2024 최신 엔드포인트)
                try:
                    # 현재 Open Interest
                    oi_response = client.futures_open_interest(symbol=futures_symbol)
                    open_interest = float(oi_response.get('openInterest', 0))
                    
                    if open_interest > 0:
                        # 24시간 전 Open Interest와 비교하여 변화량 계산
                        try:
                            # 과거 데이터는 futures_open_interest_hist 사용
                            hist_response = client.futures_open_interest_hist(
                                symbol=futures_symbol,
                                period='5m',
                                limit=288  # 24시간 = 288개 (5분봉)
                            )
                            if hist_response and len(hist_response) > 0:
                                # 24시간 전 데이터
                                old_oi = float(hist_response[0].get('sumOpenInterest', 0))
                                if old_oi > 0:
                                    oi_delta = ((open_interest - old_oi) / old_oi) * 100
                                else:
                                    oi_delta = 0
                            else:
                                oi_delta = 0
                        except:
                            oi_delta = 0
                        
                        quality_data['open_interest'] = data_quality_manager.create_quality_data(
                            'open_interest', open_interest, True, source='binance_futures'
                        )
                        quality_data['oi_delta'] = data_quality_manager.create_quality_data(
                            'oi_delta', round(oi_delta, 2), True, source='binance_futures'
                        )
                    else:
                        quality_data['open_interest'] = data_quality_manager.create_quality_data(
                            'open_interest', None, False, 'No open interest data', 'binance_futures'
                        )
                        quality_data['oi_delta'] = data_quality_manager.create_quality_data(
                            'oi_delta', None, False, 'No OI delta data', 'binance_futures'
                        )
                        
                except Exception as e:
                    logging.warning(f"Open Interest API 오류: {e}")
                    # API가 여전히 문제가 있으면 비활성화
                    quality_data['open_interest'] = data_quality_manager.create_quality_data(
                        'open_interest', None, False, f'API error: {str(e)}', 'binance_futures'
                    )
                    quality_data['oi_delta'] = data_quality_manager.create_quality_data(
                        'oi_delta', None, False, f'API error: {str(e)}', 'binance_futures'
                    )
                    
            except Exception as e:
                logging.warning(f"Open Interest 데이터 수집 실패: {e}")
                quality_data['open_interest'] = data_quality_manager.create_quality_data(
                    'open_interest', None, False, str(e), 'binance_futures'
                )
                quality_data['oi_delta'] = data_quality_manager.create_quality_data(
                    'oi_delta', None, False, str(e), 'binance_futures'
                )
        
        # 2. Funding Rate 데이터
        try:
            funding_info = client.futures_funding_rate(symbol=symbol, limit=1)
            if funding_info:
                funding_rate = float(funding_info[0]['fundingRate'])
                quality_data['funding_rate'] = data_quality_manager.create_quality_data(
                    'funding_rate', funding_rate, True, source='binance_futures'
                )
            else:
                quality_data['funding_rate'] = data_quality_manager.create_quality_data(
                    'funding_rate', None, False, 'No funding rate data available', 'binance_futures'
                )
        except Exception as e:
            logging.warning(f"Funding Rate 데이터 수집 실패: {e}")
            quality_data['funding_rate'] = data_quality_manager.create_quality_data(
                'funding_rate', None, False, str(e), 'binance_futures'
            )
        
        # 3. BTC 도미넌스 (CoinGecko API 사용)
        try:
            btc_dominance = get_btc_dominance()
            if btc_dominance > 0:
                quality_data['btc_dominance'] = data_quality_manager.create_quality_data(
                    'btc_dominance', btc_dominance, True, source='coingecko'
                )
            else:
                quality_data['btc_dominance'] = data_quality_manager.create_quality_data(
                    'btc_dominance', None, False, 'BTC dominance API returned 0', 'coingecko'
                )
        except Exception as e:
            logging.warning(f"BTC 도미넌스 데이터 수집 실패: {e}")
            quality_data['btc_dominance'] = data_quality_manager.create_quality_data(
                'btc_dominance', None, False, str(e), 'coingecko'
            )
        
        # 4. BTC 상관관계 (7일)
        try:
            btc_correlation = calculate_btc_correlation(symbol)
            if btc_correlation is not None:
                quality_data['btc_correlation'] = data_quality_manager.create_quality_data(
                    'btc_correlation', btc_correlation, True, source='binance_calculated'
                )
            else:
                quality_data['btc_correlation'] = data_quality_manager.create_quality_data(
                    'btc_correlation', None, False, 'Correlation calculation failed', 'binance_calculated'
                )
        except Exception as e:
            logging.warning(f"BTC 상관관계 계산 실패: {e}")
            quality_data['btc_correlation'] = data_quality_manager.create_quality_data(
                'btc_correlation', None, False, str(e), 'binance_calculated'
            )
            
    except Exception as e:
        logging.error(f"추가 시장 데이터 수집 중 오류: {e}")
    
    return quality_data

def get_btc_dominance():
    """
    CoinGecko API를 통해 BTC 도미넌스 데이터 수집
    """
    try:
        url = "https://api.coingecko.com/api/v3/global"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            btc_dominance = data['data']['market_cap_percentage']['btc']
            return round(btc_dominance, 2)
        else:
            return 0
    except Exception as e:
        logging.warning(f"BTC 도미넌스 API 호출 실패: {e}")
        return 0

def calculate_btc_correlation(symbol, days=7):
    """
    해당 심볼과 BTC의 7일 상관관계 계산
    """
    try:
        # 7일간의 가격 데이터 수집
        end_time = datetime.now()
        start_time = end_time - timedelta(days=days)
        
        # 해당 심볼의 일일 가격 데이터
        symbol_klines = client.get_historical_klines(
            symbol, Client.KLINE_INTERVAL_1DAY, 
            start_time.strftime('%Y-%m-%d'), 
            end_time.strftime('%Y-%m-%d')
        )
        
        # BTC의 일일 가격 데이터
        btc_klines = client.get_historical_klines(
            'BTCUSDT', Client.KLINE_INTERVAL_1DAY,
            start_time.strftime('%Y-%m-%d'), 
            end_time.strftime('%Y-%m-%d')
        )
        
        if len(symbol_klines) >= 7 and len(btc_klines) >= 7:
            # 종가 기준 일일 수익률 계산
            symbol_returns = []
            btc_returns = []
            
            for i in range(1, min(len(symbol_klines), len(btc_klines))):
                symbol_close_prev = float(symbol_klines[i-1][4])
                symbol_close_curr = float(symbol_klines[i][4])
                symbol_return = (symbol_close_curr - symbol_close_prev) / symbol_close_prev
                symbol_returns.append(symbol_return)
                
                btc_close_prev = float(btc_klines[i-1][4])
                btc_close_curr = float(btc_klines[i][4])
                btc_return = (btc_close_curr - btc_close_prev) / btc_close_prev
                btc_returns.append(btc_return)
            
            # 상관관계 계산
            if len(symbol_returns) >= 5:  # 최소 5일 데이터
                correlation = pd.Series(symbol_returns).corr(pd.Series(btc_returns))
                return round(correlation, 3) if not pd.isna(correlation) else 0
            
        return 0
        
    except Exception as e:
        logging.warning(f"BTC 상관관계 계산 실패: {e}")
        return 0

@performance_optimizer.cached_call("quant_data", ttl_seconds=300)  # 5분 캐싱
def get_full_quant_data(symbol, interval='1h', limit=500):
    """
    지정된 심볼의 모든 필수 계량 지표를 계산하여 딕셔너리로 반환합니다.
    데이터 품질 관리 및 신뢰도 검증 포함
    """
    print(f"\n--- [데이터 수집] {symbol}의 {interval} 데이터를 바이낸스에서 수집 및 계산합니다... ---")
    
    # 데이터 품질 추적용 딕셔너리
    quality_data_map = {}
    
    try:
        # 1. 바이낸스에서 캔들 데이터(OHLCV) 가져오기
        klines = client.get_klines(symbol=symbol, interval=interval, limit=limit)
        cols = ['timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time', 
                'quote_asset_volume', 'number_of_trades', 'taker_buy_base_asset_volume', 
                'taker_buy_quote_asset_volume', 'ignore']
        df = pd.DataFrame(klines, columns=cols)

        # 숫자형으로 변환
        for col in ['open', 'high', 'low', 'close', 'volume', 'quote_asset_volume']:
            df[col] = pd.to_numeric(df[col])

        # 2. pandas_ta 라이브러리를 사용하여 기술 지표 계산
        df.ta.ema(length=20, append=True)
        df.ta.ema(length=50, append=True)
        df.ta.ema(length=200, append=True)
        df.ta.rsi(length=14, append=True)
        df.ta.atr(length=14, append=True)
        df.ta.obv(append=True)

        # 3. 필요한 최신 데이터만 추출
        latest_data = df.iloc[-1]

        # 4. 기본 데이터 품질 검증 및 저장
        price = latest_data['close']
        quality_data_map['price'] = data_quality_manager.create_quality_data(
            'price', price, price > 0, 
            None if price > 0 else "Price is 0 or negative", 'binance'
        )

        volume = latest_data['volume']
        quality_data_map['volume'] = data_quality_manager.create_quality_data(
            'volume', volume, volume > 0,
            None if volume > 0 else "Volume is 0 or negative", 'binance'
        )

        # 5. 기술적 지표 품질 검증
        ema_20 = latest_data.get('EMA_20')
        quality_data_map['ema_20'] = data_quality_manager.create_quality_data(
            'ema_20', ema_20, ema_20 is not None and not pd.isna(ema_20),
            None if (ema_20 is not None and not pd.isna(ema_20)) else "EMA_20 calculation failed", 'calculated'
        )

        ema_50 = latest_data.get('EMA_50')
        quality_data_map['ema_50'] = data_quality_manager.create_quality_data(
            'ema_50', ema_50, ema_50 is not None and not pd.isna(ema_50),
            None if (ema_50 is not None and not pd.isna(ema_50)) else "EMA_50 calculation failed", 'calculated'
        )

        rsi = latest_data.get('RSI_14')
        quality_data_map['rsi'] = data_quality_manager.create_quality_data(
            'rsi', rsi, rsi is not None and not pd.isna(rsi) and 0 <= rsi <= 100,
            None if (rsi is not None and not pd.isna(rsi) and 0 <= rsi <= 100) else "RSI calculation failed or out of range", 'calculated'
        )

        atr = latest_data.get('ATRr_14')
        quality_data_map['atr'] = data_quality_manager.create_quality_data(
            'atr', atr, atr is not None and not pd.isna(atr) and atr >= 0,
            None if (atr is not None and not pd.isna(atr) and atr >= 0) else "ATR calculation failed", 'calculated'
        )

        obv = latest_data.get('OBV')
        quality_data_map['obv'] = data_quality_manager.create_quality_data(
            'obv', obv, obv is not None and not pd.isna(obv),
            None if (obv is not None and not pd.isna(obv)) else "OBV calculation failed", 'calculated'
        )

        # 6. 볼륨 비율 계산
        volume_24h_avg = df['volume'].rolling(window=24).mean().iloc[-1]
        volume_ratio = latest_data['volume'] / volume_24h_avg if volume_24h_avg and volume_24h_avg > 0 else None

        # 7. 추가 데이터 수집 (Open Interest, Funding Rate, BTC 도미넌스) - 품질 관리 포함
        additional_quality_data = get_additional_market_data(symbol)
        quality_data_map.update(additional_quality_data)

        # 8. 데이터 품질 검증
        quality_report = data_quality_manager.validate_data_collection(quality_data_map)
        
        # 품질 보고서 로깅
        quality_summary = data_quality_manager.generate_quality_summary(quality_report)
        # quality_summary contains emojis that cause encoding issues
        logging.info("Quality report generated successfully")
        
        # 9. 분석 진행 가능 여부 확인
        if not data_quality_manager.should_proceed_with_analysis(quality_report):
            print("--- ERROR: Data quality insufficient, analysis stopped ---")
            return None

        # 10. 분석용 데이터 추출 (신뢰할 수 있는 데이터만)
        reliable_data = data_quality_manager.extract_values_for_analysis(quality_data_map, include_unreliable=False)
        
        # 11. 최종 데이터 객체 생성 (품질 정보 포함)
        quant_data = {
            "current_price": reliable_data.get('price'),
            "ema_20": reliable_data.get('ema_20'),  
            "ema_50": reliable_data.get('ema_50'),
            "ema_200": latest_data.get('EMA_200'),  # 품질 관리 미적용 데이터
            "atr_14": reliable_data.get('atr'),
            "rsi_14": reliable_data.get('rsi'),
            "obv": reliable_data.get('obv'),
            "volume_vs_24h_avg_ratio": round(volume_ratio, 2) if volume_ratio else None,
            "open_interest_usdt": reliable_data.get('open_interest'),
            "open_interest_delta": reliable_data.get('oi_delta'),
            "funding_rate": reliable_data.get('funding_rate'),
            "btc_dominance_percent": reliable_data.get('btc_dominance'),
            "correlation_with_btc_7d": reliable_data.get('btc_correlation'),
            
            # 데이터 품질 정보 추가
            "data_quality": {
                "overall_confidence": quality_report.overall_confidence,
                "reliable_data_count": quality_report.reliable_data_count,
                "total_data_count": quality_report.total_data_count,
                "has_critical_failures": len(quality_report.critical_failures) > 0,
                "warnings_count": len(quality_report.warnings)
            }
        }
        
        print(f"--- SUCCESS: Quant data collection completed (confidence: {quality_report.overall_confidence:.1%}) ---")
        return quant_data

    except Exception as e:
        print(f"--- ERROR: Failed to collect quant data: {e} ---")
        logging.error(f"get_full_quant_data 오류: {e}")
        return None

if __name__ == "__main__":
    # 이 파일을 직접 실행할 때 테스트
    sol_data = get_full_quant_data("SOLUSDT")
    if sol_data:
        print("\n--- SOLUSDT 최신 퀀트 데이터 ---")
        print(json.dumps(sol_data, indent=2))