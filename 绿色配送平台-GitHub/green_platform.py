# -*- coding: utf-8 -*-
"""
末端配送绿色化信息平台
功能：① 需求感知  ② 班线规划  ③ 碳测算与碳管理  ④ 大模型碳助手  ⑤ 充换电调度
运行：streamlit run green_platform.py
"""
import numpy as np
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
import json
import urllib.request
import urllib.parse
import hashlib
import time
import os
import sys

# ---- 中文字体：多策略加载，确保 Windows / Linux / Streamlit Cloud 都能显示中文 ----
# ① 最高优先：仓库自带的简体中文字体（相对脚本路径，不依赖云端 apt 包，部署最稳）
try:
    _SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
except NameError:
    _SCRIPT_DIR = os.getcwd()

_CJK_FONT_PATHS = [
    os.path.join(_SCRIPT_DIR, "fonts", "NotoSansCJKsc-Regular.otf"),   # 仓库自带（首选）
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",          # Debian/Ubuntu: fonts-noto-cjk
    "/usr/share/fonts/opentype/noto/NotoSansCJKsc-Regular.otf",
    "/usr/share/fonts/opentype/noto/NotoSansSC-Regular.otf",
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",                  # 文泉驿微米黑
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "C:/Windows/Fonts/msyh.ttc",                                       # Windows: 微软雅黑
    "C:/Windows/Fonts/msyh.ttf",
    "C:/Windows/Fonts/simhei.ttf",                                     # Windows: 黑体
    "C:/Windows/Fonts/simsun.ttc",                                     # Windows: 宋体
]
# ② 依次尝试可用字体文件：addfont 后读取其“确切字体名”直接采用（不依赖名字猜测，杜绝乱码）
_cjk_font = None
for _p in _CJK_FONT_PATHS:
    if not os.path.exists(_p):
        continue
    try:
        font_manager.fontManager.addfont(_p)
        _cjk_font = font_manager.FontProperties(fname=_p).get_name()
        if _cjk_font:
            break
    except Exception:
        continue

# ③ 兜底：按字体名匹配任意 CJK 字体（addfont 后这些名字已进入 ttflist）
if _cjk_font is None:
    _FONT_PREFER = ["Noto Sans CJK SC", "Noto Sans SC", "Microsoft YaHei", "SimHei",
                    "Noto Sans CJK JP", "Noto Sans CJK KR", "Noto Sans CJK TC",
                    "Source Han Sans SC", "WenQuanYi Micro Hei", "WenQuanYi Zen Hei", "SimSun", "DengXian"]
    _font_names = {f.name for f in font_manager.fontManager.ttflist}
    _cjk_font = next((c for c in _FONT_PREFER if c in _font_names), None)
# ④ 再兜底：匹配任意含 CJK/黑体/宋体 等关键字的字体
if _cjk_font is None:
    for _f in sorted(font_manager.fontManager.ttflist, key=lambda f: f.name):
        _n = _f.name.lower()
        if any(k in _n for k in ("cjk", "han", "hei", "song", "ming", "kai", "yahei")):
            _cjk_font = _f.name
            break
