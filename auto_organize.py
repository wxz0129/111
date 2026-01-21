import os
import shutil
import re
import pdfplumber
from datetime import datetime

# ================= ⚙️ 配置区域 (已修改为相对路径) =================

# 1. 获取当前脚本所在的文件夹路径 (锚点)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 2. 动态拼接源文件夹路径
# 逻辑：脚本所在目录 + Investment Research
SOURCE_FOLDER = os.path.join(BASE_DIR, 'Investment Research')

# 3. 动态拼接目标文件夹路径
# 逻辑：脚本所在目录 + Company_Research_Sorted (自动创建)
TARGET_ROOT = os.path.join(BASE_DIR, 'Company_Research_Sorted')

print(f"📍 当前工作基准路径: {BASE_DIR}")
print(f"📂 锁定源文件夹: {SOURCE_FOLDER}")
print(f"📂 设定目标文件夹: {TARGET_ROOT}")
print("-" * 50)

# 【防冲突配置】
DANGEROUS_KEYS = ["T", "U", "SE", "YY", "XD", "EA", "WB", "JD", "ZH", "APP"]

# 【核心字典】 (已包含所有公司)
COMPANY_MAP = {
    "700": "腾讯控股", "TENCENT": "腾讯控股",
    "TME": "腾讯音乐", "1698": "腾讯音乐",
    "772": "阅文集团", "00772": "阅文集团",
    "HUYA": "虎牙",
    "YY": "欢聚集团", "JOYY": "欢聚集团",
    "YALA": "Yalla",
    "MOMO": "挚文集团",
    "WB": "微博",
    "ZH": "知乎",
    "1024": "快手", "KUAISHOU": "快手", "01024": "快手",
    "BILI": "哔哩哔哩", "9626": "哔哩哔哩", "BILIBILI": "哔哩哔哩",
    "IQ": "爱奇艺",
    "1970": "IMAX China",
    "1896": "猫眼娱乐",
    "1060": "阿里影业",
    "300133": "华策影视",
    "9857": "柠萌影视",
    "NTES": "网易", "9999": "网易",
    "9899": "网易云音乐", "CLOUD MUSIC": "网易云音乐",
    "YOUDAO": "有道",
    "7974": "任天堂", "NINTENDO": "任天堂",
    "6758": "索尼", "SONY": "索尼",
    "TTWO": "Take-Two",
    "EA": "艺电", "ELECTRONIC ARTS": "艺电",
    "U": "Unity", "UNITY": "Unity",
    "RBLX": "Roblox",
    "2400": "心动公司", "XD": "心动公司",
    "3888": "金山软件",
    "799": "IGG",
    "9990": "祖龙娱乐",
    "6820": "友谊时光",
    "253450": "Studio Dragon",
    "6098": "Recruit",
    "8136": "三丽鸥",
    "SE": "Sea Ltd",
    "BABA": "阿里巴巴", "9988": "阿里巴巴",
    "JD": "京东", "9618": "京东",
    "PDD": "拼多多",
    "3690": "美团", "MEITUAN": "美团",
    "9888": "百度", "BIDU": "百度",
    "9992": "泡泡玛特", "POP MART": "泡泡玛特", "POPMART": "泡泡玛特",
    "SPOT": "Spotify",
    "NFLX": "Netflix",
    "TTD": "The Trade Desk",
    "APP": "AppLovin",
    "DIS": "迪士尼", "DISNEY": "迪士尼",
    "CMCSA": "康卡斯特",
    "OMC": "宏盟", "OMNICOM": "宏盟",
    "LYV": "Live Nation",
    "WMG": "华纳音乐",
    "WBD": "华纳兄弟探索", "GSWBD": "华纳兄弟探索",
    "PARA": "派拉蒙",
    "FOXA": "福克斯",
    "LGF": "狮门影业", "LGF.A": "狮门影业",
    "T": "AT&T", "AT&T": "AT&T",
    "LKNCY": "瑞幸咖啡",
    "BEKE": "贝壳"
}

# 【行业关键词】
# 如果找不到公司，但包含这些词，就归入 "行业报告" 文件夹
INDUSTRY_KEYWORDS = ["Tracker", "Strategy", "Outlook", "Sector", "Industry", "Quantitative", "Portfolio", "Macro", "Internet", "Media"]

