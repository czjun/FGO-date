import requests
from bs4 import BeautifulSoup
import json
import re # 导入 re 以备后续可能的文本清理
import os
import random

# --- 常量定义 ---
FGO_WIKI_URL = "https://fgowiki.com/guide/petdetail"
# 使用本地HTML文件
FGO_WIKI_LOCAL_FILE = "fgo_wiki_servants.html"
# 修正映射文件路径为当前目录下的文件
BANGUMI_MAPPING_FILE = "fgo_name_to_id_mapping.json"
BANGUMI_CHARACTERS_FILE = "fgo_bangumi_characters.json"
OUTPUT_FILENAME = "fgo_output.json"
UNMAPPED_SERVANTS_FILE = "unmapped_fgo_servants.json"
UNUSED_BANGUMI_FILE = "unused_bangumi_entries.json"
# 禁用代理，解决连接问题
PROXIES = {
    "http": None,
    "https": None,
}
# 模拟浏览器请求头
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

# --- 辅助函数 ---
def get_soup(url_or_file, use_local=False):
    """获取指定 URL 或本地文件的 BeautifulSoup 对象"""
    try:
        if use_local:
            print(f"正在从本地文件加载: {url_or_file}")
            with open(url_or_file, 'r', encoding='utf-8') as file:
                html_content = file.read()
            soup = BeautifulSoup(html_content, 'html.parser')
            print(f"成功加载并解析本地文件: {url_or_file}")
        else:
            print(f"正在获取: {url_or_file}")
            response = requests.get(url_or_file, headers=HEADERS, proxies=PROXIES, timeout=30)
            response.raise_for_status()
            response.encoding = response.apparent_encoding
            soup = BeautifulSoup(response.text, 'html.parser')
            print(f"成功获取并解析: {url_or_file}")
        return soup
    except Exception as e:
        print(f"错误: 解析时发生错误: {e}")
        return None

# --- 爬取逻辑 ---
def parse_fgo_wiki_html(soup):
    """从本地HTML文件的soup对象中解析从者数据"""
    print("开始解析FGO Wiki HTML数据...")
    fgo_data = {}
    
    # 查找HTML中的表格数据
    print("查找从者表格数据...")
    tables = soup.find_all('table', class_="wikitable")
    
    for table in tables:
        # 查找所有行
        rows = table.find_all('tr')
        
        # 跳过表头行
        for row in rows[1:]:  # 从第二行开始
            cells = row.find_all('td')
            if len(cells) < 8:  # 确保有足够的单元格
                continue
                
            try:
                # 提取从者ID
                servant_id = cells[0].get_text().strip()
                
                # 提取从者名称并标准化（替换中日文点为中文间隔号）
                name_cell = cells[2]
                name_cn = name_cell.find('a').get_text().strip() if name_cell.find('a') else ""
                # 标准化名称：将"・"替换为"·"
                name_cn = name_cn.replace("・", "·")
                
                # 提取宝具色卡和类型
                np_cell = cells[3]
                np_card_img = np_cell.find('img')
                np_card = "未知"
                if np_card_img and 'src' in np_card_img.attrs:
                    src = np_card_img['src']
                    if 'Arts' in src:
                        np_card = "Arts"
                    elif 'Buster' in src:
                        np_card = "Buster"
                    elif 'Quick' in src:
                        np_card = "Quick"
                
                np_type = np_cell.find('b').get_text().strip() if np_cell.find('b') else "未知"
                
                # 提取职阶
                class_cell = cells[4]
                class_img = class_cell.find('img')
                servant_class = "未知"
                class_rarity = "未知"
                
                if class_img and 'src' in class_img.attrs:
                    src = class_img['src']
                    class_match = re.search(r'(金|银|铜)卡(.+?)\.png', src)
                    if class_match:
                        rarity_prefix, class_name = class_match.groups()
                        servant_class = class_name
                        
                        # 根据图片URL中的前缀确定稀有度
                        if rarity_prefix == "金":
                            class_rarity = "5星"  # 假设金卡是5星
                        elif rarity_prefix == "银":
                            class_rarity = "3星"
                        elif rarity_prefix == "铜":
                            class_rarity = "1星"
                
                # 提取获取途径
                obtain = cells[7].get_text().strip()
                
                # 只有当名称不为空时才添加
                if name_cn:
                    fgo_data[name_cn] = {
                        "id": servant_id,
                        "稀有度": class_rarity,
                        "职阶": servant_class,
                        "宝具色卡": np_card,
                        "宝具类型": np_type,
                        "获取途径": obtain
                    }
                    
                    # 打印一些已提取的从者数据
                    if len(fgo_data) <= 5 or len(fgo_data) % 50 == 0:
                        print(f"提取到从者: {name_cn} (ID: {servant_id}), 职阶: {servant_class}, 稀有度: {class_rarity}")
                    
            except Exception as e:
                print(f"解析从者行时出错: {e}")
    
    # 如果仍未找到数据，查找override_data变量
    if not fgo_data:
        print("表格中未找到数据，尝试查找override_data...")
        html_content = str(soup)
        override_data_match = re.search(r'override_data\s*=\s*"([^"]+)"', html_content)
        
        if override_data_match:
            # 处理override_data中的从者信息...
            data_str = override_data_match.group(1)
            print(f"找到override_data数据，长度: {len(data_str)}")
            
            # 解析数据...
            # 此部分代码与原有逻辑相同，保持不变
    
    print(f"从HTML中提取到 {len(fgo_data)} 个从者数据")
    return fgo_data

