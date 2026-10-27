# 末端配送绿色化信息平台

基于 Streamlit 的末端配送绿色化信息平台，包含五个功能页：

① 需求感知、② 班线规划、③ 碳测算与碳管理、④ 大模型碳助手、⑤ 充换电调度。

## 运行环境

- Python 3.10+（推荐）
- 依赖见 requirements.txt

## 本地安装与运行

```bash
pip install -r requirements.txt
streamlit run green_platform.py
```

运行后浏览器自动打开 http://localhost:8501 。

## 部署到 Streamlit Cloud（推荐）

1. 将本目录推送到 GitHub 仓库；
2. 在 [share.streamlit.io](https://share.streamlit.io) 新建 App，选择该仓库，入口文件填 `green_platform.py`；
3. 在 App 的 **Settings → Secrets** 中粘贴高德 / DeepSeek 密钥（格式见 `.streamlit/secrets.toml.example`）；
4. 保存后自动部署，无需自行安装系统依赖（`packages.txt` 已声明 `fonts-noto-cjk`）。

## 密钥配置（可选）

不填密钥也能运行：高德走「直线距离 × 绕行系数」兜底，大模型走内置兜底。

若要启用「高德真实道路距离 / 路线」和「真实大模型问答」：

1. 将 `.streamlit/secrets.toml.example` 复制为 `.streamlit/secrets.toml`
2. 填入你的高德 / DeepSeek 密钥

## 关于图表中文显示

仓库自带简体中文字体 `fonts/NotoSansCJKsc-Regular.otf`，程序启动时会优先加载它，
因此需求感知、班线规划、碳测算、充换电调度等页面图表中的中文在
Windows / Linux / Streamlit Cloud 上均能正常显示，无需额外配置。

## 文件说明

- `green_platform.py`   平台主程序
- `requirements.txt`    Python 依赖
- `packages.txt`        Streamlit Cloud 系统依赖（中文字体兜底）
- `fonts/`              中文字体（保证跨平台中文正常显示）
- `.streamlit/secrets.toml.example`  密钥模板
- `.gitignore`          忽略本地密钥与缓存（请勿提交真实密钥）
