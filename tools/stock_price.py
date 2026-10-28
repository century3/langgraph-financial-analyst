import pandas as pd
import matplotlib.pyplot as plt
import os
import socket
import urllib.request
import matplotlib as mpl
import numpy as np
from pathlib import Path
from langchain_core.tools import tool
import requests

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CSV_PATH = DATA_DIR / "all_data.csv"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"


def configure_network() -> None:
    """关掉 Cursor 本机代理并强制 IPv4。"""
    for key in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"):
        os.environ.pop(key, None)
    os.environ["NO_PROXY"] = "*"
    os.environ["no_proxy"] = "*"
    urllib.request.getproxies = lambda: {}
    urllib.request.getproxies_environment = lambda: {}
    if hasattr(urllib.request, "getproxies_registry"):
        urllib.request.getproxies_registry = lambda: {}
    requests.sessions.Session.trust_env = False
    original_init = requests.sessions.Session.__init__

    def _init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        self.trust_env = False
        self.proxies = {}

    requests.sessions.Session.__init__ = _init

    original_getaddrinfo = socket.getaddrinfo

    def _ipv4_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
        return original_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)

    socket.getaddrinfo = _ipv4_getaddrinfo


def tx_symbol(symbol: str) -> str:
    """转为腾讯接口使用的带市场前缀代码。akshare 对 ETF 不会自动加前缀。"""
    code = str(symbol).strip().lower()
    if code.startswith(("sh", "sz", "bj")):
        return code
    code = code.zfill(6)
    if code.startswith(("600", "601", "603", "605", "688", "689", "900", "50", "51", "52", "56", "58", "11")):
        return f"sh{code}"
    if code.startswith(("000", "001", "002", "003", "200", "300", "301", "15", "16", "17", "18", "12")):
        return f"sz{code}"
    if code.startswith(("430", "440", "830", "831", "832", "833", "839", "87", "88", "92")):
        return f"bj{code}"
    raise ValueError(f"无法识别股票代码市场: {symbol}")


