from langchain_core.tools import tool
from pathlib import Path
import os
import socket
import urllib.request
import pandas as pd
import requests

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CSV_PATH = DATA_DIR / "financial_report.csv"


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


def load_data():
    configure_network()
    import akshare as ak

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    df = ak.stock_yjbb_em(date="20241231")
    df.to_csv(CSV_PATH, index=False)
    print(f"已保存财报数据: {CSV_PATH}")
    return df

@tool
def get_financial_report(stock_codes):
    """
    根据股票代码列表获取财报数据
    
    Parameters:
    -----------
    stock_codes : list
        股票代码列表
    
    Returns:
    --------
    dict
        包含每个股票代码对应的财报数据的字典
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not CSV_PATH.exists():
        load_data()

    df = pd.read_csv(CSV_PATH)
    print("从本地文件读取数据成功")

    df['股票代码'] = df['股票代码'].astype(str).str.zfill(6)
    result = {}
    for code in stock_codes:
        code = str(code).zfill(6)
        stock_data = df[df['股票代码'] == code]
        result[code] = {
            'data': stock_data.to_dict('records') if not stock_data.empty else []
        }
    return result

# 示例使用
if __name__ == "__main__":
    # 测试用的股票代码列表
    test_codes = ['600600','002461','000729','600573']
    result = get_financial_report.invoke({"stock_codes": test_codes})
    
    if result:
        # 打印结果
        for code, data in result.items():
            print(f"\n股票代码: {code}")
            print("数据内容:")
            for row in data['data']:
                print(row)
    else:
        print("获取数据失败")


