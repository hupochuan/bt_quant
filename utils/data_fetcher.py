"""
数据获取模块 - Yahoo Finance 数据源
为 Backtrader 提供数据 feed
"""
import yfinance as yf
import pandas as pd
from datetime import datetime
import backtrader as bt
import os


class YahooFinanceData(bt.feeds.PandasData):
    """
    Backtrader 的 Yahoo Finance 数据适配器
    """
    params = (
        ('datetime', None),
        ('open', 'Open'),
        ('high', 'High'),
        ('low', 'Low'),
        ('close', 'Close'),
        ('volume', 'Volume'),
        ('openinterest', -1),
    )


class DataFetcher:
    """数据获取器"""

    def __init__(self, cache_dir="./cache"):
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)

    def fetch_data(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        interval: str = "1d"
    ) -> pd.DataFrame:
        """
        获取股票数据

        Args:
            symbol: 股票代码 (如 AAPL, TSLA)
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            interval: 数据周期 (1d, 1wk, 1h, 1m)

        Returns:
            DataFrame with columns: [Open, High, Low, Close, Volume]
        """
        cache_file = os.path.join(
            self.cache_dir,
            f"{symbol}_{start_date}_{end_date}_{interval}.csv"
        )

        # 尝试从缓存加载
        if os.path.exists(cache_file):
            print(f"[DataFetcher] 从缓存加载 {symbol} 数据")
            df = pd.read_csv(cache_file, index_col=0, parse_dates=True)
            return df

        # 从 Yahoo Finance 下载
        print(f"[DataFetcher] 从 Yahoo Finance 下载 {symbol} 数据...")
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(start=start_date, end=end_date, interval=interval)

            if df.empty:
                raise ValueError(f"未获取到 {symbol} 的数据")

            # 标准化列名 - 使用 title() 保持多词列名正确（如 "Adj Close"）
            df.columns = [col.title() for col in df.columns]

            # 将时区时间转为UTC后去除时区信息
            # Yahoo Finance 返回带时区的时间戳（如 America/New_York），
            # Backtrader 在读取时会将其转为 UTC，导致时间偏移4小时。
            # 此处统一转换为 UTC 时间再去除时区，保证策略内时间与 UTC 一致。
            if df.index.tz is not None:
                df.index = df.index.tz_convert('UTC').tz_localize(None)

            # 保存到缓存
            df.to_csv(cache_file)
            print(f"[DataFetcher] 数据已缓存: {cache_file}")

            return df

        except Exception as e:
            print(f"[DataFetcher] 获取数据失败: {e}")
            raise

    def get_stock_info(self, symbol: str) -> dict:
        """获取股票基本信息"""
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            return {
                'name': info.get('longName', ''),
                'sector': info.get('sector', ''),
                'industry': info.get('industry', ''),
                'market_cap': info.get('marketCap', 0),
                'pe_ratio': info.get('trailingPE', None),
                'dividend_yield': info.get('dividendYield', None),
            }
        except Exception as e:
            print(f"[DataFetcher] 获取股票信息失败: {e}")
            return {}

    def get_sp500_symbols(self) -> list:
        """获取标普500成分股列表"""
        try:
            url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
            tables = pd.read_html(url)
            sp500 = tables[0]
            return sp500['Symbol'].tolist()
        except Exception as e:
            print(f"[DataFetcher] 获取标普500列表失败: {e}")
            return ['AAPL', 'MSFT', 'AMZN', 'GOOGL', 'META', 'TSLA', 'NVDA', 'JPM', 'V', 'JNJ']


def create_backtrader_data(
    symbol: str,
    start_date: str = None,
    end_date: str = None,
    interval: str = "1d",
    cache_dir: str = "./cache"
) -> YahooFinanceData:
    """
    创建 Backtrader 数据 feed

    Args:
        symbol: 股票代码
        start_date: 开始日期
        end_date: 结束日期
        interval: 数据周期 (1d, 10m, 5m, 1h等)
        cache_dir: 缓存目录

    Returns:
        Backtrader Data Feed
    """
    import config

    start_date = start_date or config.START_DATE
    end_date = end_date or config.END_DATE

    fetcher = DataFetcher(cache_dir=cache_dir)
    df = fetcher.fetch_data(symbol, start_date, end_date, interval)

    # 解析interval获取时间框架和压缩值
    if interval == "1d":
        timeframe = bt.TimeFrame.Days
        compression = 1
    elif interval.endswith("m"):
        timeframe = bt.TimeFrame.Minutes
        compression = int(interval[:-1])  # "10m" -> 10
    elif interval.endswith("h"):
        timeframe = bt.TimeFrame.Minutes
        compression = int(interval[:-1]) * 60  # "1h" -> 60
    else:
        timeframe = bt.TimeFrame.Days
        compression = 1

    # 创建 Backtrader 数据 feed
    data = YahooFinanceData(
        dataname=df,
        name=symbol,
        timeframe=timeframe,
        compression=compression
    )

    return data


if __name__ == "__main__":
    # 测试数据获取
    fetcher = DataFetcher()

    print("=" * 60)
    print("测试数据获取模块")
    print("=" * 60)

    # 获取 AAPL 数据
    data = fetcher.fetch_data('AAPL', '2023-01-01', '2023-12-31')
    print(f"\n获取到 {len(data)} 条数据")
    print(f"\n数据预览:")
    print(data.head())

    # 获取股票信息
    info = fetcher.get_stock_info('AAPL')
    print(f"\n股票信息:")
    for key, value in info.items():
        print(f"  {key}: {value}")
