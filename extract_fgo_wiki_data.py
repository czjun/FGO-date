#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import json
import re
import logging
from bs4 import BeautifulSoup
import requests
import time
from collections import defaultdict

# --- 配置日志 ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("fgo_wiki_data_extraction.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# --- 常量定义 ---
FGO_WIKI_LOCAL_FILE = "fgo_wiki_servants.html"
FGO_WIKI_URL = "https://fgo.wiki/w/从者图鉴"  # 在线获取时的备用URL
OUTPUT_FILENAME = "fgo_wiki_servants_data.json"

# --- 工具函数 ---
def load_html_file(file_path):
    """从本地文件加载HTML内容"""
    try:
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                if not content or len(content) < 100:  # 检查文件内容是否为空或太小
                    logger.warning(f"本地HTML文件内容过少: {file_path}")
                    return None
                return content
        else:
            logger.warning(f"本地HTML文件不存在: {file_path}")
            return None
    except Exception as e:
        logger.error(f"加载本地HTML文件时出错: {e}")
        return None

def download_html(url):
    """从URL下载HTML内容"""
    try:
        logger.info(f"正在从 {url} 下载数据...")
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        content = response.text
        
        # 保存到本地文件作为缓存
        with open(FGO_WIKI_LOCAL_FILE, 'w', encoding='utf-8') as f:
            f.write(content)
            
        logger.info(f"成功下载数据并保存到本地文件: {FGO_WIKI_LOCAL_FILE}")
        return content
    except Exception as e:
        logger.error(f"下载HTML内容时出错: {e}")
        return None

def get_soup(file_path, use_local=True, fallback_url=None):
    """获取BeautifulSoup对象，优先使用本地文件，失败则尝试在线获取"""
    html_content = None
    
    if use_local:
        logger.info(f"正在从本地文件加载: {file_path}")
        html_content = load_html_file(file_path)
    
    # 如果本地文件加载失败且提供了fallback_url，尝试在线获取
    if not html_content and fallback_url:
        logger.info(f"本地文件加载失败，尝试从 {fallback_url} 在线获取")
        html_content = download_html(fallback_url)
    
    if html_content:
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            # 简单验证soup内容是否有效
            if not soup.find_all('table'):
                logger.warning("解析的HTML内容没有找到表格元素，可能不是有效的FGO Wiki页面")
                return None
            return soup
        except Exception as e:
            logger.error(f"解析HTML内容时出错: {e}")
            return None
    else:
        logger.error("无法获取HTML内容")
        return None

def safe_get_text(element, default="未知"):
    """安全获取元素的文本内容"""
    if element:
        return element.get_text(strip=True) or default
    return default

def split_name_and_aliases(name_text):
    """分离中日英名称和别名
    例如: "图坦卡蒙ツタンカーメンTutankhamun" => ("图坦卡蒙", ["ツタンカーメン", "Tutankhamun"])
    """
    if not name_text:
        return "未知", []
    
    # 匹配模式：中文部分 + 日文部分 + 英文部分
    # 中文字符范围
    chinese_pattern = r'[\u4e00-\u9fa5\·\（\）\〔\〕]+'
    # 日文字符范围（包含平假名、片假名和部分汉字）
    japanese_pattern = r'[\u3040-\u309f\u30a0-\u30ff\u3400-\u4dbf\u4e00-\u9fff\·\（\）\〔\〕]+'
    # 英文和数字
    english_pattern = r'[a-zA-Z0-9\s\.\-\(\)\[\]&\']+'
    
    # 尝试匹配"中文日文英文"的模式
    match = re.match(f'^({chinese_pattern})({japanese_pattern})({english_pattern})$', name_text)
    if match:
        main_name = match.group(1)
        jp_name = match.group(2)
        en_name = match.group(3)
        return main_name, [jp_name, en_name]
    
    # 尝试匹配"中文日文"的模式
    match = re.match(f'^({chinese_pattern})({japanese_pattern})$', name_text)
    if match:
        main_name = match.group(1)
        jp_name = match.group(2)
        return main_name, [jp_name]
    
    # 尝试匹配"中文英文"的模式
    match = re.match(f'^({chinese_pattern})({english_pattern})$', name_text)
    if match:
        main_name = match.group(1)
        en_name = match.group(2)
        return main_name, [en_name]
    
    # 尝试匹配"日文英文"的模式
    match = re.match(f'^({japanese_pattern})({english_pattern})$', name_text)
    if match:
        jp_name = match.group(1)
        en_name = match.group(2)
        return jp_name, [en_name]  # 使用日文作为主名称
    
    # 如果无法匹配以上模式，默认整个字符串为主名称
    return name_text, []