# 【白名单】PDF内容必须包含这些才算个股报告 (用于兜底检查)
STOCK_FEATURES = ["Target Price", "Rating", "Buy", "Sell", "Hold", "Outperform", "Neutral", "EPS Estimate"]

# ================= 正则表达式 =================

REGEX_DATE = re.compile(r'_([A-Za-z]{3}_\d{1,2},_\d{4})\.(pdf|xlsx|xls)$', re.IGNORECASE)
REGEX_TICKER = re.compile(r'\((?!Buy|Sell|Hold|Neutral|Outperform)([A-Z0-9\s\.&]+)\)', re.IGNORECASE)

# ============================================

def safe_match(key, text):
    """防冲突匹配逻辑"""
    text_upper = text.upper()
    key_upper = key.upper()
    
    if key_upper not in text_upper:
        return False
    if key_upper in DANGEROUS_KEYS or key.isdigit():
        escaped_key = re.escape(key_upper)
        pattern = rf"(?:^|[^a-zA-Z0-9]){escaped_key}(?:$|[^a-zA-Z0-9])"
        if re.search(pattern, text_upper):
            return True
        else:
            return False
    return True

def identify_file_type(filename, filepath):
    """
    智能分类逻辑
    返回: (文件夹名, 分类类型)
    分类类型: "COMPANY" | "INDUSTRY" | None
    """
    filename_upper = filename.upper()
    ext = os.path.splitext(filename)[1].lower()

    # === 1. 优先：寻找具体公司 ===
    
    # A. Excel 专属匹配
    if ext in ['.xlsx', '.xls']:
        sorted_keys = sorted(COMPANY_MAP.keys(), key=len, reverse=True)
        for key in sorted_keys:
            pattern = rf"_{re.escape(key)}(?:Financial|Model|_)"
            if re.search(pattern, filename, re.IGNORECASE):
                return COMPANY_MAP[key], "COMPANY"

    # B. PDF Ticker 匹配
    ticker_match = REGEX_TICKER.search(filename)
    if ticker_match:
        raw_ticker = ticker_match.group(1).upper()
        clean_ticker = re.split(r'\s+', raw_ticker)[0]
        if clean_ticker.isdigit(): clean_ticker = str(int(clean_ticker))
        
        if clean_ticker in COMPANY_MAP: return COMPANY_MAP[clean_ticker], "COMPANY"
        if raw_ticker in COMPANY_MAP: return COMPANY_MAP[raw_ticker], "COMPANY"

    # C. 全名单词匹配
    for key, val in COMPANY_MAP.items():
        if safe_match(key, filename):
            return val, "COMPANY"

    # D. PDF 内容扫描 (兜底找公司)
    if ext == '.pdf':
        try:
            with pdfplumber.open(filepath) as pdf:
                if len(pdf.pages) > 0:
                    text = pdf.pages[0].extract_text()
                    if text:
                        has_feature = any(f in text for f in STOCK_FEATURES)
                        if has_feature:
                            for key, val in COMPANY_MAP.items():
                                if safe_match(key, text):
                                    if len(key) < 3 and "TICKER" not in text.upper(): continue
                                    return val, "COMPANY"
        except:
            pass

    # === 2. 其次：如果没找到公司，检查是否为 "行业报告" ===
    # 只要包含 Tracker/Strategy 等词，就归入行业报告
    if any(kw.upper() in filename_upper for kw in INDUSTRY_KEYWORDS):
        return "行业报告", "INDUSTRY"

    return None, None