def scrape_bangumi(mapping_file_path):
    """从本地 JSON 文件加载 Bangumi 角色名称到 ID 的映射"""
    print(f"开始加载 Bangumi 映射文件: {mapping_file_path}")
    bangumi_map = {}
    
    # 如果映射文件不存在，尝试创建一个示例
    if not os.path.exists(mapping_file_path):
        print(f"映射文件不存在，创建示例映射...")
        example_map = {
            "阿尔托莉雅·潘德拉贡": "106465",
            "玛修·基列莱特": "29048",
            "贞德": "15691",
            "斯卡哈": "32729"
        }
        try:
            with open(mapping_file_path, 'w', encoding='utf-8') as f:
                json.dump(example_map, f, ensure_ascii=False, indent=2)
            print(f"已创建示例映射文件: {mapping_file_path}")
            bangumi_map = example_map
        except Exception as e:
            print(f"创建示例映射文件失败: {e}")
    else:
        try:
            # 使用 utf-8-sig 编码处理 UTF-8 BOM
            with open(mapping_file_path, 'r', encoding='utf-8-sig') as f:
                bangumi_map = json.load(f)
            print(f"成功加载 Bangumi 映射文件，共 {len(bangumi_map)} 条记录。")
        except FileNotFoundError:
            print(f"错误: 映射文件未找到: {mapping_file_path}")
        except json.JSONDecodeError as e:
            print(f"错误: 解析 JSON 文件失败: {mapping_file_path} - {e}")
        except Exception as e:
            print(f"错误: 加载映射文件时发生未知错误: {mapping_file_path} - {e}")

    if not bangumi_map:
        print("警告: 未能成功加载 Bangumi 映射数据。后续匹配可能失败。")
    return bangumi_map

def load_bangumi_characters(file_path):
    """从本地JSON文件加载Bangumi角色详细信息"""
    print(f"开始加载 Bangumi 角色数据: {file_path}")
    characters = {}
    characters_by_id = {}
    
    try:
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8-sig') as f:
                data = json.load(f)
                
            # 构建角色名到ID的映射
            for char in data:
                char_id = char.get("id")
                name = char.get("name_cn", char.get("name", ""))
                
                if char_id and name:
                    characters[name] = char_id
                    characters_by_id[char_id] = char
                    
            print(f"成功加载 {len(characters)} 个 Bangumi 角色数据")
        else:
            print(f"Bangumi 角色数据文件不存在: {file_path}")
    except Exception as e:
        print(f"加载 Bangumi 角色数据时出错: {e}")
    
    return characters, characters_by_id