def extract_aliases(name_cell):
    """从名称单元格中提取别名信息"""
    if not name_cell:
        return []
        
    aliases = []
    try:
        text = name_cell.get_text(strip=True)
        
        # 匹配括号内的内容
        bracket_matches = re.findall(r'[（\(]([^）\)]+)[）\)]', text)
        aliases.extend(bracket_matches)
        
        # 匹配〔〕内的内容
        special_bracket_matches = re.findall(r'〔([^〕]+)〕', text)
        aliases.extend(special_bracket_matches)
        
        # 匹配别称（通常以"/"分隔）
        if '/' in text:
            parts = text.split('/')
            other_names = [part.strip() for part in parts[1:]]
            aliases.extend(other_names)
        
        # 获取<ruby>标签内的内容
        ruby_tags = name_cell.find_all('ruby')
        for tag in ruby_tags:
            rt_tag = tag.find('rt')
            if rt_tag:
                rt_text = rt_tag.get_text(strip=True)
                if rt_text:
                    aliases.append(rt_text)
        
        # 对于符号〔Alter〕，添加Alter作为别名
        if 'Alter' in text:
            base_name = re.sub(r'〔Alter〕', '', text).strip()
            aliases.append(f"{base_name}Alter")
        
    except Exception as e:
        logger.error(f"提取别名时出错: {e}")
    
    # 移除重复并过滤空字符串
    return [alias for alias in aliases if alias]

def get_card_type(card_cell):
    """从单元格获取宝具卡色"""
    try:
        if not card_cell:
            return "未知"
            
        card_img = card_cell.find('img')
        if card_img and 'alt' in card_img.attrs:
            card_alt = card_img['alt']
            if "Buster" in card_alt:
                return "Buster"
            elif "Arts" in card_alt:
                return "Arts"
            elif "Quick" in card_alt:
                return "Quick"
        elif card_img and 'src' in card_img.attrs:
            src = card_img['src'].lower()
            if "buster" in src:
                return "Buster"
            elif "arts" in src:
                return "Arts" 
            elif "quick" in src:
                return "Quick"
        
        # 尝试从文本中判断
        text = card_cell.get_text(strip=True).lower()
        if "buster" in text:
            return "Buster"
        elif "arts" in text:
            return "Arts"
        elif "quick" in text:
            return "Quick"
    except Exception as e:
        logger.error(f"获取宝具卡色时出错: {e}")
        
    return "未知"

def extract_name_other_from_html(html_content):
    """从HTML原始数据中提取name_other字段（别名）"""
    name_other_data = {}
    try:
        # 使用正则表达式匹配name_other字段
        pattern = r'name_cn=(.+?)\nname_jp=.+?\nname_en=.+?\nname_link=.+?\nname_other=(.+?)\nmethod='
        matches = re.findall(pattern, html_content)
        
        for name_cn, name_other in matches:
            if name_other and name_other.strip():
                # 分割别名（以&符号分隔）
                aliases = [alias.strip() for alias in name_other.split('&') if alias.strip()]
                if aliases:
                    name_other_data[name_cn.strip()] = aliases
                    logger.debug(f"提取到从者 {name_cn.strip()} 的原始别名: {aliases}")
    except Exception as e:
        logger.error(f"从HTML提取name_other字段时出错: {e}")
    
    return name_other_data