def generate_new_filename(filename, folder_name, file_type):
    """
    生成标准化文件名
    如果是公司: Broker-Company-Title-Date
    如果是行业: Broker-Industry-Title-Date
    """
    file_root, ext = os.path.splitext(filename)
    
    # 日期
    date_match = REGEX_DATE.search(filename)
    if date_match:
        clean_date = date_match.group(1).replace('_', ' ').replace(',', '').strip()
        try:
            short_date = datetime.strptime(clean_date, '%b %d %Y').strftime('%y%m%d')
        except:
            short_date = "000000"
    else:
        short_date = "000000"
    
    # 券商
    broker = filename.split('_')[0]
    
    # 标题 (去除 Broker, 日期, 后缀)
    core = filename[len(broker)+1:]
    if date_match:
        core = core[: -len(date_match.group(0))] 
    else:
        core = core[: -len(ext)]

    # 智能清洗标题
    title = core
    
    # 1. 去除中间的 (Ticker)
    last_paren = title.rfind(')')
    if last_paren != -1:
        title = title[last_paren+1:]
        
    # 2. 如果是公司报告，尝试从标题中去除公司名前缀，避免重复 (如 Tencent-TencentUpdate)
    if file_type == "COMPANY":
        # 简单反向查找 Key 并去除
        pass 
        
    title = title.strip('_- ')
    
    # 3. 确定“中间名” (Company vs Industry)
    if file_type == "INDUSTRY":
        middle_name = "Industry" # 行业报告统一用 Industry
    else:
        middle_name = folder_name # 公司报告用中文公司名

    # 兜底标题
    if not title: 
        title = "Model" if ext in ['.xlsx', '.xls'] else "Update"
    if len(title) > 60: title = title[:60]
    
    # 组装
    new_name = f"{broker}-{middle_name}-{title}-{short_date}{ext}"
    return new_name.replace('/', '-')

def main():
    if not os.path.exists(SOURCE_FOLDER):
        print(f"❌ 错误: 找不到文件夹 '{SOURCE_FOLDER}'")
        print(f"👉 请确保本脚本文件与 'Investment Research' 文件夹在同一目录下。")
        return

    files = [f for f in os.listdir(SOURCE_FOLDER) if f.lower().endswith(('.pdf', '.xlsx', '.xls'))]
    print(f"🔍 扫描到 {len(files)} 份文件，开始处理...\n")

    count_company = 0
    count_industry = 0
    count_uncategorized = 0

    for i, filename in enumerate(files):
        filepath = os.path.join(SOURCE_FOLDER, filename)
        ext = os.path.splitext(filename)[1].lower()
        
        # 1. 识别
        folder_name, file_type = identify_file_type(filename, filepath)
        
        if folder_name and file_type:
            # 生成新文件名
            new_name = generate_new_filename(filename, folder_name, file_type)
            
            # 确定目标路径
            if file_type == "COMPANY":
                # 公司报告 -> 公司名/报告(或模型)
                sub = "模型" if ext in ['.xlsx', '.xls'] else "报告"
                target_dir = os.path.join(TARGET_ROOT, folder_name, sub)
                # 确保兄弟文件夹存在
                os.makedirs(os.path.join(TARGET_ROOT, folder_name, "报告" if sub == "模型" else "模型"), exist_ok=True)
                icon = "📊" if sub == "模型" else "📄"
                count_company += 1
                
            else: # file_type == "INDUSTRY"
                # 行业报告 -> 行业报告
                target_dir = os.path.join(TARGET_ROOT, "行业报告")
                icon = "🌎"
                count_industry += 1
            
            os.makedirs(target_dir, exist_ok=True)
            
            try:
                shutil.copy2(filepath, os.path.join(target_dir, new_name))
                print(f"[{i+1}] {icon} {folder_name} | {new_name[-30:]}")
            except Exception as e:
                print(f"❌ 复制失败: {filename} -> {e}")

        else:
            # 未分类
            uncategorized_dir = os.path.join(TARGET_ROOT, "_未分类文件")
            os.makedirs(uncategorized_dir, exist_ok=True)
            try:
                shutil.copy2(filepath, os.path.join(uncategorized_dir, filename))
                print(f"[{i+1}] 📂 未分类 | {filename[:40]}...")
                count_uncategorized += 1
            except:
                pass

    print(f"\n{'='*40}")
    print(f"🎉 处理完成")
    print(f"🏢 个股报告: {count_company} 份")
    print(f"🌎 行业报告: {count_industry} 份 (已重命名为 Industry)")
    print(f"📂 未分类:   {count_uncategorized} 份")
    print(f"{'='*40}")
    print(f"\n📂 结果位置: {TARGET_ROOT}")

if __name__ == "__main__":
    main()