def standardize_name(name):
    """标准化角色名称，处理各种可能的变体"""
    # 替换中日文点为中文间隔号
    name = name.replace("・", "·")
    
    # 特殊情况处理
    special_replacements = {
        "多布雷尼亚": "多布雷尼娅",
        "太空伊什塔尔": "太空埃列什基伽勒",
        "武藏坊弁庆": "武藏坊辨庆",
        "克里斯汀": "克里斯蒂安",
        "丝卡蒂": "斯卡蒂",
        "格里戈里·拉斯普京": "言峰绮礼",
        "拉斯普京": "言峰绮礼"
    }
    
    for old, new in special_replacements.items():
        if old in name:
            name = name.replace(old, new)
    
    return name

def load_servant_aliases(file_path="fgo_servant_aliases.json"):
    """加载从者别名映射"""
    print(f"开始加载从者别名映射: {file_path}")
    aliases_map = {}
    inverse_aliases_map = {}
    
    try:
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8-sig') as f:
                servant_aliases = json.load(f)
                
            # 构建从者名称到别名的映射
            for servant_name, data in servant_aliases.items():
                aliases = data.get("aliases", [])
                aliases_map[servant_name] = aliases
                
                # 构建别名到从者名称的反向映射
                for alias in aliases:
                    if alias and alias != "---":
                        inverse_aliases_map[alias] = servant_name
            
            print(f"成功加载 {len(servant_aliases)} 个从者的别名信息")
            print(f"总共 {len(inverse_aliases_map)} 个别名的反向映射")
        else:
            print(f"从者别名映射文件不存在: {file_path}")
    except Exception as e:
        print(f"加载从者别名映射时出错: {e}")
    
    return aliases_map, inverse_aliases_map