def parse_servant_row(columns, name_other_data):
    """解析从者表格行，返回从者数据"""
    if len(columns) < 3:  # 至少需要ID、名称和稀有度
        return None, None
    
    try:
        # 提取ID
        servant_id = safe_get_text(columns[0])
        # 尝试清理ID文本以获取纯数字
        servant_id = re.sub(r'[^\d]', '', servant_id)
        if not servant_id.isdigit():
            logger.debug(f"跳过无效ID的行: {safe_get_text(columns[0])}")
            return None, None
        
        # 提取稀有度（第三列）- 修复这里的错误
        rarity = safe_get_text(columns[2]) if len(columns) > 2 else "未知"
        # 检查稀有度是否是数字（1-5星）
        if not re.match(r'^[1-5]$', rarity):
            # 如果不是数字，可能是名称和稀有度列被错误识别
            # 尝试从第二列获取名称和稀有度
            name_rarity_text = safe_get_text(columns[1])
            # 尝试分离名称和别名
            servant_name, name_aliases = split_name_and_aliases(name_rarity_text)
            # 使用第三列作为职阶
            servant_class = rarity
        else:
            # 提取从者名称和别名（从第二列）
            name_cell = columns[1]
            full_name = safe_get_text(name_cell)
            
            # 清理名称中的特殊符号
            servant_name = re.sub(r'[（\(].*?[）\)]', '', full_name)
            servant_name = re.sub(r'〔.*?〕', '', servant_name)
            
            # 处理可能包含"/"的名称，取第一部分
            if '/' in servant_name:
                servant_name = servant_name.split('/')[0].strip()
            
            # 提取别名
            name_aliases = extract_aliases(name_cell)
            
            # 提取职阶（第四列）
            servant_class = safe_get_text(columns[3]) if len(columns) > 3 else "未知"
        
        if not servant_name:
            logger.debug(f"跳过无效名称的行: {safe_get_text(columns[1])}")
            return None, None
            
        # 获取图片URL（如果有）
        img_url = ""
        name_cell = columns[1]
        img_tag = name_cell.find('img')
        if img_tag and 'src' in img_tag.attrs:
            img_url = img_tag['src']
        
        # 提取宝具色卡
        np_card = "未知"
        if len(columns) > 4:
            np_card = get_card_type(columns[4])
        
        # 提取宝具类型
        np_type = safe_get_text(columns[5]) if len(columns) > 5 else "未知"
        
        # 提取获取途径
        acquisition = safe_get_text(columns[7]) if len(columns) > 7 else "未知"
        
        # 从原始HTML中获取额外别名
        if servant_name in name_other_data:
            for alias in name_other_data[servant_name]:
                if alias not in name_aliases:
                    name_aliases.append(alias)
                    logger.debug(f"为从者 {servant_name} 添加了原始HTML中的别名: {alias}")
        
        # 存储从者数据
        servant_data = {
            "id": servant_id,
            "稀有度": rarity if re.match(r'^[1-5]$', rarity) else "未知",
            "职阶": servant_class,
            "宝具色卡": np_card,
            "宝具类型": np_type,
            "获取途径": acquisition,
            "别名": name_aliases,
            "图片URL": img_url
        }
        
        return servant_name, servant_data
        
    except Exception as e:
        logger.error(f"解析从者行时出错: {e}")
        return None, None

def parse_fgo_wiki_html(soup):
    """解析FGO Wiki HTML获取从者详细信息"""
    logger.info("开始解析FGO Wiki HTML数据...")
    
    servants_data = {}
    
    if not soup:
        logger.error("无法解析空的BeautifulSoup对象")
        return servants_data
        
    try:
        # 查找所有从者表格
        logger.info("查找从者表格数据...")
        servant_tables = soup.find_all('table', class_='wikitable')
        
        if not servant_tables:
            logger.warning("未找到任何从者表格数据")
            
            # 尝试查找不同的表格类型
            servant_tables = soup.find_all('table')
            logger.info(f"尝试查找任何表格，找到 {len(servant_tables)} 个表格")
            
        # 先从HTML中提取name_other字段的数据
        logger.info("从HTML原始数据中提取name_other字段（别名）...")
        name_other_data = extract_name_other_from_html(str(soup))
        
        for table_idx, table in enumerate(servant_tables):
            logger.info(f"处理第 {table_idx+1}/{len(servant_tables)} 个表格")
            
            # 获取表格的所有行
            rows = table.find_all('tr')
            if len(rows) <= 1:  # 空表格或只有表头
                continue
                
            # 跳过表头行
            rows = rows[1:]  # 从第二行开始
            
            for row_idx, row in enumerate(rows):
                columns = row.find_all(['td', 'th'])
                servant_name, servant_data = parse_servant_row(columns, name_other_data)
                
                if servant_name and servant_data:
                    servants_data[servant_name] = servant_data
                    logger.info(f"提取到从者: {servant_name} (ID: {servant_data['id']}), "
                                f"职阶: {servant_data['职阶']}, 稀有度: {servant_data['稀有度']}, "
                                f"别名数量: {len(servant_data['别名'])}")
        
        logger.info(f"从HTML中提取到 {len(servants_data)} 个从者数据")
        
        if len(servants_data) == 0:
            logger.warning("未能提取到任何从者数据，这可能是由于HTML结构变化导致的")
            
    except Exception as e:
        logger.error(f"解析FGO Wiki HTML时发生错误: {e}")
    
    return servants_data

