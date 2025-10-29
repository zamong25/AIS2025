"""
Binance API를 사용한 차트 생성 모듈
Selenium 대신 API로 데이터를 받아 matplotlib로 차트 생성
"""
import os
import sys
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Rectangle
import warnings
warnings.filterwarnings('ignore')

# 프로젝트 루트 경로 추가
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Binance 클라이언트 임포트
try:
    from binance.client import Client
    from binance.exceptions import BinanceAPIException
except ImportError:
    print("[ERROR] python-binance 라이브러리가 필요합니다: pip install python-binance")
    sys.exit(1)

# pandas-ta 임포트
try:
    import pandas_ta as ta
except ImportError:
    print("[ERROR] pandas-ta 라이브러리가 필요합니다: pip install pandas-ta")
    sys.exit(1)


class ChartGenerator:
    """Binance API 기반 차트 생성기"""

    # 타임프레임 매핑
    TIMEFRAMES = {
        '5m': Client.KLINE_INTERVAL_5MINUTE,
        '15m': Client.KLINE_INTERVAL_15MINUTE,
        '1H': Client.KLINE_INTERVAL_1HOUR,
        '1D': Client.KLINE_INTERVAL_1DAY
    }

    # 각 타임프레임당 가져올 캔들 수
    CANDLE_LIMITS = {
        '5m': 200,   # 약 16시간
        '15m': 200,  # 약 50시간 (2일)
        '1H': 200,   # 약 8일
        '1D': 200    # 약 200일
    }

    def __init__(self, symbol='SOLUSDT'):
        """
        초기화

        Args:
            symbol: 거래 심볼 (기본값: SOLUSDT)
        """
        self.symbol = symbol
        self.client = Client("", "")  # Public API (키 불필요)

    def fetch_klines(self, timeframe: str, limit: int = None) -> pd.DataFrame:
        """
        Binance에서 OHLCV 데이터 가져오기

        Args:
            timeframe: 타임프레임 (5m, 15m, 1H, 1D)
            limit: 가져올 캔들 수

        Returns:
            DataFrame with columns: timestamp, open, high, low, close, volume
        """
        if limit is None:
            limit = self.CANDLE_LIMITS[timeframe]

        interval = self.TIMEFRAMES[timeframe]

        try:
            print(f"[DATA] {timeframe} 데이터 가져오는 중... (최근 {limit}개)")
            klines = self.client.get_klines(
                symbol=self.symbol,
                interval=interval,
                limit=limit
            )

            # DataFrame 변환
            df = pd.DataFrame(klines, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_volume', 'trades', 'taker_buy_base',
                'taker_buy_quote', 'ignore'
            ])

            # 필요한 컬럼만 선택 및 타입 변환
            df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = df[col].astype(float)

            print(f"[OK] {timeframe} 데이터 {len(df)}개 로드 완료")
            return df

        except BinanceAPIException as e:
            print(f"[ERROR] Binance API 오류: {e}")
            return None
        except Exception as e:
            print(f"[ERROR] 데이터 가져오기 실패: {e}")
            return None

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        기술적 지표 계산

        Args:
            df: OHLCV 데이터프레임

        Returns:
            지표가 추가된 데이터프레임
        """
        print("[INDICATORS] 기술적 지표 계산 중...")

        # 1. 이동평균선 (EMA)
        df['ema20'] = ta.ema(df['close'], length=20)
        df['ema50'] = ta.ema(df['close'], length=50)
        df['ema200'] = ta.ema(df['close'], length=200)

        # 2. RSI (Relative Strength Index)
        df['rsi'] = ta.rsi(df['close'], length=14)

        # 3. MACD
        macd = ta.macd(df['close'], fast=12, slow=26, signal=9)
        df['macd'] = macd['MACD_12_26_9']
        df['macd_signal'] = macd['MACDs_12_26_9']
        df['macd_hist'] = macd['MACDh_12_26_9']

        # 4. Bollinger Bands
        bbands = ta.bbands(df['close'], length=20, std=2)
        df['bb_upper'] = bbands['BBU_20_2.0']
        df['bb_middle'] = bbands['BBM_20_2.0']
        df['bb_lower'] = bbands['BBL_20_2.0']

        # 5. ATR (Average True Range)
        df['atr'] = ta.atr(df['high'], df['low'], df['close'], length=14)

        print("[OK] 지표 계산 완료")
        return df

    def find_support_resistance(self, df: pd.DataFrame, window: int = 20) -> dict:
        """
        지지선과 저항선 자동 계산

        Args:
            df: OHLCV 데이터프레임
            window: 윈도우 크기

        Returns:
            {'support': [가격들], 'resistance': [가격들]}
        """
        highs = df['high'].values
        lows = df['low'].values

        resistance_levels = []
        support_levels = []

        # 최근 데이터에 더 가중치
        recent_data = df.tail(window * 3)

        # 저항선: 최근 고점들
        for i in range(window, len(recent_data) - window):
            if recent_data['high'].iloc[i] == recent_data['high'].iloc[i-window:i+window].max():
                resistance_levels.append(recent_data['high'].iloc[i])

        # 지지선: 최근 저점들
        for i in range(window, len(recent_data) - window):
            if recent_data['low'].iloc[i] == recent_data['low'].iloc[i-window:i+window].min():
                support_levels.append(recent_data['low'].iloc[i])

        # 중복 제거 및 정렬
        resistance_levels = sorted(list(set([round(r, 2) for r in resistance_levels])), reverse=True)[:3]
        support_levels = sorted(list(set([round(s, 2) for s in support_levels])))[:3]

        return {
            'resistance': resistance_levels,
            'support': support_levels
        }

    def create_chart(self, df: pd.DataFrame, timeframe: str, output_path: str):
        """
        AI 분석에 최적화된 차트 생성

        Args:
            df: 지표가 계산된 데이터프레임
            timeframe: 타임프레임 (제목용)
            output_path: 저장 경로
        """
        print(f"[CHART] {timeframe} 차트 생성 중...")

        # 지지/저항선 계산
        levels = self.find_support_resistance(df)

        # Figure 설정 (AI가 분석하기 좋은 고해상도)
        fig = plt.figure(figsize=(16, 12), facecolor='#0E1117')

        # 4개 서브플롯: 메인차트, RSI, MACD, Volume
        gs = fig.add_gridspec(4, 1, height_ratios=[3, 1, 1, 1], hspace=0.05)
        ax1 = fig.add_subplot(gs[0])  # 메인 차트
        ax2 = fig.add_subplot(gs[1], sharex=ax1)  # RSI
        ax3 = fig.add_subplot(gs[2], sharex=ax1)  # MACD
        ax4 = fig.add_subplot(gs[3], sharex=ax1)  # Volume

        # 색상 설정 (AI 식별에 좋은 명확한 색상)
        colors = {
            'bg': '#0E1117',
            'grid': '#1E2530',
            'text': '#FFFFFF',
            'up': '#26A69A',      # 양봉 (초록)
            'down': '#EF5350',    # 음봉 (빨강)
            'ema20': '#FFD700',   # 금색 (단기)
            'ema50': '#FF6B6B',   # 주황 (중기)
            'ema200': '#4ECDC4',  # 청록 (장기)
            'bb': '#9C27B0',      # 보라 (볼린저밴드)
            'support': '#26A69A', # 초록 (지지선)
            'resistance': '#EF5350', # 빨강 (저항선)
            'rsi_over': '#EF5350',   # RSI 과매수
            'rsi_under': '#26A69A',  # RSI 과매도
            'macd_pos': '#26A69A',   # MACD 양수
            'macd_neg': '#EF5350'    # MACD 음수
        }

        # 1. 메인 차트: 캔들스틱 + EMA + Bollinger Bands
        for ax in [ax1, ax2, ax3, ax4]:
            ax.set_facecolor(colors['bg'])
            ax.grid(True, alpha=0.2, color=colors['grid'])
            ax.tick_params(colors=colors['text'])
            for spine in ax.spines.values():
                spine.set_color(colors['grid'])

        # 캔들스틱
        for idx, row in df.iterrows():
            color = colors['up'] if row['close'] >= row['open'] else colors['down']

            # 캔들 몸통
            height = abs(row['close'] - row['open'])
            bottom = min(row['open'], row['close'])
            ax1.add_patch(Rectangle(
                (mdates.date2num(row['timestamp']), bottom),
                0.0006,  # 캔들 너비
                height,
                facecolor=color,
                edgecolor=color,
                alpha=0.9
            ))

            # 꼬리 (심지)
            ax1.plot(
                [row['timestamp'], row['timestamp']],
                [row['low'], row['high']],
                color=color,
                linewidth=1,
                alpha=0.8
            )

        # 이동평균선
        ax1.plot(df['timestamp'], df['ema20'], color=colors['ema20'],
                linewidth=2, label='EMA 20', alpha=0.9)
        ax1.plot(df['timestamp'], df['ema50'], color=colors['ema50'],
                linewidth=2, label='EMA 50', alpha=0.9)
        ax1.plot(df['timestamp'], df['ema200'], color=colors['ema200'],
                linewidth=2, label='EMA 200', alpha=0.9)

        # 볼린저 밴드
        ax1.plot(df['timestamp'], df['bb_upper'], color=colors['bb'],
                linewidth=1, linestyle='--', label='BB Upper', alpha=0.6)
        ax1.plot(df['timestamp'], df['bb_middle'], color=colors['bb'],
                linewidth=1, alpha=0.4)
        ax1.plot(df['timestamp'], df['bb_lower'], color=colors['bb'],
                linewidth=1, linestyle='--', label='BB Lower', alpha=0.6)
        ax1.fill_between(df['timestamp'], df['bb_upper'], df['bb_lower'],
                         color=colors['bb'], alpha=0.1)

        # 지지/저항선
        for resistance in levels['resistance']:
            ax1.axhline(y=resistance, color=colors['resistance'],
                       linewidth=2, linestyle='--', alpha=0.7)
            ax1.text(df['timestamp'].iloc[-1], resistance, f' R: ${resistance:.2f}',
                    color=colors['resistance'], fontsize=10, fontweight='bold',
                    verticalalignment='center')

        for support in levels['support']:
            ax1.axhline(y=support, color=colors['support'],
                       linewidth=2, linestyle='--', alpha=0.7)
            ax1.text(df['timestamp'].iloc[-1], support, f' S: ${support:.2f}',
                    color=colors['support'], fontsize=10, fontweight='bold',
                    verticalalignment='center')

        # 현재가 표시
        current_price = df['close'].iloc[-1]
        ax1.axhline(y=current_price, color='#FFC107', linewidth=3, alpha=0.8)
        ax1.text(df['timestamp'].iloc[0], current_price, f' ${current_price:.2f}',
                color='#FFC107', fontsize=12, fontweight='bold',
                verticalalignment='center',
                bbox=dict(boxstyle='round', facecolor='#0E1117', alpha=0.8))

        ax1.legend(loc='upper left', facecolor=colors['bg'],
                  edgecolor=colors['grid'], labelcolor=colors['text'])
        ax1.set_ylabel('Price (USDT)', color=colors['text'], fontsize=12, fontweight='bold')
        ax1.set_title(f'{self.symbol} - {timeframe}',
                     color=colors['text'], fontsize=16, fontweight='bold', pad=20)

        # 2. RSI
        ax2.plot(df['timestamp'], df['rsi'], color='#2196F3', linewidth=2)
        ax2.axhline(y=70, color=colors['rsi_over'], linestyle='--', linewidth=1, alpha=0.7)
        ax2.axhline(y=30, color=colors['rsi_under'], linestyle='--', linewidth=1, alpha=0.7)
        ax2.fill_between(df['timestamp'], 70, 100, color=colors['rsi_over'], alpha=0.1)
        ax2.fill_between(df['timestamp'], 0, 30, color=colors['rsi_under'], alpha=0.1)
        ax2.set_ylabel('RSI(14)', color=colors['text'], fontsize=10, fontweight='bold')
        ax2.set_ylim(0, 100)
        ax2.text(0.01, 0.95, 'Overbought > 70', transform=ax2.transAxes,
                color=colors['rsi_over'], fontsize=9, verticalalignment='top')
        ax2.text(0.01, 0.05, 'Oversold < 30', transform=ax2.transAxes,
                color=colors['rsi_under'], fontsize=9, verticalalignment='bottom')

        # 3. MACD
        colors_macd = [colors['macd_pos'] if x > 0 else colors['macd_neg']
                      for x in df['macd_hist']]
        ax3.bar(df['timestamp'], df['macd_hist'], color=colors_macd, alpha=0.5, width=0.0006)
        ax3.plot(df['timestamp'], df['macd'], color='#2196F3', linewidth=2, label='MACD')
        ax3.plot(df['timestamp'], df['macd_signal'], color='#FF9800', linewidth=2, label='Signal')
        ax3.axhline(y=0, color=colors['text'], linestyle='-', linewidth=1, alpha=0.3)
        ax3.set_ylabel('MACD(12,26,9)', color=colors['text'], fontsize=10, fontweight='bold')
        ax3.legend(loc='upper left', facecolor=colors['bg'],
                  edgecolor=colors['grid'], labelcolor=colors['text'], fontsize=9)

        # 4. Volume
        colors_vol = [colors['up'] if df['close'].iloc[i] >= df['open'].iloc[i]
                     else colors['down'] for i in range(len(df))]
        ax4.bar(df['timestamp'], df['volume'], color=colors_vol, alpha=0.6, width=0.0006)
        ax4.set_ylabel('Volume', color=colors['text'], fontsize=10, fontweight='bold')
        ax4.set_xlabel('Time', color=colors['text'], fontsize=10, fontweight='bold')

        # X축 포맷 (시간 표시)
        ax4.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d %H:%M'))
        ax4.xaxis.set_major_locator(mdates.AutoDateLocator())
        plt.setp(ax4.xaxis.get_majorticklabels(), rotation=45, ha='right')

        # 상단 3개 차트는 X축 라벨 숨김
        plt.setp(ax1.get_xticklabels(), visible=False)
        plt.setp(ax2.get_xticklabels(), visible=False)
        plt.setp(ax3.get_xticklabels(), visible=False)

        # 레이아웃 조정
        plt.tight_layout()

        # 저장
        plt.savefig(output_path, dpi=150, facecolor=colors['bg'],
                   bbox_inches='tight', pad_inches=0.1)
        plt.close()

        print(f"[SAVED] 차트 저장 완료: {output_path}")

    def generate_all_charts(self, output_dir: str = None):
        """
        모든 타임프레임의 차트 생성

        Args:
            output_dir: 저장 디렉토리 (기본값: data/screenshots/)
        """
        if output_dir is None:
            output_dir = os.path.join(project_root, "data", "screenshots")

        # 디렉토리 생성
        os.makedirs(output_dir, exist_ok=True)

        print(f"\n{'='*60}")
        print(f"[START] {self.symbol} 차트 생성 시작")
        print(f"{'='*60}\n")

        success_count = 0

        for tf_name, tf_interval in self.TIMEFRAMES.items():
            try:
                # 1. 데이터 가져오기
                df = self.fetch_klines(tf_name)
                if df is None or len(df) == 0:
                    print(f"[SKIP] {tf_name} 데이터 없음, 스킵")
                    continue

                # 2. 지표 계산
                df = self.calculate_indicators(df)

                # 3. 차트 생성
                output_path = os.path.join(output_dir, f"chart_{tf_name}.png")
                self.create_chart(df, tf_name, output_path)

                success_count += 1

            except Exception as e:
                print(f"[ERROR] {tf_name} 차트 생성 실패: {e}")
                import traceback
                traceback.print_exc()

        print(f"\n{'='*60}")
        print(f"[COMPLETE] 차트 생성 완료: {success_count}/{len(self.TIMEFRAMES)}개 성공")
        print(f"{'='*60}\n")

        return success_count == len(self.TIMEFRAMES)


def main():
    """메인 실행 함수"""
    import argparse

    parser = argparse.ArgumentParser(description='Binance API 기반 차트 생성')
    parser.add_argument('--symbol', type=str, default='SOLUSDT',
                       help='거래 심볼 (기본값: SOLUSDT)')
    parser.add_argument('--output', type=str, default=None,
                       help='출력 디렉토리 (기본값: data/screenshots/)')

    args = parser.parse_args()

    # 차트 생성기 초기화
    generator = ChartGenerator(symbol=args.symbol)

    # 모든 차트 생성
    success = generator.generate_all_charts(output_dir=args.output)

    if success:
        print("[SUCCESS] 모든 차트가 성공적으로 생성되었습니다!")
        sys.exit(0)
    else:
        print("[WARNING] 일부 차트 생성에 실패했습니다.")
        sys.exit(1)


if __name__ == "__main__":
    main()