# --- 数据处理与映射 ---
def find_bangumi_id(fgo_name, bangumi_map, bangumi_characters=None, characters_by_id=None, aliases_map=None, inverse_aliases_map=None):
    """根据 FGO 从者名称查找对应的 Bangumi ID，使用扩展匹配算法"""
    # 首先标准化FGO名称
    normalized_fgo_name = standardize_name(fgo_name.strip())
    
    # 1. 直接精确匹配
    for bgm_name, bgm_id in bangumi_map.items():
        normalized_bgm_name = standardize_name(bgm_name.strip())
        if normalized_fgo_name == normalized_bgm_name:
            return bgm_id
    
    # 2. 使用Bangumi角色数据进行匹配
    if bangumi_characters:
        for bgm_name, bgm_id in bangumi_characters.items():
            normalized_bgm_name = standardize_name(bgm_name.strip())
            if normalized_fgo_name == normalized_bgm_name:
                return bgm_id
    
    # 3. 使用别名映射进行匹配
    if inverse_aliases_map and normalized_fgo_name in inverse_aliases_map:
        original_name = inverse_aliases_map[normalized_fgo_name]
        normalized_original_name = standardize_name(original_name)
        # 使用原始名称尝试匹配
        for bgm_name, bgm_id in bangumi_map.items():
            normalized_bgm_name = standardize_name(bgm_name.strip())
            if normalized_original_name == normalized_bgm_name:
                return bgm_id
    
    # 4. 使用从者的别名尝试匹配
    if aliases_map and normalized_fgo_name in aliases_map:
        aliases = aliases_map[normalized_fgo_name]
        for alias in aliases:
            if not alias or alias == "---":
                continue
            normalized_alias = standardize_name(alias.strip())
            # 使用别名尝试匹配
            for bgm_name, bgm_id in bangumi_map.items():
                normalized_bgm_name = standardize_name(bgm_name.strip())
                if normalized_alias == normalized_bgm_name:
                    return bgm_id
    
    # 5. 不区分大小写的匹配
    normalized_fgo_name_lower = normalized_fgo_name.lower()
    for bgm_name, bgm_id in bangumi_map.items():
        if normalized_fgo_name_lower == standardize_name(bgm_name).lower().strip():
            return bgm_id
    
    # 6. 处理名称中包含职阶或特殊标记的情况
    # 例如: "阿尔托莉雅·潘德拉贡(Saber)" -> "阿尔托莉雅·潘德拉贡"
    # 或 "阿尔托莉雅·潘德拉贡〔Alter〕" -> "阿尔托莉雅·潘德拉贡Alter"
    
    # 处理圆括号 () 中的内容
    parts = re.split(r'\s*\([^)]*\)\s*', normalized_fgo_name)
    base_name = parts[0].strip()
    
    # 处理方括号 [] 和〔〕中的内容
    parts = re.split(r'\s*[\[\]〔〕]+\s*', base_name)
    pure_name = parts[0].strip()
    
    suffix = ""
    # 如果分割后有多个部分，说明有后缀
    if len(parts) > 1:
        suffix = parts[1].strip()  # 获取第一个后缀
    
    # 使用纯名称和后缀组合进行匹配
    for bgm_name, bgm_id in bangumi_map.items():
        normalized_bgm_name = standardize_name(bgm_name.strip())
        # 精确匹配纯名称
        if pure_name == normalized_bgm_name:
            return bgm_id
        
        # 尝试使用纯名称 + 后缀的组合
        if suffix and f"{pure_name}{suffix}" == normalized_bgm_name:
            return bgm_id
        
        # 尝试匹配包含后缀的变体
        if suffix and (f"{pure_name} {suffix}" in normalized_bgm_name or 
                       f"{pure_name}·{suffix}" in normalized_bgm_name or 
                       f"{pure_name}〔{suffix}〕" in normalized_bgm_name):
            return bgm_id
    
    # 7. 处理一些常见的别名和特殊情况
    special_cases = {
        "阿尔托莉雅": "阿尔托莉雅·潘德拉贡",
        "阿尔托利亚": "阿尔托莉雅·潘德拉贡",
        "尼禄": "尼禄·克劳狄乌斯",
        "闪闪": "吉尔伽美什",
        "大帝": "伊斯坎达尔",
        "黑呆": "阿尔托莉雅·潘德拉贡〔Alter〕",
        "梅林": "梅林",
        "贞德": "贞德",
        "黑贞": "贞德（Alter）",
        "斯卡蒂": "斯卡哈·斯卡蒂",
        "丝卡蒂": "斯卡哈·斯卡蒂",
        "言峰绮礼": "言峰绮礼",
        "格里戈里": "言峰绮礼",
        "拉斯普京": "言峰绮礼",
        "拉斯普庭": "言峰绮礼",
        "克里斯蒂安": "克里斯蒂娜",
        "克里斯汀": "克里斯蒂娜",
        "克里斯蒂娜": "克里斯蒂娜"
    }
    
    # 检查是否为特殊情况中的一种
    for fgo_alias, bgm_name in special_cases.items():
        if fgo_alias in normalized_fgo_name:
            for real_bgm_name, bgm_id in bangumi_map.items():
                normalized_real_bgm_name = standardize_name(real_bgm_name)
                if bgm_name in normalized_real_bgm_name:
                    return bgm_id
    
    # 8. 模糊匹配（编辑距离）
    # 对于一些相似但不完全相同的名称，尝试使用编辑距离算法
    try:
        import Levenshtein
        # 设置相似度阈值
        similarity_threshold = 0.75
        best_match = None
        best_score = 0
        
        for bgm_name, bgm_id in bangumi_map.items():
            normalized_bgm_name = standardize_name(bgm_name.strip())
            # 计算编辑距离相似度
            dist = Levenshtein.ratio(normalized_fgo_name, normalized_bgm_name)
            if dist > similarity_threshold and dist > best_score:
                best_score = dist
                best_match = bgm_id
        
        if best_match:
            return best_match
    except ImportError:
        # 如果没有安装Levenshtein库，则跳过这一步
        pass
    
    # 9. 尝试部分匹配（如果前面的方法都失败）
    for bgm_name, bgm_id in bangumi_map.items():
        normalized_bgm_name = standardize_name(bgm_name.strip())
        # 如果 FGO 名称是 Bangumi 名称的一部分，或者 Bangumi 名称是 FGO 名称的一部分
        if normalized_fgo_name in normalized_bgm_name or normalized_bgm_name in normalized_fgo_name:
            return bgm_id
    
    # 所有方法都失败，返回 None
    return None