plt.rcParams["font.sans-serif"] = [_cjk_font, "DejaVu Sans"] if _cjk_font else ["DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

st.set_page_config(page_title="末端配送绿色化信息平台", page_icon="🌿", layout="wide")

# ---- 全局样式：紧凑留白 + 卡片化 metric + 统一配色 ----
st.markdown("""
<style>
    #MainMenu, footer {visibility: hidden;}
    .block-container {padding-top: 1.4rem; padding-bottom: 2rem;}
    .hero {
        background: linear-gradient(100deg, #0d7a5f 0%, #1baf7a 60%, #2fd6a0 100%);
        border-radius: 14px;
        padding: 1.3rem 1.8rem;
        margin-bottom: 1.1rem;
        color: #ffffff;
    }
    .hero h1 {margin:0; font-size:1.7rem; font-weight:700;}
    .hero p {margin:.4rem 0 0 0; font-size:.92rem; opacity:.93;}
    [data-testid="stMetric"] {
        background:#f7f9fa; border:1px solid #e8ecf0;
        border-radius:10px; padding:.65rem .9rem;
    }
    [data-testid="stMetricLabel"] {color:#4a5568;}
    div[data-testid="stExpander"] {border:1px solid #e8ecf0; border-radius:10px;}

    /* ---- 四个模块标签放大 + 突出 ---- */
    [data-testid="stTabs"] [role="tablist"] {gap: .4rem;}
    [data-testid="stTabs"] [data-testid="stTab"] {
        font-size: 1.12rem;
        font-weight: 700;
        padding: .75rem 1.5rem;
        border-radius: 12px 12px 0 0;
        background: #f2f7f5;
        border: 1px solid #dfe9e4;
        border-bottom: none;
        color: #27564b;
        transition: all .15s ease;
    }
    [data-testid="stTabs"] [data-testid="stTab"]:hover {
        background: #e4f2ec;
        color: #0d7a5f;
    }
    [data-testid="stTabs"] [data-testid="stTab"][aria-selected="true"] {
        background: linear-gradient(100deg, #0d7a5f 0%, #1baf7a 100%);
        color: #ffffff;
        border-color: #0d7a5f;
        box-shadow: 0 4px 12px rgba(13,122,95,.28);
    }
    [data-testid="stTabs"] [data-testid="stTab"] span,
    [data-testid="stTabs"] [data-testid="stTab"] [class*="Text"] {
        font-size: 1.12rem;
        font-weight: 700;
    }

    /* ---- 大模型助手：豆包风格对话（绿色主题） ---- */
    [data-testid="stChatMessage"] {
        display: flex;
        align-items: flex-start;
        gap: .7rem;
        margin: .8rem 0;
        background: transparent !important;
    }
    [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {
        flex-direction: row-reverse;
        align-items: flex-end;
    }
    [data-testid="stChatMessageContent"] {
        line-height: 1.7;
        font-size: .96rem;
        color: #1f2a36;
    }
    /* 用户：右侧绿色气泡 */
    [data-testid="stChatMessageContent"][aria-label="Chat message from user"] {
        background: linear-gradient(100deg, #0d7a5f 0%, #1baf7a 100%);
        color: #ffffff;
        padding: .65rem 1.1rem;
        border-radius: 16px;
        border-bottom-right-radius: 4px;
        max-width: 70%;
    }
    [data-testid="stChatMessageContent"][aria-label="Chat message from user"] * {
        color: #ffffff !important;
    }
    /* 助手：左侧纯文本（豆包/ChatGPT 式，不带灰底框） */
    [data-testid="stChatMessageContent"][aria-label="Chat message from assistant"] {
        background: transparent;
        border: none;
        padding: .15rem .1rem;
    }
    /* 头像 */
    [data-testid="stChatMessageAvatarUser"] { background: #0d7a5f !important; }
    [data-testid="stChatMessageAvatarAssistant"] { background: #e4f2ec !important; }
    [data-testid="stChatMessageAvatarAssistant"] * { color: #0d7a5f !important; }
    [data-testid="stChatMessageAvatarUser"],
    [data-testid="stChatMessageAvatarAssistant"] { flex: 0 0 auto; }
    /* 输入框：豆包式大圆角 + 绿色发送按钮 */
    [data-testid="stChatInput"] {
        position: sticky;
        bottom: 0;
        z-index: 20;
        background: #ffffff;
        padding-top: .4rem;
    }
    [data-testid="stChatInputTextArea"] {
        border-radius: 14px !important;
        padding: .6rem .9rem !important;
    }
    [data-testid="stChatInputSubmitButton"] {
        background: #1baf7a !important;
        color: #ffffff !important;
        border-radius: 10px !important;
    }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="hero">
  <h1>🌿 末端配送绿色化信息平台</h1>
  <p>需求感知 → 班线规划 → 碳测算与碳管理 → 大模型碳助手</p>
</div>
""", unsafe_allow_html=True)

HUB_LAT, HUB_LON = 40.127656, 116.586875                   # 总站：顺义顺航中转站（顺义区顺航路，临空经济区）

# ---- 密钥读取（高德 / DeepSeek）----
# 优先级：环境变量 > Streamlit secrets（本地 .streamlit/secrets.toml 或云端 dashboard）> 内置默认
def _get_secret(name, default=""):
    v = os.environ.get(name)
    if v:
        return v
    try:
        v = st.secrets[name]
        if v:
            return v
    except Exception:
        pass
    return default

# ---- 高德地图（画真实道路路径）----
# 三个值都填好才启用真实地图；否则自动回退直线距离 + matplotlib 示意图
AMAP_WEB_KEY = _get_secret("AMAP_WEB_KEY")          # Web端(JS API) Key
AMAP_WEB_JSCODE = _get_secret("AMAP_WEB_JSCODE")    # securityJsCode
AMAP_SERVICE_KEY = _get_secret("AMAP_SERVICE_KEY")  # Web服务 Key（真实道路距离）
AMAP_SERVICE_PRIVATE = _get_secret("AMAP_SERVICE_PRIVATE", "你的Web服务私钥")  # 数字签名私钥（可选）
AMAP_READY = (AMAP_WEB_KEY and AMAP_WEB_JSCODE
              and not AMAP_WEB_KEY.startswith("你的"))


# ================= 工具函数 =================
def haversine(lat1, lon1, lat2, lon2):
    """两点大圆距离(km)，高德不可用时的直线距离兜底"""
    p1, p2 = np.radians(lat1), np.radians(lat2)
    a = (np.sin(np.radians(lat2 - lat1) / 2) ** 2
         + np.cos(p1) * np.cos(p2) * np.sin(np.radians(lon2 - lon1) / 2) ** 2)
    return 2 * 6371.0 * np.arcsin(np.sqrt(a))


def dist_matrix(lats, lons):
    """lats[0]/lons[0]=总站，其余为站点；返回 (n+1)x(n+1) 距离矩阵(km)"""
    n = len(lats) - 1
    D = np.zeros((n + 1, n + 1))
    for i in range(n + 1):
        for j in range(n + 1):
            D[i][j] = haversine(lats[i], lons[i], lats[j], lons[j])
    return D


# 默认片区配送站（朝阳区各街道，可编辑；[名称, 纬度, 经度, 当日到货量(件), 当日退货量(件), 当日揽收量(件)]）
DEFAULT_STATIONS = [
    ["望京站", 40.000, 116.470, 620, 56, 280],
    ["酒仙桥站", 39.970, 116.490, 490, 41, 220],
    ["亚运村站", 39.990, 116.400, 380, 30, 170],
    ["奥运村站", 40.010, 116.400, 340, 26, 150],
    ["太阳宫站", 39.980, 116.440, 320, 24, 140],
    ["三里屯站", 39.930, 116.450, 460, 39, 205],
    ["建外站", 39.910, 116.460, 520, 46, 235],
    ["双井站", 39.890, 116.460, 440, 36, 200],
    ["劲松站", 39.880, 116.460, 370, 29, 165],
    ["潘家园站", 39.870, 116.450, 340, 26, 150],
    ["高碑店站", 39.910, 116.510, 360, 28, 160],
    ["常营站", 39.930, 116.570, 410, 33, 185],
    ["管庄站", 39.910, 116.590, 380, 30, 170],
    ["东坝站", 39.960, 116.550, 320, 24, 145],
    ["十八里店站", 39.850, 116.480, 290, 21, 130],
    ["朝外站", 39.918, 116.448, 330, 25, 150],
    ["六里屯站", 39.930, 116.475, 300, 22, 135],
    ["平房站", 39.945, 116.535, 310, 23, 140],
    ["垡头站", 39.865, 116.485, 280, 20, 125],
    ["来广营站", 40.025, 116.470, 350, 27, 160],
]

# 运输碳排固定密度口径（《统一清单》：120 km / 500 件 = 0.24 km/件）
KM_PER_ITEM = 0.24

# ================= 遗传算法（进化计算 · AI 智能优化分支）=================
def _split(perm, demands, pickups, cap, dist, alpha=1.0, fixed=0.0):
    """Prins 分割：把排列 perm（客户索引 1..n）切成满足去程/回程容量(硬)约束的回路，DP 最小化综合成本。

    回路成本 = alpha×里程 ＋ fixed(单车固定成本)。"""
    n = len(perm)
    pref = [0.0] * n                          # pref[t] = perm[0..t] 相邻路段累计里程
    for t in range(1, n):
        pref[t] = pref[t - 1] + dist[perm[t - 1]][perm[t]]
    dd = np.zeros(n + 1)                      # 去程体积前缀和
    pp = np.zeros(n + 1)                      # 回程体积前缀和
    for i in range(n):
        k = perm[i] - 1
        dd[i + 1] = dd[i] + demands[k]
        pp[i + 1] = pp[i] + pickups[k]
    V = np.full(n + 1, np.inf)                # V[i] = 服务前 i 个客户的最小综合成本
    P = np.zeros(n + 1, dtype=int)            # P[i] = 最后一条回路的起点（1-based）
    V[0] = 0.0
    for i in range(1, n + 1):
        for j in range(i, 0, -1):             # 最后一条回路覆盖 perm[j-1 .. i-1]
            if dd[i] - dd[j - 1] > cap + 1e-9 or pp[i] - pp[j - 1] > cap + 1e-9:
                break                         # 容量超限，j 再小只会更超
            a, b = j - 1, i - 1
            mileage = dist[0][perm[a]] + (pref[b] - pref[a]) + dist[perm[b]][0]
            cost = alpha * mileage + fixed
            if V[j - 1] + cost < V[i]:
                V[i] = V[j - 1] + cost
                P[i] = j
    routes, i = [], n
    while i > 0:
        j = P[i]
        routes.append(perm[j - 1:i])
        i = j - 1
    routes.reverse()
    return routes, V[n]


def _route_stats(route, demands, pickups, cap, dist):
    """把一条回路（客户索引列表）换算成配载统计字典（去程/回程装载、满载率、里程）。"""
    D = sum(demands[k - 1] for k in route)
    R = sum(pickups[k - 1] for k in route)
    P = max(D, R)
    mileage = (dist[0][route[0]]
               + sum(dist[route[i]][route[i + 1]] for i in range(len(route) - 1))
               + dist[route[-1]][0])
    return {"route": route, "D": D, "R": R, "P": P,
            "load_rate": P / cap, "mileage": mileage, "return_km": dist[route[-1]][0]}


def _ox(p1, p2, rng):
    """顺序交叉（OX）：保留一段连续子串，其余位置按另一父代的相对顺序补齐。"""
    n = len(p1)
    a, b = sorted(int(x) for x in rng.integers(0, n, 2))

    def _child(seg, other):
        s = set(seg)
        rest = [x for x in other if x not in s]
        return rest[:a] + seg + rest[a:]

    return _child(p1[a:b + 1], p2), _child(p2[a:b + 1], p1)


def _mutate(seq, rng):
    """交换变异：随机交换两个位置。"""
    i, j = int(rng.integers(0, len(seq))), int(rng.integers(0, len(seq)))
    if i != j:
        seq[i], seq[j] = seq[j], seq[i]


def genetic_algorithm(demands, pickups, cap, dist,
                      pop_size=60, generations=150, patience=30, seed=42, **cost_kw):
    """遗传算法求解 VRPSPD（同时取送货）：排列编码 + Prins 分割解码 + 锦标赛选择
    + OX 交叉 + 交换变异 + 精英保留。cost_kw 透传给 _split（alpha/fixed），
    从而把目标从“最小里程”升级为“最小综合成本”。
    返回 (配载方案列表, 最优综合成本, 收敛历史)。"""
    rng = np.random.default_rng(seed)
    n = len(demands)
    nodes = list(range(1, n + 1))
    if n == 1:
        r, m = _split(nodes, demands, pickups, cap, dist, **cost_kw)
        return [_route_stats(rt, demands, pickups, cap, dist) for rt in r], m, [m], [m]

    # 随机初始化种群（不依赖最近邻贪心，保证初始解多样性、收敛曲线有真实下降过程）
    pop = []
    for _ in range(pop_size):
        s = nodes[:]
        rng.shuffle(s)
        pop.append(s)

    def _fit(seq):
        return _split(seq, demands, pickups, cap, dist, **cost_kw)[1]

    fits = [_fit(s) for s in pop]
    bi = int(np.argmin(fits))
    best_seq, best_fit = pop[bi][:], fits[bi]
    history = [best_fit]
    mean_history = [float(np.mean(fits))]
    stale = 0

    def _tour():                              # 二元锦标赛选择
        a, b = rng.integers(0, len(pop), 2)
        return pop[a] if fits[a] <= fits[b] else pop[b]

    for _ in range(generations):
        children = []
        while len(children) < pop_size - 1:
            c1, c2 = _ox(_tour(), _tour(), rng)
            _mutate(c1, rng)
            _mutate(c2, rng)
            children += [c1, c2]
        pop = children[:pop_size - 1] + [best_seq]   # 精英保留
        fits = [_fit(s) for s in pop]
        bi = int(np.argmin(fits))
        if fits[bi] < best_fit - 1e-9:
            best_seq, best_fit = pop[bi][:], fits[bi]
            stale = 0
        else:
            stale += 1
        history.append(best_fit)
        mean_history.append(float(np.mean(fits)))
        if stale >= patience:
            break
    routes, total = _split(best_seq, demands, pickups, cap, dist, **cost_kw)
    result = [_route_stats(rt, demands, pickups, cap, dist) for rt in routes]
    return result, total, history, mean_history


@st.cache_data(show_spinner="遗传算法多目标进化求解中…")
def _solve_vrpspd(demands_t, pickups_t, D_t, cap, alpha, fixed, generations):
    """遗传算法缓存包装：输入用可哈希的 tuple 形式，参数不变时直接命中缓存，
    避免每次切换标签或调整任意参数都重跑整轮进化计算（页面切换变慢的主因）。
    返回 (routes, total, history, mean_history)，与 genetic_algorithm 一致。"""
    demands = np.asarray(demands_t, dtype=float)
    pickups = np.asarray(pickups_t, dtype=float)
    D = np.asarray(D_t, dtype=float)
    return genetic_algorithm(demands, pickups, cap, D, generations=generations,
                             alpha=alpha, fixed=fixed)


def objective_breakdown(routes, ev_rate, c_ev, c_fuel,
                        cost_ev_km, cost_fuel_km, carbon_price,
                        vehicle_fixed_cost, pack_cost, recycle_rate, total_items):
    """对一组配载方案（routes = _route_stats 字典列表）计算三维综合成本分项（元/天）：
    综合成本 = 能耗＋固定成本＋碳成本 ＋ 包装成本×(1−回收率)。"""
    total_km = sum(r["mileage"] for r in routes)
    K = len(routes)
    energy_cost = total_km * (ev_rate * cost_ev_km + (1 - ev_rate) * cost_fuel_km)
    carbon_kg = total_km * (ev_rate * c_ev + (1 - ev_rate) * c_fuel)
    carbon_cost = carbon_kg / 1000.0 * carbon_price
    vehicle_cost = K * vehicle_fixed_cost
    pack_total = total_items * pack_cost * (1 - recycle_rate)   # 常数项，不随路线变
    total = energy_cost + carbon_cost + vehicle_cost + pack_total
    return {"total_km": total_km, "K": K, "energy_cost": energy_cost,
            "carbon_kg": carbon_kg, "carbon_cost": carbon_cost,
            "vehicle_cost": vehicle_cost, "pack_total": pack_total, "total": total}


# ================= 高德地图（真实道路）=================
def _amap_sig(params, private_key):
    """高德 Web服务数字签名：MD5(按参数名升序的 k=v&k=v 串 + 私钥)"""
    base = "&".join("%s=%s" % (k, params[k]) for k in sorted(params))
    return hashlib.md5((base + private_key).encode("utf-8")).hexdigest()


def _amap_driving(origin, dest, key):
    """origin/dest=(lng,lat)，返回(距离米, 折线[[lng,lat],...])，失败(None,None)"""
    url = ("https://restapi.amap.com/v3/direction/driving?origin=%.6f,%.6f"
           "&destination=%.6f,%.6f&extensions=base&key=%s"
           % (origin[0], origin[1], dest[0], dest[1], key))
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            data = json.loads(r.read().decode("utf-8"))
        if data.get("status") != "1" or not data.get("route", {}).get("paths"):
            return None, None
        path = data["route"]["paths"][0]
        dist = int(path["distance"])
        pts = []
        for step in path["steps"]:
            for pair in step["polyline"].split(";"):
                a, b = pair.split(",")
                pts.append([float(a), float(b)])
        return dist, pts
    except Exception:
        return None, None


DETOUR_FACTOR = 1.28        # 道路/直线绕行系数：实测高德驾车距离约为直线距离的1.25~1.33倍，兜底时用它校正


@st.cache_data(show_spinner="正在获取高德真实道路距离…")
def amap_dist_matrix(lats, lons, key):
    """真实驾车距离矩阵(km)；逐列请求（多起点×单终点）。限流/失败仅回退该列（直线×绕行系数），
    不再整表退化。返回 (D, n_fallback)：n_fallback 为兜底列数，>0 表示这些站点触发了限流或异常。"""
    n = len(lats) - 1
    pts = ["%.6f,%.6f" % (lons[i], lats[i]) for i in range(n + 1)]
    origins = "|".join(pts)                    # 所有点作为起点（高德只支持多起点×单终点）
    D = np.zeros((n + 1, n + 1))
    n_fallback = 0
    for j in range(n + 1):                     # 每个终点一列，共 n+1 次请求
        got = False
        for attempt in range(5):               # QPS 限流时退避重试（个人开发者 key 限流阈值较低）
            try:
                params = {"origins": origins, "destination": pts[j], "type": "1", "key": key}
                if AMAP_SERVICE_PRIVATE and not AMAP_SERVICE_PRIVATE.startswith("你的"):
                    params["sig"] = _amap_sig(params, AMAP_SERVICE_PRIVATE)
                url = "https://restapi.amap.com/v3/distance?" + urllib.parse.urlencode(params)
                with urllib.request.urlopen(url, timeout=15) as r:
                    data = json.loads(r.read().decode("utf-8"))
                if data.get("status") != "1":
                    if "QPS" in str(data.get("info", "")):   # 限流 → 等一会儿再试
                        time.sleep(1.5 + attempt * 1.5)
                        continue
                    raise ValueError(data.get("info", "高德接口返回异常"))
                for item in data["results"]:
                    D[int(item["origin_id"]) - 1][j] = int(item["distance"]) / 1000.0
                got = True
                break
            except ValueError:
                break
            except Exception:
                time.sleep(1.5 + attempt * 1.5)
        if not got:                            # 该列失败 → 仅此列用直线×绕行系数兜底，不影响其他列
            n_fallback += 1
            for i in range(n + 1):
                D[i][j] = haversine(lats[i], lons[i], lats[j], lons[j]) * DETOUR_FACTOR
        time.sleep(0.8)                        # 限速，避免连续请求触发高德 QPS 限制
    return D, n_fallback


def _amap_loop_polyline(pts, key):
    """pts=[(lng,lat),...] 首尾=总站、中间=途经站；返回真实道路折线[[lng,lat],...]，失败None"""
    origin = "%.6f,%.6f" % pts[0]
    dest = "%.6f,%.6f" % pts[-1]
    waypoints = ";".join("%.6f,%.6f" % p for p in pts[1:-1])
    url = ("https://restapi.amap.com/v3/direction/driving?origin=%s&destination=%s"
           "&extensions=base&key=%s" % (origin, dest, key))
    if waypoints:
        url += "&waypoints=" + waypoints
    for attempt in range(4):                       # QPS 限流时退避重试
        try:
            with urllib.request.urlopen(url, timeout=12) as r:
                data = json.loads(r.read().decode("utf-8"))
            if data.get("status") == "1" and data.get("route", {}).get("paths"):
                poly = []
                for step in data["route"]["paths"][0]["steps"]:
                    for pair in step["polyline"].split(";"):
                        a, b = pair.split(",")
                        poly.append([float(a), float(b)])
                return poly
            if "QPS" in str(data.get("info", "")):  # 限流 → 等一会儿再试
                time.sleep(1.0 + attempt * 1.5)
                continue
            return None
        except Exception:
            time.sleep(1.0 + attempt * 1.5)
    return None


@st.cache_data(show_spinner="正在获取高德真实道路路线…")
def amap_route_polylines(hub, station_coords, route_indices, key):
    """每条回路一条真实道路折线（origin=dest=总站+途经站，一次请求一条回路）；失败回退直线"""
    polylines = []
    for idxs in route_indices:
        pts = [(hub[1], hub[0])]
        for i in idxs:
            pts.append(station_coords[i - 1])      # (lng, lat)
        pts.append((hub[1], hub[0]))
        poly = _amap_loop_polyline(pts, key) if len(pts) > 2 else None
        if not poly:
            poly = [[p[0], p[1]] for p in pts]     # 直线兜底
        polylines.append(poly)
        time.sleep(0.5)                            # 限速，避免触发高德 QPS 限制
    return polylines


def amap_route_map(hub, stations, routes, polylines, web_key, jscode, sel_idx=None, height=620):
    """高德地图：标记 + 每条回路的真实道路折线；sel_idx 指定单独高亮某辆车（None=全部显示）"""
    hub_lat, hub_lon = hub
    colors = ["#2a78d6", "#eb6834", "#1baf7a", "#9b59b6",
              "#f39c12", "#e74c3c", "#16a085", "#c0392b"]

    sel_stations = set(routes[sel_idx]["route"]) if sel_idx is not None else set()

    markers = [{"name": "顺义总站", "lnglat": [hub_lon, hub_lat], "bg": "#e74c3c", "color": "#fff"}]
    for i, s in enumerate(stations):
        idx = i + 1
        if sel_idx is not None and idx in sel_stations:
            bg, fg = colors[sel_idx % len(colors)], "#fff"   # 选中车辆途经站高亮
        elif sel_idx is not None:
            bg, fg = "#f0f0f0", "#999"                        # 未选中站淡化
        else:
            bg, fg = "#fff", "#333"
        markers.append({"name": s["name"], "lnglat": [s["lon"], s["lat"]], "bg": bg, "color": fg})

    paths = []
    for vi, poly in enumerate(polylines):
        if sel_idx is None:
            paths.append({"path": poly, "color": colors[vi % len(colors)],
                          "weight": 5, "opacity": 0.85})
        elif vi == sel_idx:
            paths.append({"path": poly, "color": colors[vi % len(colors)],
                          "weight": 7, "opacity": 0.95})
        else:
            paths.append({"path": poly, "color": "#999999",
                          "weight": 2, "opacity": 0.2})

    payload = json.dumps({"markers": markers, "paths": paths}, ensure_ascii=False)

    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<style>html,body,#map{{width:100%;height:100%;margin:0;padding:0;}}</style>
<script>window._AMapSecurityConfig = {{ securityJsCode: '{jscode}' }};</script>
<script src="https://webapi.amap.com/maps?v=2.0&key={web_key}"></script>
</head><body><div id="map"></div><script>
var data = {payload};
var map = new AMap.Map('map', {{ zoom: 12, center: [{hub_lon}, {hub_lat}] }});
data.markers.forEach(function(m) {{
    map.add(new AMap.Marker({{
        position: m.lnglat, title: m.name,
        label: {{ content: "<div style='background:" + m.bg + ";color:" + m.color + ";padding:1px 6px;border:1px solid #bbb;border-radius:3px;font-size:11px;white-space:nowrap'>" + m.name + "</div>", direction: 'top' }}
    }}));
}});
data.paths.forEach(function(seg) {{
    new AMap.Polyline({{
        path: seg.path, strokeColor: seg.color, strokeWeight: seg.weight, strokeOpacity: seg.opacity
    }}).setMap(map);
}});
map.setFitView(null, false, [40, 40, 40, 40]);
</script></body></html>"""
    st.iframe(html, height=height)


# ================= 侧边栏参数 =================
with st.sidebar:
    st.markdown("## ⚙️ 参数配置")

    with st.expander("🚚 车辆与碳参数", expanded=True):
        capacity = st.slider("货车载物体积(m³)", 5, 40, 16, 1)   # 4.2米厢式货车典型值
        vol_per_item = st.slider("快递平均体积(m³)", 0.005, 0.20, 0.02, 0.005)
        c_fuel = st.slider("燃油车碳排(kg CO₂e/km)", 0.10, 0.60, 0.2893, 0.0001)   # 0.2893=11L/100km×2.63kgCO₂e/L÷100（轻型货车·统一清单口径）
        c_ev = st.slider("新能源车碳排(kg CO₂e/km)", 0.00, 0.30, 0.1944, 0.0001)   # 0.1944=35kWh/100km×0.5554kgCO₂e/kWh÷100（北京市2023年省级电力因子·统一清单口径）
        ev_rate = st.slider("新能源车渗透率", 0.0, 1.0, 0.15, 0.05)            # 基准15%（成员3第五章），用于混合车队碳排
        c_pack_g = st.slider("单件包装碳排(g CO₂e/件)", 0, 1000, 180, 10)      # 180g/件（第四章口径·统一）
        c_lastmile = st.slider("末端派送+仓储碳排(g CO₂e/件)", 0, 30, 5, 1)   # 派送1.94%+仓储0.04%×全链251g/件≈5g/件（统一清单口径）

    with st.expander("💰 成本与碳交易", expanded=False):
        oil_price = st.slider("柴油价格(元/L)", 5.0, 10.0, 7.5, 0.1)          # 北京柴油约7.5元/L
        elec_price = st.slider("谷段充电电价(元/kWh)", 0.1, 1.0, 0.3, 0.05)   # 谷段0.3元/kWh（清单值；错峰后充电，与第十章10.3节一致）
        carbon_price = st.slider("碳交易价格(元/吨CO₂e)", 0, 200, 80, 5)        # 北京碳配额BEA约80元/吨
        target_rate = st.slider("减排目标(较全燃油减碳)", 0.05, 0.50, 0.20, 0.01)  # 默认目标减碳20%

    with st.expander("📈 情景推演", expanded=False):
        scenario = st.selectbox("业务情景", ["正常", "双十一 / 大促", "恶劣天气"])
        st.caption("情景推演是对未来业务波动的敏感性假设（what-if），非历史数据预测；需求感知用当日已知订单数据。")

    with st.expander("🧬 遗传算法参数", expanded=False):
        ga_gens = st.slider("遗传算法进化代数", 30, 400, 150, 10)
        vehicle_fixed_cost = st.slider("单车固定成本(元/天)", 0, 500, 150, 10)   # 司机+折旧等固定成本
        pack_cost = st.slider("单件包装成本(元/件)", 0.0, 2.0, 1.0, 0.05)         # 一次性纸箱1.0元/个（清单表6·五层加强箱）；循环箱0.3元/次、建议上调0.8~1.3元/次
        recycle_rate = st.slider("包装回收率", 0.0, 0.9, 0.4, 0.05)               # 假设值（清单无此口径：同城循环占比超10%、可循环目标50%）


out_mult, ret_mult, pic_mult = 1.0, 1.0, 1.0
if scenario == "双十一 / 大促":
    out_mult, ret_mult, pic_mult = 2.5, 1.0, 1.6
elif scenario == "恶劣天气":
    out_mult, ret_mult, pic_mult = 0.6, 1.5, 0.7

# ================= 站点信息（可编辑，≥15个）=================
with st.expander("📋 片区配送站（可编辑 · 默认 20 个朝阳区站点）", expanded=False):
    st.caption("到货量来自中转站分拨舱单，揽收量来自揽收预约单，退货量来自退货申请与站点存量。")
    station_df = st.data_editor(
        pd.DataFrame(DEFAULT_STATIONS, columns=["站点名称", "纬度", "经度", "当日到货量(件)", "当日退货量(件)", "当日揽收量(件)"]),
        num_rows="dynamic", key="station_editor",
    )
stations = []
for _, row in station_df.iterrows():
    name = str(row["站点名称"]).strip()
    if name and pd.notna(row["纬度"]) and pd.notna(row["经度"]):
        stations.append({
            "name": name, "lat": float(row["纬度"]), "lon": float(row["经度"]),
            "out": float(row["当日到货量(件)"]) if pd.notna(row["当日到货量(件)"]) else 0.0,
            "ret": float(row["当日退货量(件)"]) if pd.notna(row["当日退货量(件)"]) else 0.0,
            "pic": float(row["当日揽收量(件)"]) if pd.notna(row["当日揽收量(件)"]) else 0.0,
        })
if not stations:
    st.stop()
if len(stations) < 15:
    st.warning("⚠️ 当前有效站点 %d 个，不足 15 个，请补足后再查看路径结果。" % len(stations))
# ================= 大模型碳助手（DeepSeek · 语言层，不参与碳计算） =================
# 密钥与模型：优先环境变量 / Streamlit secrets，其次同目录 llm_config.py（已 .gitignore）；皆无则走内置 mock 兜底。
# 先把脚本所在目录加入 sys.path，确保无论从哪个目录启动都能找到 llm_config.py。
try:
    _SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
except NameError:
    _SCRIPT_DIR = os.getcwd()
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

DEEPSEEK_API_KEY = _get_secret("DEEPSEEK_API_KEY")
DEEPSEEK_BASE_URL = _get_secret("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL = _get_secret("DEEPSEEK_MODEL", "deepseek-chat")
if not DEEPSEEK_API_KEY:                       # 本地 llm_config.py 兜底
    try:
        from llm_config import DEEPSEEK_API_KEY as _k, DEEPSEEK_BASE_URL as _b, DEEPSEEK_MODEL as _m
        DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL = _k, _b, _m
    except ImportError:
        pass

LLM_READY = bool(DEEPSEEK_API_KEY)

SYSTEM_PROMPT = (
    "你是“末端配送绿色化信息平台”的碳管理助手，也是一名懂物流与双碳的顾问。回答要求："
    "1) 涉及平台事实与数字（碳排、占比、成本、里程、满载率等）时，必须以【当前平台数据】为准，不得改动或编造；"
    "2) 在数据基础上，你要给出自己的专业分析与建议（例如绿色循环包装方案、车辆电动化与充换电调度、政策补贴与碳交易、"
    "需求预测与路径优化等），这些建议不要求出现在数据里，可以结合行业常识、政策与企业实践；"
    "3) 给建议时先点明依据的数据，再展开你的判断，并区分“数据事实”与“我的分析建议”；"
    "4) 用简体中文，专业、具体、可落地，可用要点式，字数按问题需要展开；"
    "5) 涉及国际对标时，遵循“结合北京本地实际—考察国际有成效实践—判断是否可取”的借鉴逻辑（本平台服务于北京本地减排、"
    "非出口合规），判断口径：制度路径是否兼容（北京走碳交易 BEA 而非碳税）、成本冲击是否可承受、北京是否已有政策承接，"
    "并明确给出“可取/部分可取/不可取”及理由。"
)


def call_deepseek(messages, timeout=30):
    """调用 DeepSeek chat/completions（OpenAI 兼容）。失败抛异常，由上层兜底。"""
    url = DEEPSEEK_BASE_URL.rstrip("/") + "/chat/completions"
    payload = json.dumps({
        "model": DEEPSEEK_MODEL,
        "messages": messages,
        "temperature": 0.6,
        "stream": False,
    }).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={
        "Content-Type": "application/json",
        "Authorization": "Bearer " + DEEPSEEK_API_KEY,
    })
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data["choices"][0]["message"]["content"]


def compute_carbon_summary(routes, stations, capacity, c_fuel, c_ev, ev_rate,
                           c_pack_g, c_lastmile, oil_price, elec_price,
                           carbon_price, target_rate, out_mult, ret_mult, pic_mult):
    """把当前碳测算结果汇总为结构化字典（与④碳测算页同一套公式，口径一致）。"""
    cap = float(capacity)
    total_km = sum(r["mileage"] for r in routes)
    K = len(routes)
    total_P = sum(r["P"] for r in routes)
    avg_load = total_P / (K * cap) if K else 0.0
    return_km = sum(r["return_km"] for r in routes)
    total_items = sum(s["out"] * out_mult + s["ret"] * ret_mult + s["pic"] * pic_mult for s in stations)
    trans_km = total_items * KM_PER_ITEM   # 清单固定密度等效运输里程（120 km/500 件）
    carbon_fuel = trans_km * c_fuel
    carbon_ev = trans_km * c_ev
    carbon_mixed = trans_km * (ev_rate * c_ev + (1 - ev_rate) * c_fuel)
    save = carbon_fuel - carbon_mixed
    save_max = carbon_fuel - carbon_ev
    unit_fuel = carbon_fuel * 1000 / total_items if total_items else 0.0
    unit_mixed = carbon_mixed * 1000 / total_items if total_items else 0.0
    pack_carbon = total_items * c_pack_g / 1000.0
    lastmile_carbon = total_items * c_lastmile / 1000.0
    total_carbon_mixed = carbon_mixed + lastmile_carbon + pack_carbon
    unit_fullchain = total_carbon_mixed * 1000 / total_items if total_items else 0.0
    cost_fuel_km = 0.11 * oil_price
    cost_ev_km = 0.35 * elec_price
    cost_fuel = total_km * cost_fuel_km
    cost_ev = total_km * cost_ev_km
    cost_mixed = total_km * (ev_rate * cost_ev_km + (1 - ev_rate) * cost_fuel_km)
    cost_save = cost_fuel - cost_mixed
    save_target = carbon_fuel * target_rate
    achieve = save / save_target if save_target else 0.0
    carbon_cost_mixed = carbon_mixed / 1000 * carbon_price
    carbon_asset = save / 1000 * carbon_price                      # 减碳对应的碳减排价值(元，理论折算)
    load_out = sum(r["D"] for r in routes) / (K * cap) if K else 0.0
    load_back = sum(r["R"] for r in routes) / (K * cap) if K else 0.0
    return {
        "n_stations": len(stations), "total_km": total_km, "K": K, "avg_load": avg_load,
        "return_km": return_km, "carbon_fuel": carbon_fuel, "carbon_ev": carbon_ev,
        "carbon_mixed": carbon_mixed, "save": save, "save_max": save_max,
        "total_items": total_items, "unit_fuel": unit_fuel, "unit_mixed": unit_mixed,
        "pack_carbon": pack_carbon, "lastmile_carbon": lastmile_carbon,
        "total_carbon_mixed": total_carbon_mixed, "unit_fullchain": unit_fullchain,
        "cost_fuel": cost_fuel, "cost_ev": cost_ev, "cost_mixed": cost_mixed, "cost_save": cost_save,
        "save_target": save_target, "achieve": achieve,
        "carbon_cost_mixed": carbon_cost_mixed, "carbon_asset": carbon_asset,
        "load_out": load_out, "load_back": load_back,
        "ev_rate": ev_rate, "carbon_price": carbon_price, "c_pack_g": c_pack_g,
        "c_lastmile": c_lastmile, "oil_price": oil_price, "elec_price": elec_price,
        "target_rate": target_rate,
    }


def format_ctx_text(c):
    """把结构化数字压缩成 prompt 上下文（全部来自平台，不编造）。"""
    denom = c["total_carbon_mixed"] or 1.0
    r_trans = c["carbon_mixed"] / denom * 100
    r_pack = c["pack_carbon"] / denom * 100
    r_last = c["lastmile_carbon"] / denom * 100
    return (
        "【当前平台数据（全部来自平台碳测算结果，仅可引用、禁止改动或外推）】\n"
        f"· 站点 {c['n_stations']} 个，总业务量 {c['total_items']:.0f} 件/日，共 {c['K']} 辆车，"
        f"总里程 {c['total_km']:.1f} km，回程里程 {c['return_km']:.1f} km。\n"
        f"· 平均满载率 {c['avg_load']*100:.1f}%，去程 {c['load_out']*100:.1f}%，回程 {c['load_back']*100:.1f}%。\n"
        f"· 运输碳排：全燃油 {c['carbon_fuel']:.1f} kg、混合车队(新能源渗透率 {c['ev_rate']*100:.0f}%) {c['carbon_mixed']:.1f} kg、"
        f"全新能源 {c['carbon_ev']:.1f} kg；较全燃油减碳 {c['save']:.1f} kg。\n"
        f"· 单件运输碳排：全燃油 {c['unit_fuel']:.1f} g/件、混合 {c['unit_mixed']:.1f} g/件。\n"
        f"· 全链碳排(混合口径)=运输 {c['carbon_mixed']:.1f} + 末端派送仓储 {c['lastmile_carbon']:.1f} + 包装 {c['pack_carbon']:.1f}"
        f" = 合计 {c['total_carbon_mixed']:.1f} kg；单件全链 {c['unit_fullchain']:.1f} g/件。\n"
        f"· 环节占比：运输 {r_trans:.1f}%、包装 {r_pack:.1f}%、末端派送+仓储 {r_last:.1f}%。\n"
        f"· 能耗成本：全燃油 {c['cost_fuel']:.0f} 元/天、混合 {c['cost_mixed']:.0f} 元/天、全新能源 {c['cost_ev']:.0f} 元/天；"
        f"较全燃油降本 {c['cost_save']:.0f} 元/天。\n"
        f"· 减排目标(较全燃油 {c['target_rate']*100:.0f}%)：目标 {c['save_target']:.1f} kg、当前减碳 {c['save']:.1f} kg、"
        f"达成率 {c['achieve']*100:.0f}%。\n"
        f"· 碳交易：碳价 {c['carbon_price']:.0f} 元/吨，混合车队碳成本 {c['carbon_cost_mixed']:.0f} 元/天，"
        f"减碳对应碳减排价值（理论折算）{c['carbon_asset']:.0f} 元/天。\n"
        f"· 参数口径：柴油 2.63 kgCO₂e/L、电力 0.5554 kgCO₂e/kWh、油价 {c['oil_price']:.1f} 元/L、"
        f"电价 {c['elec_price']:.1f} 元/kWh、单件包装碳排 {c['c_pack_g']:.0f} g/件、末端派送+仓储 {c['c_lastmile']:.0f} g/件；"
        "其中“运输”碳排按《统一清单》固定密度口径折算（120 km/500 件 = 0.24 km/件）。"
    )


def mock_answer(question, c):
    """无 API 时的兜底：规则模板 + 平台真实数据作答（不联网、也不编造）。"""
    q = question
    denom = c["total_carbon_mixed"] or 1.0
    r_pack = c["pack_carbon"] / denom * 100
    r_trans = c["carbon_mixed"] / denom * 100
    r_last = c["lastmile_carbon"] / denom * 100
    lines = [f"（内置兜底回答 · 未调用大模型）当前平台核心数据：全链碳排 {c['total_carbon_mixed']:.1f} kg/日、"
             f"单件 {c['unit_fullchain']:.1f} g/件；其中包装占 {r_pack:.1f}%、运输占 {r_trans:.1f}%、末端派送+仓储占 {r_last:.1f}%。"]
    if any(k in q for k in ["包装", "纸箱", "占比", "为什么"]):
        lines.append(f"包装是当前最大碳排环节（{r_pack:.1f}%）。当前一次性纸箱 {c['c_pack_g']:.0f} g/件、成本 1.0 元/个；"
                     "换循环箱可把包装碳排降到一次性纸箱的约 10%，是降碳同时降本的首选抓手。")
    if any(k in q for k in ["降", "减碳", "减排", "建议", "措施", "优化"]):
        lines.append(f"降碳建议（按数据排序）：① 包装环节占 {r_pack:.1f}%，换循环箱收益最大；"
                     f"② 运输侧把新能源渗透率从 {c['ev_rate']*100:.0f}% 提高，单车电动化约降 33%；"
                     f"③ 当前碳价 {c['carbon_price']:.0f} 元/吨下碳成本仅 {c['carbon_cost_mixed']:.0f} 元/天，"
                     "碳价对决策影响有限，需叠加国四报废更新补贴（最高 14 万元/辆）等政策合力。")
    if any(k in q for k in ["碳资产", "碳交易", "碳价", "BEA", "交易"]):
        lines.append(f"按北京碳配额（BEA）{c['carbon_price']:.0f} 元/吨折算，较全燃油减碳 {c['save']:.1f} kg，"
                     f"对应碳减排价值（理论折算）约 {c['carbon_asset']:.0f} 元/天（实际可交易性取决于核证与项目资格）。")
    if any(k in q for k in ["全链", "口径", "运输", "251"]):
        lines.append("口径说明：全链碳排 = 运输 + 末端派送仓储 + 包装；其中运输碳排按《统一清单》固定密度口径折算"
                     "（120 km/500 件 = 0.24 km/件），与统一清单 251 g/件口径一致。")
    if any(k in q for k in ["成本", "降本", "省钱", "省"]):
        lines.append(f"降本测算：混合车队能耗成本 {c['cost_mixed']:.0f} 元/天，较全燃油 {c['cost_fuel']:.0f} 元/天，"
                     f"每天节省 {c['cost_save']:.0f} 元。")
    if len(lines) == 1:
        lines.append("你可以问我：包装为何占比最高、如何再降碳、碳减排价值怎么算、全链口径等。")
    return "\n\n".join(lines)


def generate_answer(question, c):
    ctx_text = format_ctx_text(c)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "问题：" + question + "\n\n" + ctx_text},
    ]
    if LLM_READY:
        try:
            return call_deepseek(messages)
        except Exception as e:
            return mock_answer(question, c) + "\n\n（注：大模型调用失败，已退回内置兜底回答，原因：%s）" % e
    return mock_answer(question, c)


def build_report(c, ai_summary=""):
    denom = c["total_carbon_mixed"] or 1.0
    r_trans = c["carbon_mixed"] / denom * 100
    r_pack = c["pack_carbon"] / denom * 100
    r_last = c["lastmile_carbon"] / denom * 100
    md = []
    md.append("# 末端配送碳核算报告")
    md.append("")
    md.append("## 一、核算口径")
    md.append("- 方法：碳排放因子法（碳排放 = 活动数据 × 排放因子）")
    md.append("- 因子：柴油 2.63 kgCO₂e/L；电力 0.5554 kgCO₂e/kWh（北京市 2023 年省级电力因子）")
    md.append("- 范围：运输 + 末端派送仓储 + 包装；运输碳排按《统一清单》固定密度折算（120 km/500 件）")
    md.append("")
    md.append("## 二、业务规模")
    md.append(f"- 站点 {c['n_stations']} 个；当日业务量 {c['total_items']:.0f} 件")
    md.append(f"- 车辆 {c['K']} 辆；总里程 {c['total_km']:.1f} km；平均满载率 {c['avg_load']*100:.1f}%")
    md.append("")
    md.append("## 三、分环节碳排（混合车队 · 新能源渗透率 %.0f%%）" % (c["ev_rate"] * 100))
    md.append("")
    md.append("| 环节 | 碳排(kg/日) | 占比 |")
    md.append("|---|---|---|")
    md.append(f"| 运输（清单固定密度） | {c['carbon_mixed']:.1f} | {r_trans:.1f}% |")
    md.append(f"| 末端派送+仓储 | {c['lastmile_carbon']:.1f} | {r_last:.1f}% |")
    md.append(f"| 包装 | {c['pack_carbon']:.1f} | {r_pack:.1f}% |")
    md.append(f"| **全链合计** | **{c['total_carbon_mixed']:.1f}** | 100% |")
    md.append("")
    md.append(f"- 单件全链碳排：{c['unit_fullchain']:.1f} g CO₂e/件")
    md.append("")
    md.append("## 四、减排与成本分析")
    md.append(f"- 运输碳排：全燃油 {c['carbon_fuel']:.1f} kg → 混合 {c['carbon_mixed']:.1f} kg，减碳 {c['save']:.1f} kg")
    md.append(f"- 能耗成本：全燃油 {c['cost_fuel']:.0f} 元/天 → 混合 {c['cost_mixed']:.0f} 元/天，降本 {c['cost_save']:.0f} 元/天")
    md.append(f"- 减排目标：较全燃油 {c['target_rate']*100:.0f}%（{c['save_target']:.1f} kg），当前达成率 {c['achieve']*100:.0f}%")
    md.append("")
    md.append("## 五、碳减排价值（理论折算）")
    md.append(f"- 碳价：{c['carbon_price']:.0f} 元/吨（北京 BEA，可调）")
    md.append(f"- 减碳对应碳减排价值（理论折算）：{c['carbon_asset']:.0f} 元/天；混合车队碳成本：{c['carbon_cost_mixed']:.0f} 元/天")
    if ai_summary:
        md.append("")
        md.append("## 六、AI 管理建议")
        md.append(ai_summary)
    return "\n".join(md)


# ================= 页面 =================
tab_sense, tab_route, tab_carbon, tab_assistant, tab_charge = st.tabs(["① 需求感知", "② 班线规划", "③ 碳测算与碳管理", "④ 大模型碳助手", "⑤ 充换电调度"])

# 点击「④ 大模型碳助手」标签时，滚动到该页标题（标题置顶、提问框 sticky 置底，两者同时可见）
components.html("""
<script>
(function () {
  function assistantTitle() {
    var doc = window.parent.document;
    var heads = doc.querySelectorAll('h1, h2, h3');
    for (var i = 0; i < heads.length; i++) {
      var h = heads[i];
      if (h.textContent.indexOf('大模型碳助手') !== -1 && h.getBoundingClientRect().height > 0) {
        return h;
      }
    }
    return null;
  }
  function scrollWhenReady() {
    var h = assistantTitle();
    if (h) { h.scrollIntoView({behavior: 'smooth', block: 'start'}); return; }
    var tries = 0;
    var timer = setInterval(function () {
      tries += 1;
      var hh = assistantTitle();
      if (hh || tries > 40) {
        clearInterval(timer);
        if (hh) { hh.scrollIntoView({behavior: 'smooth', block: 'start'}); }
      }
    }, 100);
  }
  function attach() {
    var tabs = window.parent.document.querySelectorAll('[data-testid="stTabs"] [data-testid="stTab"]');
    if (!tabs.length) { setTimeout(attach, 300); return; }
    for (var i = 0; i < tabs.length; i++) {
      var tab = tabs[i];
      if (tab.textContent.indexOf('大模型碳助手') !== -1) {
        tab.addEventListener('click', function () { scrollWhenReady(); });
      }
    }
  }
  attach();
})();
</script>
""", height=0)

# ---- Tab 1 需求感知（订单数据） ----
with tab_sense:
    st.subheader("需求感知 · 来自订单 / 分拨系统的已知数据")
    st.caption("到货量来自中转站分拨舱单，揽收量来自揽收预约单，退货量来自退货申请与站点存量。")

    st.table(pd.DataFrame({
        "流量": ["到货量（正向）", "揽收量（逆向）", "退货量（逆向）"],
        "数据来源": ["中转站分拨舱单 / 订单系统", "客户揽收预约单", "退货申请 + 站点退货存量"],
        "性质": ["确定（已到货）", "确定（已预约）", "确定（已申请/已留存）"],
    }))

    st.caption("各站点当日需求感知量")
    st.dataframe(pd.DataFrame({
        "站点": [s["name"] for s in stations],
        "到货量(件)": [int(s["out"] * out_mult) for s in stations],
        "退货量(件)": [int(s["ret"] * ret_mult) for s in stations],
        "揽收量(件)": [int(s["pic"] * pic_mult) for s in stations],
    }))

    names = [s["name"] for s in stations]
    out_eff = np.array([s["out"] * out_mult for s in stations])
    ret_eff = np.array([s["ret"] * ret_mult for s in stations])
    pic_eff = np.array([s["pic"] * pic_mult for s in stations])
    x = np.arange(len(stations))
    fig, ax = plt.subplots(figsize=(12, 6))
    w = 0.25
    b1 = ax.bar(x - w, out_eff, w, label="到货量", color="#2a78d6")
    b2 = ax.bar(x, ret_eff, w, label="退货量", color="#eb6834")
    b3 = ax.bar(x + w, pic_eff, w, label="揽收量", color="#1baf7a")
    ax.set_xticks(x)
    ax.set_xticklabels(names, rotation=45, ha="right", fontsize=8)
    ax.set_ylabel("件数")
    ax.set_ylim(0, max(out_eff) * 1.22)          # 顶部留白，避免数值标注被截断
    ax.legend(frameon=False)
    ax.grid(True, axis="y", color="#eeeeee")
    ax.set_title("各站点需求感知量（到货 / 退货 / 揽收）")
    for bars in (b1, b2, b3):                    # 每根柱子标注数值，退货量(20~56件)虽矮也能读清
        ax.bar_label(bars, fmt="%.0f", fontsize=7, padding=2, rotation=90)
    fig.tight_layout()                           # 收缩边距，避免旋转后的站名/数值标签被裁掉
    st.pyplot(fig)

# ---- Tab 2 班线规划（含拆分配送） ----
with tab_route:
    st.subheader("配送班线规划（顺义顺航中转站出发 · 环形返回）")

    # 1) 各站点装载体积（去程=到货，回程=退货+揽收）
    station_demand = [s["out"] * out_mult * vol_per_item for s in stations]                 # 去程到货体积(m³)，含情景系数
    station_pickup = [(s["ret"] * ret_mult + s["pic"] * pic_mult) * vol_per_item for s in stations]  # 回程体积=退货+揽收(m³)，含情景系数

    # 2) 超载站点拆分为多辆车（SDVRP 拆分配送）：单站峰值超过单车容量时，按“装不下就分多辆”拆成若干配送任务
    cap = float(capacity)
    tasks = []                                   # 拆分后的“配送任务”列表（同坐标的虚拟节点）
    n_split = 0
    for i, s in enumerate(stations):
        d, p = station_demand[i], station_pickup[i]
        k = 1 if max(d, p) <= cap else int(np.ceil(max(d, p) / cap))   # 该站峰值所需的车辆数
        if k > 1:
            n_split += 1
        for part in range(k):
            tasks.append({
                "name": s["name"] if k == 1 else "%s(%d/%d)" % (s["name"], part + 1, k),
                "lat": s["lat"], "lon": s["lon"],
                "d": d / k, "p": p / k,
            })

    demands = np.array([t["d"] for t in tasks])      # 去程体积（任务级）
    pickups = np.array([t["p"] for t in tasks])      # 回程体积（任务级）
    task_lats = [HUB_LAT] + [t["lat"] for t in tasks]
    task_lons = [HUB_LON] + [t["lon"] for t in tasks]

    if n_split:
        st.info("有 %d 个站点单日装载量超过单车容量（%.1f m³），已拆分为多辆车配送。" % (n_split, cap))

    # 3) 距离矩阵与班线规划
    if AMAP_SERVICE_KEY and not AMAP_SERVICE_KEY.startswith("你的"):
        D, n_fb = amap_dist_matrix(tuple(task_lats), tuple(task_lons), AMAP_SERVICE_KEY)
        dist_note = "高德真实道路距离"
        if n_fb:
            st.warning("⚠️ 高德接口有 %d 个站点触发限流，其相关距离已用「直线×绕行系数 %.2f」近似道路距离兜底。" % (n_fb, DETOUR_FACTOR))
    else:
        D = dist_matrix(task_lats, task_lons) * DETOUR_FACTOR
        dist_note = "直线距离×绕行系数(%.2f，近似道路距离)" % DETOUR_FACTOR
    # 综合成本系数：遗传算法目标 = 能耗＋固定成本＋碳成本（包装为常数项，展示层另加）
    cost_ev_km = 0.35 * elec_price                       # 新能源能耗成本 元/km
    cost_fuel_km = 0.11 * oil_price                      # 燃油能耗成本 元/km
    alpha = (ev_rate * cost_ev_km + (1 - ev_rate) * cost_fuel_km) \
        + carbon_price / 1000.0 * (ev_rate * c_ev + (1 - ev_rate) * c_fuel)   # 元/km（能耗＋碳成本）

    # 遗传算法结果缓存：同一组输入直接命中缓存，避免切换标签时重跑进化计算（页面切换变慢的主因）
    routes, ga_total, ga_hist, ga_mean = _solve_vrpspd(
        tuple(demands.tolist()), tuple(pickups.tolist()),
        tuple(map(tuple, D.tolist())), cap, alpha, vehicle_fixed_cost, ga_gens)

    # 4) 各站点装载体积与所需车辆数（件数口径见「① 需求感知」，此处只保留班线规划用的体积/车辆数）
    need_df = pd.DataFrame({
        "站点": [s["name"] for s in stations],
        "去程体积(到货, m³)": np.round(station_demand, 2),
        "回程体积(退货+揽收, m³)": np.round(station_pickup, 2),
        "所需车辆数": [1 if max(station_demand[i], station_pickup[i]) <= cap
                       else int(np.ceil(max(station_demand[i], station_pickup[i]) / cap))
                       for i in range(len(stations))],
    })
    st.caption("各站点装载体积与所需车辆数（体积 = 件数 × 快递平均体积 %.2f m³/件；件数明细见「① 需求感知」）" % vol_per_item)
    st.dataframe(need_df)

    # 5) 车辆配载方案（任务级，拆分站点会以“站点名(1/N)”形式出现多次）
    rrows = []
    for vi, r in enumerate(routes):
        names = [tasks[i - 1]["name"] for i in r["route"]]
        rrows.append({
            "车辆": "车%d" % (vi + 1),
            "路线": "顺义顺航中转站 → " + " → ".join(names) + " → 顺义顺航中转站",
            "去程装载(m³)": round(r["D"], 2),
            "回程装载(退货+揽收, m³)": round(r["R"], 2),
            "峰值(m³)": round(r["P"], 2),
            "满载率": "%.1f%%" % (r["load_rate"] * 100),
            "里程(km)": round(r["mileage"], 1),
        })
    st.caption("车辆配载方案（遗传算法 · 共 %d 辆车 · 距离口径：%s）" % (len(routes), dist_note))
    st.dataframe(pd.DataFrame(rrows))

    # 遗传算法收敛过程（综合成本 = 能耗＋固定成本＋碳成本，不含包装；包装为常数项）
    st.markdown("---")
    st.subheader("🧬 遗传算法收敛过程（综合成本 = 能耗＋固定成本＋碳成本，不含包装）")
    total_items = sum(s["out"] * out_mult + s["ret"] * ret_mult + s["pic"] * pic_mult for s in stations)
    ga_bd = objective_breakdown(routes, ev_rate, c_ev, c_fuel,
                                cost_ev_km, cost_fuel_km, carbon_price,
                                vehicle_fixed_cost, pack_cost, recycle_rate, total_items)
    fig2, ax2 = plt.subplots(figsize=(10, 3.4))
    # 种群均值做滚动平均平滑，去除锦标赛选择的抖动，凸显均值逐步逼近最优的收敛趋势
    _w = 5
    if len(ga_mean) >= _w:
        _mean_s = np.convolve(ga_mean, np.ones(_w) / _w, mode="valid")
        ax2.plot(np.arange(_w - 1, len(ga_mean)), _mean_s,
                 color="#9bb8d3", lw=1.8, ls="--", label="种群平均综合成本(平滑)")
    else:
        ax2.plot(ga_mean, color="#9bb8d3", lw=1.8, ls="--", label="种群平均综合成本(平滑)")
    ax2.plot(ga_hist, color="#1baf7a", lw=2.4, label="最优综合成本(不含包装)")
    ax2.set_xlabel("进化代数")
    ax2.set_ylabel("综合成本 (元/天)")
    ax2.set_title("遗传算法收敛过程：种群平均成本逐步逼近最优")
    ax2.legend(frameon=False)
    ax2.grid(True, color="#eeeeee")
    fig2.tight_layout()
    st.pyplot(fig2)
    st.caption("遗传算法以「能耗＋固定成本＋碳成本」为综合目标（包装为常数项），"
               "种群平均成本随进化收敛，收敛后最优综合成本（不含包装）%.0f 元/天、共 %d 辆车、总里程 %.1f km。"
               % (ga_total, ga_bd["K"], ga_bd["total_km"]))

    veh_opts = ["全部车辆"] + ["车%d" % (i + 1) for i in range(len(routes))]
    veh_sel = st.selectbox("地图显示：查看全部或某一辆车的路线", veh_opts)
    sel_idx = None if veh_sel == "全部车辆" else veh_opts.index(veh_sel) - 1

    if AMAP_READY:
        task_coords = tuple((t["lon"], t["lat"]) for t in tasks)
        route_indices = tuple(tuple(r["route"]) for r in routes)
        polylines = amap_route_polylines((HUB_LAT, HUB_LON), task_coords,
                                         route_indices, AMAP_SERVICE_KEY)
        amap_route_map((HUB_LAT, HUB_LON), tasks, routes, polylines,
                       AMAP_WEB_KEY, AMAP_WEB_JSCODE, sel_idx=sel_idx)
    else:
        fig, ax = plt.subplots(figsize=(8, 8))
        ax.scatter([HUB_LON], [HUB_LAT], c="red", s=160, marker="s", zorder=6, label="顺义顺航中转站")
        for i, t in enumerate(tasks):
            ax.scatter(t["lon"], t["lat"], c="#888888", s=45, zorder=5)
            ax.text(t["lon"], t["lat"], t["name"], fontsize=8)
        colors = plt.cm.tab10.colors
        for vi, r in enumerate(routes):
            color = colors[vi % len(colors)]
            xs = [HUB_LON] + [task_lons[i] for i in r["route"]] + [HUB_LON]
            ys = [HUB_LAT] + [task_lats[i] for i in r["route"]] + [HUB_LAT]
            ax.plot(xs, ys, color=color, marker="o", lw=2,
                    label="车%d (%.0f%%)" % (vi + 1, r["load_rate"] * 100))
        ax.set_xlabel("经度")
        ax.set_ylabel("纬度")
        ax.legend(frameon=False, fontsize=8)
        ax.set_title("配送路线示意图")
        fig.tight_layout()
        st.pyplot(fig)

# ---- Tab 3 碳测算 ----
with tab_carbon:
    st.subheader("碳测算与碳管理（降碳降本 · 减排目标 · 碳交易对接）")
    total_km = sum(r["mileage"] for r in routes)
    K = len(routes)
    total_P = sum(r["P"] for r in routes)
    avg_load = total_P / (K * cap) if K else 0.0
    return_km = sum(r["return_km"] for r in routes)
    total_items = sum(s["out"] * out_mult + s["ret"] * ret_mult + s["pic"] * pic_mult for s in stations)
    trans_km = total_items * KM_PER_ITEM   # 清单固定密度等效运输里程（120 km/500 件）
    carbon_fuel = trans_km * c_fuel                                      # 全燃油基线
    carbon_ev = trans_km * c_ev                                          # 全新能源上限
    carbon_mixed = trans_km * (ev_rate * c_ev + (1 - ev_rate) * c_fuel)  # 混合车队（当前渗透率）
    save = carbon_fuel - carbon_mixed                                    # 相对全燃油的减碳量
    save_max = carbon_fuel - carbon_ev                                   # 全新能源最大减碳潜力

    unit_fuel = carbon_fuel * 1000 / total_items if total_items else 0.0   # 单件碳排 g CO₂e/件
    unit_mixed = carbon_mixed * 1000 / total_items if total_items else 0.0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("总里程", "%.1f km" % total_km)
    c2.metric("车辆数", "%d 辆" % K)
    c3.metric("平均满载率", "%.1f%%" % (avg_load * 100))
    c4.metric("回程里程", "%.1f km" % return_km)

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("全燃油碳排", "%.1f kg CO₂e" % carbon_fuel)
    c6.metric("混合车队碳排（渗透率 %.0f%%）" % (ev_rate * 100), "%.1f kg CO₂e" % carbon_mixed)
    c7.metric("全新能源碳排", "%.1f kg CO₂e" % carbon_ev)
    c8.metric("较全燃油减碳", "%.1f kg (%.0f%%)" % (save, save / carbon_fuel * 100 if carbon_fuel else 0))

    c9, c10, c11 = st.columns(3)
    c9.metric("单件碳排·全燃油", "%.1f g CO₂e/件" % unit_fuel)
    c10.metric("单件碳排·混合", "%.1f g CO₂e/件" % unit_mixed)
    c11.metric("全新能源减碳潜力", "%.1f kg (%.0f%%)" % (save_max, save_max / carbon_fuel * 100 if carbon_fuel else 0))

    st.caption("运输碳排按《统一清单》固定密度折算（120 km/500 件 = 0.24 km/件），与上方「总里程」（班线规划真实路线）口径不同；"
               "能耗成本仍按真实路线里程测算。")

    # ---- 包装 + 末端派送环节碳排（对接第四章全链口径）----
    pack_carbon = total_items * c_pack_g / 1000.0              # 当日包装碳排(kg CO₂e)
    lastmile_carbon = total_items * c_lastmile / 1000.0        # 当日末端派送+仓储碳排(kg CO₂e)
    total_carbon_mixed = carbon_mixed + lastmile_carbon + pack_carbon   # 全链碳排 = 运输 + 末端派送 + 包装
    unit_fullchain = total_carbon_mixed * 1000 / total_items if total_items else 0.0  # 单件全链碳排 g CO₂e/件

    st.divider()
    st.subheader("包装与末端派送环节碳排")
    p1, p2, p3, p4 = st.columns(4)
    p1.metric("单件包装碳排系数", "%.0f g CO₂e/件" % c_pack_g)
    p2.metric("单件末端派送+仓储碳排", "%.0f g CO₂e/件" % c_lastmile)
    p3.metric("全链总碳排·混合(运输+末端+包装)", "%.1f kg CO₂e" % total_carbon_mixed)
    p4.metric("单件全链碳排", "%.1f g CO₂e/件" % unit_fullchain)

    # ---- 降本测算（降碳降本双目标协同）----
    cost_fuel_km = 0.11 * oil_price          # 燃油能耗成本 = 11L/100km × 油价 → 元/km
    cost_ev_km = 0.35 * elec_price           # 新能源能耗成本 = 35kWh/100km × 电价 → 元/km
    cost_fuel = total_km * cost_fuel_km      # 全燃油车队能耗成本(元)
    cost_ev = total_km * cost_ev_km          # 全新能源车队能耗成本(元)
    cost_mixed = total_km * (ev_rate * cost_ev_km + (1 - ev_rate) * cost_fuel_km)
    cost_save = cost_fuel - cost_mixed       # 较全燃油降本(元)

    st.divider()
    st.subheader("降本测算（降碳降本双目标协同）")
    d1, d2, d3, d4 = st.columns(4)
    d1.metric("全燃油能耗成本", "%.0f 元/天" % cost_fuel)
    d2.metric("混合车队能耗成本", "%.0f 元/天" % cost_mixed)
    d3.metric("全新能源能耗成本", "%.0f 元/天" % cost_ev)
    d4.metric("较全燃油降本", "%.0f 元 (%.0f%%)" % (cost_save, cost_save / cost_fuel * 100 if cost_fuel else 0))

    # ---- 减排目标管理 + 碳交易对接 ----
    save_target = carbon_fuel * target_rate           # 减排目标(kg CO₂e)
    achieve = save / save_target if save_target else 0.0
    carbon_cost_mixed = carbon_mixed / 1000 * carbon_price   # 混合车队碳成本(元)
    carbon_asset = save / 1000 * carbon_price                # 减碳对应的碳减排价值(元，理论折算)

    st.divider()
    st.subheader("减排目标管理 与 碳交易对接")
    e1, e2, e3, e4 = st.columns(4)
    e1.metric("减排目标(较全燃油)", "%.0f kg (%.0f%%)" % (save_target, target_rate * 100))
    e2.metric("当前减碳量", "%.0f kg" % save, delta="%.0f kg" % (save - save_target))
    e3.metric("目标达成率", "%.0f%%" % (achieve * 100))
    e4.metric("减碳价值(理论折算, %.0f 元/吨)" % carbon_price, "%.0f 元" % carbon_asset)
    st.caption("按北京碳配额（BEA）折算：混合车队碳成本约 %.0f 元/天；较全燃油减碳的部分按碳价折算为碳减排价值（理论参考值，实际可交易性取决于核证与项目资格）。"
               % carbon_cost_mixed)

    load_out = sum(r["D"] for r in routes) / (K * cap) if K else 0.0
    load_back = sum(r["R"] for r in routes) / (K * cap) if K else 0.0
    st.caption("去程平均满载率 %.1f%%；回程平均满载率 %.1f%%。" % (load_out * 100, load_back * 100))
    st.caption("全链碳排 = 运输（业务量 × 固定单位里程 0.24 km/件 × 碳排系数）＋ 末端派送与仓储（单件约 5g CO₂e）＋ 包装（单件约 180g CO₂e）。"
               "口径：运输碳排按《统一清单》固定密度折算（燃油货车 120 km/500 件、电动货车 120 km/500 件）；"
               "柴油 2.63 kgCO₂e/L、电力 0.5554 kgCO₂e/kWh（北京市2023年省级电力因子）。")

# ---- Tab 4 大模型碳助手 ----
with tab_assistant:
    st.subheader("🤖 大模型碳助手（数据驱动 · 语言层）")
    st.caption("碳排数字仍由平台因子法 / 路线算法确定计算；大模型只负责用自然语言解释、归纳并生成报告，不参与任何计算。")

    ctx = compute_carbon_summary(routes, stations, capacity, c_fuel, c_ev, ev_rate,
                                 c_pack_g, c_lastmile, oil_price, elec_price,
                                 carbon_price, target_rate, out_mult, ret_mult, pic_mult)

    if LLM_READY:
        st.info("已连接大模型服务，回答由大模型生成；若调用失败会自动退回内置兜底。")
    else:
        st.warning("未配置大模型密钥，当前走内置兜底（不联网，仍引用平台真实数据）。请在 llm_config.py 填入密钥后刷新。")

    b1, b2, b3 = st.columns(3)
    with b1:
        if st.button("🤖 生成 AI 管理建议"):
            with st.spinner("大模型生成中…"):
                st.session_state.llm_summary = generate_answer(
                    "请基于以上数据，给出三条按优先级排序的降碳降本建议，每条说明依据的是哪个数字。", ctx)
    with b2:
        if st.button("📄 一键生成碳核算报告"):
            ai_sum = st.session_state.get("llm_summary", "")
            st.session_state.llm_report = build_report(ctx, ai_sum)
    with b3:
        if st.button("🧹 清空对话"):
            st.session_state.llm_msgs = []
            st.session_state.pop("llm_report", None)
            st.session_state.pop("llm_summary", None)

    if st.session_state.get("llm_report"):
        st.download_button("⬇️ 下载碳核算报告 (Markdown)",
                           data=st.session_state.llm_report.encode("utf-8"),
                           file_name="末端配送碳核算报告.md", mime="text/markdown")
        with st.expander("预览碳核算报告", expanded=False):
            st.markdown(st.session_state.llm_report)

    if "llm_msgs" not in st.session_state:
        st.session_state.llm_msgs = []

    # 对话区：固定高度的可滚动“框”，回答内容多了就在框内上下滚动
    chat_box = st.container(border=True, height=400, autoscroll=True)
    with chat_box:
        for m in st.session_state.llm_msgs:
            with st.chat_message(m["role"]):
                st.markdown(m["content"])

    q = st.chat_input("向碳助手提问，例如：包装为什么占比最高？怎么再降 10% 碳排？")
    if q:
        st.session_state.llm_msgs.append({"role": "user", "content": q})
        with chat_box:
            with st.chat_message("user"):
                st.markdown(q)
            with st.chat_message("assistant"):
                with st.spinner("碳助手分析中…"):
                    ans = generate_answer(q, ctx)
                st.markdown(ans)
        st.session_state.llm_msgs.append({"role": "assistant", "content": ans})

# ---- Tab 5 充换电调度（分时电价错峰） ----
with tab_charge:
    st.subheader("智能充换电调度（优先级调度 + 分时电价错峰）")
    st.caption("充电负荷按「班线规划真实总里程 × 电耗(35 kWh/100km)」折算；错峰调度把可转移的充电负荷从峰段(8:00—22:00)移到谷段(22:00—次日 8:00)，降低电费并缓解日间充电排队。")

    total_km_charge = sum(r["mileage"] for r in routes)
    K_charge = len(routes)
    energy_need = total_km_charge * 0.35                     # kWh（35kWh/100km · 统一清单口径）

    peak_price = st.slider("峰段电价(元/kWh · 8:00—22:00)", 0.5, 2.0, 1.0, 0.1)
    valley_price = st.slider("谷段电价(元/kWh · 22:00—次日8:00)", 0.1, 1.0, 0.3, 0.05)
    valley_share = st.slider("可错峰移入谷段的负荷比例", 0.0, 1.0, 0.8, 0.05)

    cost_all_peak = energy_need * peak_price
    cost_shifted = energy_need * (valley_share * valley_price + (1 - valley_share) * peak_price)
    saving = cost_all_peak - cost_shifted
    saving_pct = saving / cost_all_peak * 100 if cost_all_peak else 0.0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("日充电负荷", "%.0f kWh" % energy_need)
    c2.metric("全峰段电费", "%.0f 元/天" % cost_all_peak)
    c3.metric("错峰后电费", "%.0f 元/天" % cost_shifted)
    c4.metric("错峰节省", "%.0f 元 (%.0f%%)" % (saving, saving_pct))

    fig, ax = plt.subplots(figsize=(9, 4.2))
    labels = ["全峰段充电", "错峰调度后"]
    peak_load = [energy_need, energy_need * (1 - valley_share)]
    valley_load = [0.0, energy_need * valley_share]
    ax.bar(labels, peak_load, color="#eb6834", label="峰段负荷（%.1f 元/kWh）" % peak_price)
    ax.bar(labels, valley_load, bottom=peak_load, color="#1baf7a", label="谷段负荷（%.1f 元/kWh）" % valley_price)
    ax.set_ylabel("日充电负荷 (kWh)")
    ax.set_ylim(0, energy_need * 1.25)
    ax.grid(True, axis="y", color="#eeeeee")
    ax.legend(frameon=False)
    ax.set_title("峰谷充电负荷错峰对比（%d 辆车 · 总里程 %.1f km）" % (K_charge, total_km_charge))
    for i in range(2):
        ax.text(i, energy_need * 1.06, "%.0f kWh" % energy_need, ha="center", va="bottom", fontsize=9)
        if peak_load[i] > 0:
            ax.text(i, peak_load[i] / 2, "峰 %.0f" % peak_load[i], ha="center", va="center", fontsize=8, color="white")
        if valley_load[i] > 0:
            ax.text(i, peak_load[i] + valley_load[i] / 2, "谷 %.0f" % valley_load[i], ha="center", va="center", fontsize=8, color="white")
    fig.tight_layout()
    st.pyplot(fig)

    st.caption("优先级规则：谷段优先排充、峰段兜底。%.0f%% 的充电负荷移入谷段后，日充电电费由 %.0f 元降至 %.0f 元，节省 %.0f 元（下降 %.0f%%）。"
               % (valley_share * 100, cost_all_peak, cost_shifted, saving, saving_pct))
    st.caption("算例对照（文稿 7.3 / 第五章 5.2.2）：10 辆电动车日需 200 kWh，全峰段 200 元/天；80% 移入谷段后 88 元/天，省 112 元、下降约 56%，"
               "外推典型站点全年节约约 4.09 万元。平台按真实班线里程折算，口径一致。")
    st.caption("换电模式详见第五章 5.2.1（对策一）。")