def add_special_aliases(servants_data):
    """为从者添加特殊别名"""
    logger.info("正在为从者添加特殊别名...")
    
    # 对每个从者添加更多别名
    for servant_name, data in servants_data.items():
        # 为从者名称添加更多可能的别名变体
        additional_aliases = []
        
        # 替换常见别称变体
        name_variants = [
            (r'·', ' '),  # 中间点替换为空格
            (r'・', ' '),  # 日文中间点替换为空格
            (r' ', ''),   # 移除空格
        ]
        
        for pattern, replacement in name_variants:
            variant = re.sub(pattern, replacement, servant_name)
            if variant != servant_name and variant not in data["别名"]:
                additional_aliases.append(variant)
        
        # 处理带有量词或称号的名称
        name_parts = re.split(r'[的之]', servant_name)
        if len(name_parts) > 1:
            for part in name_parts:
                if len(part) > 1 and part not in data["别名"]:
                    additional_aliases.append(part)
        
        # 添加额外别名
        data["别名"].extend(additional_aliases)
        
        # 处理特定从者的特殊别名
        special_aliases = {
            "阿尔托莉雅·潘德拉贡": ["阿尔托莉雅", "呆毛王", "棉被", "蓝傻", "圣剑"],
            "尼禄·克劳狄乌斯": ["尼禄", "红傻", "umu"],
            "斯卡哈": ["师匠"],
            "贞德": ["村姑"],
            "伊丽莎白·巴托里": ["伊丽莎白", "龙娘"],
            "冲田总司": ["冲田", "总司"],
            "谜之女主角X": ["X毛", "星战傻"],
            "阿尔托莉雅·潘德拉贡〔Alter〕": ["黑呆", "黑saber"],
            "贞德〔Alter〕": ["黑贞", "黑村姑"],
            "库·丘林〔Alter〕": ["狂狗", "黑狗"],
            "吉尔伽美什": ["金闪闪", "金皮卡", "吉尔"],
            "伊斯坎达尔": ["大帝", "肌肉王"],
            "梅林": ["花之魔术师", "花之逃亡者", "梅林子"],
            "阿比盖尔·威廉姆斯": ["阿比", "小阿比"],
            "喀耳刻": ["猪神", "C子"],
            "魁札尔科亚特尔": ["羽蛇神", "魁扎尔"],
            "岩窟王": ["基督山伯爵", "爱德蒙·唐泰斯"],
            "阿尔托莉雅·潘德拉贡〔Lancer〕": ["狮子王", "白枪呆"],
            "阿尔托莉雅·潘德拉贡〔Lancer Alter〕": ["黑枪呆"],
            "阿尔托莉雅·潘德拉贡〔Santa Alter〕": ["骑呆", "黑骑呆"],
            "玉藻前": ["小玉", "狐狸", "JK狐"],
            "赫克托耳": ["狗哥"],
            "罗穆路斯": ["狼祖"],
            "BB": ["月BB", "樱BB"],
            "凯妮斯": ["奥德修斯", "奥德修斯·卡隆"],
            "阿育王": ["阿育王AshokaAshoka"],
            "兰陵王": ["兰陵王高长恭", "高长恭"],
            "哪吒": ["三太子"],
            "宇津见绘里世": ["绘里世"],
            "物部布都": ["布都"],
            "帕里斯": ["亚历山大"],
            "清少纳言": ["清少"],
            "项羽": ["项籍"],
            "马嘶": ["马嘶·Ashwatthaman", "阿斯瓦塔曼"],
            "卡利古拉": ["盖乌斯·尤利乌斯·凯撒·奥古斯都·日耳曼尼库斯", "加里古拉"],
            "韦伯·维尔维特": ["君主·埃尔梅罗二世", "埃尔梅罗二世", "埃二", "二世"],
            "克娄巴特拉": ["艳后", "埃及艳后"],
            "尼古拉·特斯拉": ["特斯拉"],
            "戈尔贡": ["美杜莎"],
            "梅杜莎（Lancer）": ["安娜", "美杜莎"],
            "上杉谦信": ["长尾景虎"],
            "李书文": ["老李", "李书文(Assassin)"],
            "杀生院祈荒": ["杀生院", "祈荒"],
            "夏绿蒂·科黛": ["夏洛特"],
            "沃尔夫冈·阿马德乌斯·莫扎特": ["莫扎特"],
            "罗宾汉": ["罗宾"],
            "诸葛孔明": ["孔明", "诸葛亮"],
            "查尔斯·巴贝奇": ["巴贝奇"],
            "苏利耶": ["日神"],
            "弗朗西斯·德雷克": ["船长", "海盗船长"],
            "伊斯坎达尔": ["征服王", "肌肉王"],
            # 添加更多特殊从者的别名
            "图坦卡蒙": ["ツタンカーメン", "Tutankhamun", "法老王"],
            "理查Ⅰ世": ["理查德一世", "狮心王", "Richard I", "リチャードⅠ世"]
        }
        
        if servant_name in special_aliases:
            for alias in special_aliases[servant_name]:
                if alias not in data["别名"]:
                    data["别名"].append(alias)
                    
    return servants_data