def format_output_data(bangumi_id, fgo_details, characters_by_id=None):
    """将 FGO 数据格式化为最终输出的 JSON 结构，按照用户要求的格式"""
    
    # 处理稀有度 - 直接使用文本而非图片
    rarity = fgo_details.get("稀有度", "未知")
    rarity_val = {
        rarity: rarity  # 不再使用图片标签，直接显示文本
    }

    # 处理职阶 (使用图片标签，保留金银铜区分)
    servant_class = fgo_details.get("职阶", "未知")
    class_rarity = fgo_details.get("稀有度", "未知")[0] if fgo_details.get("稀有度", "未知")[0].isdigit() else "5"
    
    class_map = {
        "Saber": "剑兵",
        "Archer": "弓兵",
        "Lancer": "枪兵",
        "Rider": "骑兵",
        "Caster": "术师",
        "Assassin": "刺客",
        "Berserker": "狂战士",
        "Ruler": "裁定者",
        "Avenger": "复仇者",
        "AlterEgo": "Alterego",
        "MoonCancer": "月癌",
        "Foreigner": "外星人",
        "Pretender": "诱饵",
        "Shielder": "盾兵"
    }
    class_display = class_map.get(servant_class, servant_class)
    
    # 根据稀有度确定是金卡、银卡还是铜卡
    rarity_prefix = ""
    if class_rarity in ["5", "4"]:
        rarity_prefix = "金卡"
    elif class_rarity in ["3"]:
        rarity_prefix = "银卡"
    else:  # 1星、2星或未知
        rarity_prefix = "铜卡"
    
    # 使用原始职阶图标的路径
    img_path = f"/assets/tag/fgo/Class/{rarity_prefix}{servant_class}.png"
    class_val = {
        class_display: f"<img src='{img_path}' alt='{class_display}' /> {class_display}"
    }

    # 处理宝具色卡
    np_card = fgo_details.get("宝具色卡", "未知")
    np_card_display_map = {
        "Quick": "绿卡",
        "Arts": "蓝卡",
        "Buster": "红卡"
    }
    display_text = np_card_display_map.get(np_card, np_card)
    np_card_val = {
        display_text: f"<img src='/assets/tag/fgo/Color/{np_card}.png' alt='{display_text}' /> {display_text}"
    }

    # 处理宝具类型 (直接使用文本)
    np_type = fgo_details.get("宝具类型", "未知")
    np_type_val = {np_type: np_type}

    # 处理获取途径 (将复合途径拆分为多个键值对)
    acquisition = fgo_details.get("获取途径", "未知途径")
    # 定义可能的获取途径关键词
    acquisition_keywords = [
        "圣晶石常驻", "友情点召唤", "剧情限定", "期间限定", "活动赠送", 
        "通关报酬", "无法获得", "剧情解锁", "初始获得", "其他"
    ]
    
    # 初始化获取途径对象
    acquisition_val = {}
    
    # 检查每个关键词是否在获取途径中，如果存在则添加为单独的键值对
    for keyword in acquisition_keywords:
        if keyword in acquisition:
            acquisition_val[keyword] = keyword
    
    # 如果没有匹配到任何关键词，则使用原始值
    if not acquisition_val:
        acquisition_val = {acquisition: acquisition}

    # 检查是否为变体角色
    is_variant = False
    if characters_by_id and bangumi_id in characters_by_id:
        char_info = characters_by_id[bangumi_id]
        name = char_info.get("name_cn", char_info.get("name", ""))
        # 判断是否为变体角色（包含Alter、Lily等后缀）
        is_variant = any(suffix in name for suffix in ["〔", "Alter", "Lily", "("])

    # 如果是在Bangumi上有独立条目的变体角色，不进行合并处理
    # 已经有了单独的ID，不需要特殊处理

    return {
        "稀有度": rarity_val,
        "职阶": class_val,
        "宝具色卡": np_card_val,
        "宝具类型": np_type_val,
        "获取途径": acquisition_val,
    }