def fetch_history(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    """从腾讯证券拉取前复权日线。"""
    import akshare as ak

    df = ak.stock_zh_a_hist_tx(
        symbol=tx_symbol(symbol),
        start_date=start_date,
        end_date=end_date,
        adjust="qfq",
        timeout=15,
    )
    if df.empty:
        return pd.DataFrame()
    out = pd.DataFrame({
        '日期': pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d'),
        '股票代码': str(symbol).zfill(6),
        '开盘': df['open'],
        '收盘': df['close'],
        '最高': df['high'],
        '最低': df['low'],
        '成交量': (df['volume'] / 100).round().astype('int64'),
        '成交额': df['amount'],
        '换手率': (df['turnover'] * 100).round(2),
    })
    start = pd.to_datetime(start_date)
    end = pd.to_datetime(end_date)
    day = pd.to_datetime(out['日期'])
    out = out[(day >= start) & (day <= end)]
    return out


def ensure_price_data(stock_codes, start_date: str, end_date: str) -> None:
    """保证本地 all_data.csv 覆盖本次分析需要的股票。"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    codes = [str(code).zfill(6) for code in stock_codes]
    existing = pd.DataFrame()
    have = set()
    if CSV_PATH.exists():
        existing = pd.read_csv(CSV_PATH)
        existing['股票代码'] = existing['股票代码'].astype(str).str.zfill(6)
        existing['日期'] = existing['日期'].astype(str).str.slice(0, 10)
        have = set(existing['股票代码'].unique())
    missing = [code for code in codes if code not in have]
    if not missing:
        return

    configure_network()
    frames = [existing] if not existing.empty else []
    for code in missing:
        df = fetch_history(code, start_date, end_date)
        if df.empty:
            print(f"警告: 未能获取股价数据: {code}")
            continue
        frames.append(df)
    if not frames:
        raise FileNotFoundError(f"未能获取任何股价数据: {codes}")
    all_df = pd.concat(frames, ignore_index=True)
    all_df['日期'] = all_df['日期'].astype(str).str.slice(0, 10)
    all_df.to_csv(CSV_PATH, index=False)
    print(f"已保存股价数据: {CSV_PATH}")

@tool
def analyze_stocks(stock_codes):
    """
    根据股票代码列表获取股票的起始价格，结束价格，区间涨跌幅，最大回撤，年化波动率
    
    Parameters:
    -----------
    stock_codes : list
        股票代码列表
    """

    start_date='20250422'
    end_date='20261022'

    # 设置中文字体
    plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'Arial Unicode MS']
    plt.rcParams['axes.unicode_minus'] = False
    mpl.rcParams['font.family'] = 'sans-serif'
    
    # 读取数据
    ensure_price_data(stock_codes, start_date, end_date)
    df = pd.read_csv(CSV_PATH)
    df['股票代码'] = df['股票代码'].astype(str).str.zfill(6)
    df['日期'] = pd.to_datetime(df['日期'].astype(str).str.slice(0, 10))
    
    # 创建结果列表
    all_results = []
    
    # 创建图表
    plt.figure(figsize=(15, 8))
    
    # 转换日期参数
    start_date = pd.to_datetime(start_date)
    end_date = pd.to_datetime(end_date)
    
    # 为每个股票代码进行分析
    for stock_code in stock_codes:
        try:
            # 筛选股票数据
            print("------stock_code-------")
            print(stock_code)
            print("------------------")
            stock_code = str(stock_code).zfill(6)
            stock_data = df[df['股票代码'] == stock_code].copy()
            
            if stock_data.empty:
                print(f"警告: 未找到股票: {stock_code}")
                continue
            
            # 筛选日期范围
            stock_data = stock_data[(stock_data['日期'] >= start_date) & (stock_data['日期'] <= end_date)]
            
            if len(stock_data) < 2:  # 确保至少有两条数据
                print(f"警告: 在指定日期范围内数据不足: {stock_code}")
                continue
            
            # 按日期排序
            stock_data = stock_data.sort_values('日期')
            
            # 计算日收益率
            stock_data['日收益率'] = stock_data['收盘'].pct_change()
            
            # 计算年化波动率 (假设一年252个交易日)
            volatility = stock_data['日收益率'].std() * np.sqrt(252) * 100
            
            # 计算关键指标
            start_price = stock_data.iloc[0]['收盘']
            end_price = stock_data.iloc[-1]['收盘']
            total_return = (end_price - start_price) / start_price * 100
            
            # 计算最大回撤
            stock_data['max_price'] = stock_data['收盘'].cummax()
            stock_data['min_price'] = stock_data['收盘'].cummin()
            stock_data['drawdown'] = (stock_data['max_price'] - stock_data['min_price']) / stock_data['max_price'] * 100
            max_drawdown = stock_data['drawdown'].max()
            
            # 添加到结果列表
            all_results.append({
                '股票代码': stock_code,
                '起始价格': start_price,
                '结束价格': end_price,
                '区间涨跌幅(%)': total_return,
                '最大回撤(%)': max_drawdown,
                '年化波动率(%)': volatility
            })
            
            # 绘制股价走势图
            plt.plot(stock_data['日期'], stock_data['收盘'], label=f'{stock_code}')
            
            # 添加关键价格标注
            plt.annotate(f'{stock_code} 起始价: {start_price:.2f}', 
                        xy=(stock_data['日期'].iloc[0], start_price),
                        xytext=(10, 10), textcoords='offset points')
            plt.annotate(f'{stock_code} 结束价: {end_price:.2f}',
                        xy=(stock_data['日期'].iloc[-1], end_price),
                        xytext=(10, -10), textcoords='offset points')
            
            # 标注最大回撤点
            max_drawdown_idx = stock_data['drawdown'].idxmax()
            if max_drawdown_idx is not None and max_drawdown_idx in stock_data.index:
                plt.annotate(f'{stock_code} 最大回撤: {max_drawdown:.2f}%',
                            xy=(stock_data.loc[max_drawdown_idx, '日期'], stock_data.loc[max_drawdown_idx, '收盘']),
                            xytext=(10, -10), textcoords='offset points')
            
        except Exception as e:
            print(f"处理股票 {stock_code} 时出错: {str(e)}")
            continue
    
    if not all_results:
        raise ValueError("没有找到任何有效的股票数据")
    
    # 创建结果DataFrame
    results = pd.DataFrame(all_results)
    
    # 保存结果到CSV
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    results.to_csv(OUTPUT_DIR / 'stocks_analysis.csv', index=False, encoding='utf-8-sig')
    
    # 完善图表
    plt.title(f'股价走势图 ({start_date.strftime("%Y-%m-%d")} 至 {end_date.strftime("%Y-%m-%d")})')
    plt.xlabel('日期')
    plt.ylabel('价格')
    plt.grid(True)
    plt.legend()
    
    # 调整x轴日期显示
    plt.gcf().autofmt_xdate()
    
    # 保存图表
    plt.savefig(OUTPUT_DIR / 'stocks_price_chart.png', dpi=300, bbox_inches='tight')
    plt.close()
    
    return results

if __name__ == '__main__':
    # 示例使用
    try:
        stock_codes = ['000612','688126','601788','513100']  # 可以替换为您想要分析的股票代码列表
        results = analyze_stocks.invoke({"stock_codes": stock_codes})
        print("\n分析结果:")
        print(results)
    except Exception as e:
        print(f"错误: {str(e)}")