def fix_servant_names(servants_data):
    """修复从者名称和别名的问题，处理特殊情况"""
    logger.info("修复从者名称和别名...")
    fixed_data = {}

    # 对每个从者处理名称和别名
    for servant_name, data in servants_data.items():
        if servant_name == "未知":
            # 尝试从稀有度字段中提取真实名称
            rarity_text = data.get("稀有度", "")
            if re.search(r'[\u4e00-\u9fa5]', rarity_text):  # 如果稀有度字段包含中文
                new_name, new_aliases = split_name_and_aliases(rarity_text)
                if new_name != "未知":
                    # 更新从者名称和别名
                    servant_name = new_name
                    data["别名"].extend(new_aliases)
                    logger.info(f"修复从者名称: '未知' -> '{servant_name}', 添加别名: {new_aliases}")
                    
                    # 将稀有度重置为未知，因为原始值可能被错误识别
                    data["稀有度"] = "未知"
        
        # 确保别名中不包含主名称
        data["别名"] = [alias for alias in data["别名"] if alias != servant_name]
        
        # 去除重复别名
        data["别名"] = list(dict.fromkeys(data["别名"]))
        
        # 添加到修复后的数据中
        fixed_data[servant_name] = data
    
    return fixed_data

def save_json_file(data, file_path):
    """保存数据到JSON文件"""
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"数据已成功保存到 {file_path}")
        return True
    except Exception as e:
        logger.error(f"保存数据到 {file_path} 时出错: {e}")
        return False

# --- 主程序 ---
def main():
    logger.info("=== 开始提取FGO Wiki从者数据 ===")
    
    # 1. 从本地HTML文件加载FGO Wiki数据，失败则尝试在线获取
    fgo_soup = get_soup(FGO_WIKI_LOCAL_FILE, use_local=True, fallback_url=FGO_WIKI_URL)
    if not fgo_soup:
        logger.error("无法获取FGO Wiki数据，程序退出。")
        return False
    
    # 2. 解析HTML获取从者数据
    servants_data = parse_fgo_wiki_html(fgo_soup)
    
    if not servants_data:
        logger.error("未能提取到任何从者数据，程序退出。")
        return False
    
    # 3. 修复从者名称和别名问题
    servants_data = fix_servant_names(servants_data)
    
    # 4. 对每个从者添加更多别名
    servants_data = add_special_aliases(servants_data)
    
    # 5. 输出到JSON文件
    logger.info(f"准备将结果写入文件: {OUTPUT_FILENAME}")
    success = save_json_file(servants_data, OUTPUT_FILENAME)
    
    if success:
        logger.info(f"成功将 {len(servants_data)} 条从者数据写入 {OUTPUT_FILENAME}")
        logger.info("脚本执行成功。")
        return True
    else:
        logger.error("保存数据失败，程序退出。")
        return False

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.critical(f"脚本执行过程中发生未处理的异常: {e}", exc_info=True) 