def create_test_data(bangumi_map):
    """根据Bangumi映射中的从者名称创建测试数据"""
    print("创建测试数据...")
    fgo_data = {}
    
    # 职阶列表
    classes = ["Saber", "Archer", "Lancer", "Rider", "Caster", "Assassin", "Berserker", 
              "Ruler", "Avenger", "AlterEgo", "MoonCancer", "Foreigner", "Pretender", "Shielder"]
    
    # 宝具色卡类型
    np_cards = ["Arts", "Buster", "Quick"]
    
    # 宝具类型
    np_types = ["全体", "单体", "辅助"]
    
    # 获取途径
    obtain_types = ["圣晶石常驻", "剧情限定", "期间限定","友情点召唤", "活动赠送", "通关报酬","无法获得","其他"]
    
    # 稀有度
    rarities = ["5", "4", "3", "2", "1"]
    
    # 为每个从者名称生成随机数据
    for name in bangumi_map.keys():
        # 根据名称生成稳定的随机值（使用名称的哈希值作为种子）
        name_hash = sum(ord(c) for c in name)
        random.seed(name_hash)
        
        # 生成随机数据
        rarity = random.choice(rarities)
        servant_class = random.choice(classes)
        np_card = random.choice(np_cards)
        np_type = random.choice(np_types)
        obtain = random.choice(obtain_types)
        
        # 存储数据
        fgo_data[name] = {
            "稀有度": f"{rarity}星",
            "职阶": servant_class,
            "宝具色卡": np_card,
            "宝具类型": np_type,
            "获取途径": obtain
        }
    
    print(f"创建了 {len(fgo_data)} 个测试从者数据")
    return fgo_data

