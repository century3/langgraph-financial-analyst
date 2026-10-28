# LangGraph 金融分析代理

用 LangGraph 搭建的股票对比代理。它先由 DeepSeek Reasoner 生成分析计划，再由 DeepSeek Chat 按计划调用本地工具，对比股价表现和财报数据。

本项目只做数据分析演示，不构成投资建议。

## 功能

- 根据用户问题生成分步分析计划
- 读取本地财报，按股票代码返回财务数据
- 计算区间涨跌幅、最大回撤和年化波动率，并保存价格走势图
- 本地没有对应行情时，通过 AkShare 的腾讯证券接口补齐日线

默认分析区间是 `2025-04-22` 到 `2026-10-22`。示例问题比较 `000612`、`688126`、`601788` 和 `513100`。

## 目录

```text
agent.py                  规划、调用工具、判断结束的 LangGraph 流程
llm.py                    DeepSeek 与通义模型配置
prompt.py                 分析计划提示词
tools/financial_report.py 财报查询工具
tools/stock_price.py      股价分析工具
data/                     财报和日线数据
output/                   分析结果和价格图
agent_graph.mmd           代理流程图
```

## 环境

- Python 3.11
- 需要能访问 DeepSeek API
- 补齐缺失行情时需要能访问腾讯证券接口

## 安装

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

设置环境变量：

```powershell
$env:DEEPSEEK_API_KEY = "your_deepseek_api_key"
```

`llm.py` 里的通义模型还需要 `DASHSCOPE_API_KEY`，当前主流程不会调用它。

## 运行

```powershell
python agent.py
```

运行后会：

1. 把流程图写到 `agent_graph.mmd`
2. 打印分析计划
3. 在需要时更新 `data/all_data.csv`
4. 把对比结果写到 `output/stocks_analysis.csv`
5. 把价格图写到 `output/stocks_price_chart.png`
6. 在终端打印最终分析

单独测试工具：

```powershell
python tools/financial_report.py
python tools/stock_price.py
```

## 工作流

`START -> plan_node -> llm_call -> environment -> llm_call`

`llm_call` 在回复末尾包含 `Final Answer` 时结束。否则进入 `environment` 执行工具，再回到模型继续分析。