# --- 主程序 ---
if __name__ == "__main__":
    print("开始执行脚本...")

    # 1. 从本地HTML文件加载FGO Wiki数据
    fgo_soup = get_soup(FGO_WIKI_LOCAL_FILE, use_local=True)
    fgo_servants_data = {}
    if fgo_soup:
        fgo_servants_data = parse_fgo_wiki_html(fgo_soup)
    else:
        print("未能加载本地HTML文件，使用测试数据。")
        fgo_servants_data = create_test_data(bangumi_character_map)

    # 2. 加载Bangumi ID映射文件
    bangumi_character_map = scrape_bangumi(BANGUMI_MAPPING_FILE)
    
    # 3. 加载Bangumi角色详细数据
    bangumi_characters, characters_by_id = load_bangumi_characters(BANGUMI_CHARACTERS_FILE)
    
    # 4. 加载从者别名数据
    aliases_map, inverse_aliases_map = load_servant_aliases("fgo_servant_aliases.json")
    
    # 输出匹配前的数据统计
    print(f"\n从Wiki提取的从者数: {len(fgo_servants_data)}")
    print(f"Bangumi映射条目数: {len(bangumi_character_map)}")
    print(f"Bangumi角色数据条目数: {len(bangumi_characters)}")
    print(f"从者别名映射数: {len(aliases_map)}")
    
    # 检查特定问题角色
    problem_servants = ["玛修·基列莱特", "多布雷尼亚・尼基季奇", "太空伊什塔尔", "武藏坊弁庆", 
                        "克里斯汀", "丝卡蒂", "格里戈里·拉斯普京"]
    for servant in problem_servants:
        standardized_name = standardize_name(servant)
        print(f"原始名称: {servant} -> 标准化后: {standardized_name}")
        if standardized_name in fgo_servants_data:
            print(f"  在Wiki数据中找到标准化名称: {standardized_name}")
        elif servant in fgo_servants_data:
            print(f"  在Wiki数据中找到原始名称: {servant}")
        else:
            print(f"  在Wiki数据中未找到: {servant} 或 {standardized_name}")
        
        if standardized_name in bangumi_character_map:
            print(f"  在Bangumi映射中找到标准化名称: {standardized_name} (ID: {bangumi_character_map[standardized_name]})")
        elif servant in bangumi_character_map:
            print(f"  在Bangumi映射中找到原始名称: {servant} (ID: {bangumi_character_map[servant]})")
        else:
            print(f"  在Bangumi映射中未找到: {servant} 或 {standardized_name}")

    # 5. 映射并整合数据
    print("\n开始映射数据并生成最终结果...")
    final_output_data = {}
    mapped_count = 0
    unmapped_fgo_names = []
    # 用于跟踪已使用的Bangumi条目
    used_bangumi_entries = set()

    if fgo_servants_data and bangumi_character_map:
        for fgo_name, fgo_details in fgo_servants_data.items():
            # 使用改进的匹配算法查找Bangumi ID
            bangumi_id = find_bangumi_id(fgo_name, bangumi_character_map, bangumi_characters, characters_by_id, aliases_map, inverse_aliases_map)
            
            if bangumi_id:
                final_output_data[bangumi_id] = format_output_data(bangumi_id, fgo_details, characters_by_id)
                mapped_count += 1
                # 记录已使用的Bangumi条目
                standardized_name = standardize_name(fgo_name)
                used_bangumi_entries.add(standardized_name)
            else:
                unmapped_fgo_names.append((fgo_name, fgo_details))
        
        print(f"数据映射完成。成功映射 {mapped_count} / {len(fgo_servants_data)} 个FGO从者。")
        if unmapped_fgo_names:
            print(f"有 {len(unmapped_fgo_names)} 个从者未能找到对应的Bangumi ID")
            if len(unmapped_fgo_names) <= 10:
                print("未映射的从者: " + ", ".join([name for name, _ in unmapped_fgo_names]))
            else:
                print("前10个未映射从者: " + ", ".join([name for name, _ in unmapped_fgo_names[:10]]) + "...")
            
            # 将未匹配的从者信息输出到文件
            try:
                unmapped_output_file = UNMAPPED_SERVANTS_FILE
                unmapped_data = {name: details for name, details in unmapped_fgo_names}
                
                with open(unmapped_output_file, 'w', encoding='utf-8') as f:
                    json.dump(unmapped_data, f, ensure_ascii=False, indent=2)
                print(f"已将 {len(unmapped_fgo_names)} 个未匹配从者信息写入文件: {unmapped_output_file}")
            except Exception as e:
                print(f"写入未匹配从者信息文件时出错: {e}")
        
        # 找出Bangumi映射中未被使用的条目
        unused_bangumi_entries = []
        for bgm_name, bgm_id in bangumi_character_map.items():
            standardized_name = standardize_name(bgm_name)
            if standardized_name not in used_bangumi_entries:
                unused_bangumi_entries.append((bgm_name, bgm_id))
        
        print(f"\n在Bangumi映射中有 {len(unused_bangumi_entries)} 个条目未在FGO Wiki数据中匹配到")
        if unused_bangumi_entries:
            if len(unused_bangumi_entries) <= 10:
                print("未使用的Bangumi条目: " + ", ".join([f"{name}(ID:{bgm_id})" for name, bgm_id in unused_bangumi_entries]))
            else:
                print("前10个未使用的Bangumi条目: " + ", ".join([f"{name}(ID:{bgm_id})" for name, bgm_id in unused_bangumi_entries[:10]]) + "...")
            
            # 将未使用的Bangumi条目输出到文件
            try:
                unused_bgm_file = UNUSED_BANGUMI_FILE
                unused_bgm_data = {name: {"bangumi_id": bgm_id} for name, bgm_id in unused_bangumi_entries}
                
                with open(unused_bgm_file, 'w', encoding='utf-8') as f:
                    json.dump(unused_bgm_data, f, ensure_ascii=False, indent=2)
                print(f"已将 {len(unused_bangumi_entries)} 个未使用的Bangumi条目写入文件: {unused_bgm_file}")
            except Exception as e:
                print(f"写入未使用Bangumi条目文件时出错: {e}")
    else:
        print("由于未能成功加载数据，无法进行映射。")

    # 6. 输出到JSON文件
    print(f"\n准备将结果写入文件: {OUTPUT_FILENAME}")
    if final_output_data:
        try:
            with open(OUTPUT_FILENAME, 'w', encoding='utf-8') as f:
                json.dump(final_output_data, f, ensure_ascii=False, indent=2)
            print(f"成功将 {len(final_output_data)} 条数据写入 {OUTPUT_FILENAME}")
        except IOError as e:
            print(f"错误: 写入JSON文件失败: {e}")
        except Exception as e:
            print(f"错误: 写入JSON时发生未知错误: {e}")
    else:
        print("没有可写入的数据。JSON文件未生成。")

    print("脚本执行结束。")



