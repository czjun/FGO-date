#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import json
import re
from difflib import SequenceMatcher

# --- 常量定义 ---
FGO_WIKI_DATA_FILE = "fgo_wiki_servants_data.json"  # 从extract_fgo_wiki_data.py生成的数据
BANGUMI_MAPPING_FILE = "fgo_name_to_id_mapping.json"
OUTPUT_FILENAME = "improved_fgo_output.json"
UNMAPPED_SERVANTS_FILE = "improved_unmapped_servants.json"
UNUSED_BANGUMI_FILE = "improved_unused_bangumi_entries.json"

# --- 工具函数 ---
def load_json_file(file_path):
    """加载JSON文件"""
    try:
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8-sig') as f:
                return json.load(f)
        else:
            print(f"文件不存在: {file_path}")
            return {}
    except Exception as e:
        print(f"加载文件 {file_path} 时出错: {e}")
        return {}

def save_json_file(data, file_path):
    """保存JSON数据到JSON文件"""
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"数据已成功保存到 {file_path}")
        return True
    except Exception as e:
        print(f"保存数据到 {file_path} 时出错: {e}")
        return False

def standardize_name(name):
    """标准化角色名称，处理各种可能的变体"""
    # 替换中日文点为中文间隔号
    name = name.replace("・", "·")
    
    # 清理名称中的特殊符号
    name = re.sub(r'[（\(].*?[）\)]', '', name)
    name = re.sub(r'〔.*?〕', '', name)
    name = name.split('/')[0].strip()
    
    # 特殊情况处理
    special_replacements = {
        "多布雷尼亚": "多布雷尼娅",
        "太空伊什塔尔": "太空埃列什基伽勒",
        "武藏坊弁庆": "武藏坊辨庆",
        "克里斯汀": "克里斯蒂安",
        "丝卡蒂": "斯卡蒂",
        "格里戈里·拉斯普京": "言峰绮礼",
        "拉斯普京": "言峰绮礼",
        "堂·吉诃德": "堂吉诃德"
    }
    
    for old, new in special_replacements.items():
        if old in name:
            name = name.replace(old, new)
    
    return name

def strip_foreign_chars(name):
    """移除非中文字符"""
    # 保留中文、日文、英文字母和数字
    result = ''.join(c for c in name if '\u4e00' <= c <= '\u9fff' or '\u3040' <= c <= '\u30ff')
    return result.strip()

def split_mixed_name(name):
    """分割混合了中文和外文的名称"""
    # 例如：阿育王AshokaAshoka -> 阿育王, AshokaAshoka
    chinese_part = ''.join(c for c in name if '\u4e00' <= c <= '\u9fff' or '\u3040' <= c <= '\u30ff')
    foreign_part = ''.join(c for c in name if (c.isalpha() and ord(c) < 0x3040) or c.isdigit())
    
    return [p for p in [chinese_part, foreign_part] if p]

def similarity(a, b):
    """计算两个字符串的相似度"""
    return SequenceMatcher(None, a, b).ratio()

def process_bangumi_name(bangumi_name):
    """处理Bangumi名称，获取可能的变体"""
    variants = [bangumi_name]
    
    # 移除括号内容
    no_brackets = re.sub(r'[（\(].*?[）\)]', '', bangumi_name).strip()
    if no_brackets != bangumi_name:
        variants.append(no_brackets)
    
    # 移除所有括号和标记
    clean_name = re.sub(r'[（\(].*?[）\)]', '', bangumi_name)
    clean_name = re.sub(r'〔.*?〕', '', clean_name)
    clean_name = clean_name.split('/')[0].strip()
    if clean_name != bangumi_name and clean_name not in variants:
        variants.append(clean_name)
    
    # 分割中外文混合名称
    split_names = split_mixed_name(bangumi_name)
    variants.extend([n for n in split_names if n not in variants])
    
    # 移除空格
    no_space = bangumi_name.replace(' ', '')
    if no_space != bangumi_name and no_space not in variants:
        variants.append(no_space)
    
    # 返回所有可能的变体
    return variants

def find_bangumi_id(fgo_name, fgo_data, bangumi_map):
    """查找FGO从者对应的Bangumi ID，使用改进的匹配算法"""
    # 标准化从者名称
    normalized_fgo_name = standardize_name(fgo_name)
    
    # 获取从者别名和变体
    aliases = []
    if fgo_name in fgo_data and "别名" in fgo_data[fgo_name]:
        aliases = fgo_data[fgo_name]["别名"]
    
    # 生成可能的名称变体
    fgo_variants = [normalized_fgo_name] + aliases
    fgo_variants.extend(split_mixed_name(normalized_fgo_name))
    fgo_variants.append(strip_foreign_chars(normalized_fgo_name))
    
    # 移除重复
    fgo_variants = list(set(fgo_variants))
    
    # 1. 直接精确匹配
    for variant in fgo_variants:
        for bgm_name, bgm_id in bangumi_map.items():
            bgm_variants = process_bangumi_name(bgm_name)
            for bgm_variant in bgm_variants:
                if variant == bgm_variant:
                    print(f"精确匹配: {fgo_name} -> {bgm_name} (变体: {variant} = {bgm_variant})")
                    return bgm_id
    
    # 2. 包含关系匹配（一个名称是另一个的子串）
    for variant in fgo_variants:
        if len(variant) < 2:  # 跳过过短的变体
            continue
        
        for bgm_name, bgm_id in bangumi_map.items():
            bgm_variants = process_bangumi_name(bgm_name)
            for bgm_variant in bgm_variants:
                if len(bgm_variant) < 2:  # 跳过过短的变体
                    continue
                
                # 检查包含关系
                if variant in bgm_variant or bgm_variant in variant:
                    # 计算相似度作为额外参考
                    sim = similarity(variant, bgm_variant)
                    if sim > 0.5:  # 设定相似度阈值
                        print(f"包含匹配: {fgo_name} -> {bgm_name} (变体: {variant} 包含/被包含于 {bgm_variant}, 相似度: {sim:.2f})")
                        return bgm_id
    
    # 3. 特殊匹配规则
    special_matches = {
        # 特殊匹配规则，格式为：fgo_name: bangumi_name
        "阿育王": "阿育王AshokaAshoka",
        "查理曼": "查理大帝",
        "克琳希德": "布伦希尔德",
        "上杉谦信": "长尾景虎",
        "大和武尊": "日本武尊",
        "诺克娜蕾·雅兰杜": "诺克纳蕾·雅兰杜",
        "莱妮丝": "莱妮丝·埃尔梅罗·阿奇佐尔缇",
        "齐格飞": "齐格弗里德",
        "山鲁佐德": "雪赫拉莎德",
        "杀生院祈荒": "杀生院",
        "凯妮斯": "凯妮斯",
        "安哥拉·曼纽": "安哥拉·曼纽",
        "清姬": "清姬",
        "西格鲁德": "西格鲁德",
        "百貌哈桑": "百貌的哈桑",
        "静谧哈桑": "静谧的哈桑",
        "咒腕哈桑": "咒腕的哈桑",
        "BB迪拜": "BB",
        "谜之代行者C.I.E.L": "希耶尔",
        "响＆千键": "日比乃响",
        "岩窟王　基督山": "基督山伯爵 爱德蒙·唐泰斯",
        "喀耳刻": "喀耳刻",
        "尼托克里斯": "尼托克里斯",
        "梅林": "梅林",
        "玉藻前": "玉藻前",
        "罗宾汉": "罗宾汉",
        "贞德": "贞德",
        "阿维斯布隆": "齐格鲁德",
        "玄奘三藏": "玄奘三蔵",
        "BeastⅢ／L": "杀生院",
        "伊莉雅": "伊莉雅斯菲尔·冯·爱因兹贝伦",
        "克洛伊·冯·爱因兹贝伦": "伊莉雅斯菲尔·冯·爱因兹贝伦",
        "美游·艾德费尔特": "美游",
        "宫本武藏": "新免武藏守藤原玄信",
        "夏洛特·科黛": "夏绿蒂·科黛"
    }
    
    # 尝试特殊匹配
    if fgo_name in special_matches:
        target_name = special_matches[fgo_name]
        for bgm_name, bgm_id in bangumi_map.items():
            if target_name in bgm_name or bgm_name in target_name:
                print(f"特殊匹配: {fgo_name} -> {bgm_name} (目标: {target_name})")
                return bgm_id
    
    # 4. 模糊匹配（编辑距离）
    best_match = None
    best_sim = 0.7  # 设置相似度阈值
    
    for variant in fgo_variants:
        if len(variant) < 2:  # 跳过过短的变体
            continue
        
        for bgm_name, bgm_id in bangumi_map.items():
            bgm_variants = process_bangumi_name(bgm_name)
            for bgm_variant in bgm_variants:
                if len(bgm_variant) < 2:  # 跳过过短的变体
                    continue
                
                sim = similarity(variant, bgm_variant)
                if sim > best_sim:
                    best_sim = sim
                    best_match = (bgm_name, bgm_id, variant, bgm_variant, sim)
    
    if best_match:
        bgm_name, bgm_id, variant, bgm_variant, sim = best_match
        print(f"模糊匹配: {fgo_name} -> {bgm_name} (变体: {variant} 与 {bgm_variant}, 相似度: {sim:.2f})")
        return bgm_id
    
    # 没有找到匹配
    return None

def format_output_data(servant_data):
    """格式化输出数据"""
    # 处理稀有度
    rarity = servant_data.get("稀有度", "未知")
    rarity_val = {
        rarity: rarity
    }

    # 处理职阶
    servant_class = servant_data.get("职阶", "未知")
    class_rarity = servant_data.get("稀有度", "未知")[0] if servant_data.get("稀有度", "未知")[0].isdigit() else "5"
    
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
        "Shielder": "盾兵",
        "Beast": "Beast"
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
    
    img_path = f"/assets/tag/fgo/Class/{rarity_prefix}{servant_class}.png"
    class_val = {
        class_display: f"<img src='{img_path}' alt='{class_display}' /> {class_display}"
    }

    # 处理宝具色卡
    np_card = servant_data.get("宝具色卡", "未知")
    np_card_display_map = {
        "Quick": "绿卡",
        "Arts": "蓝卡",
        "Buster": "红卡"
    }
    display_text = np_card_display_map.get(np_card, np_card)
    np_card_val = {
        display_text: f"<img src='/assets/tag/fgo/Color/{np_card}.png' alt='{display_text}' /> {display_text}"
    }

    # 处理宝具类型
    np_type = servant_data.get("宝具类型", "未知")
    np_type_val = {np_type: np_type}

    # 处理获取途径
    acquisition = servant_data.get("获取途径", "未知途径")
    acquisition_keywords = [
        "圣晶石常驻", "友情点召唤", "剧情限定", "期间限定", "活动赠送", 
        "通关赠送", "无法获得", "剧情解锁", "初始获得", "其他"
    ]
    
    acquisition_val = {}
    for keyword in acquisition_keywords:
        if keyword in acquisition:
            acquisition_val[keyword] = keyword
    
    if not acquisition_val:
        acquisition_val = {acquisition: acquisition}

    return {
        "稀有度": rarity_val,
        "职阶": class_val,
        "宝具色卡": np_card_val,
        "宝具类型": np_type_val,
        "获取途径": acquisition_val,
    }

# --- 主程序 ---
if __name__ == "__main__":
    print("开始执行改进的FGO从者匹配脚本...")
    
    # 1. 加载数据
    fgo_wiki_data = load_json_file(FGO_WIKI_DATA_FILE)
    bangumi_character_map = load_json_file(BANGUMI_MAPPING_FILE)
    
    if not fgo_wiki_data or not bangumi_character_map:
        print("无法加载必要的数据文件，程序退出。")
        exit(1)
    
    print(f"已加载FGO Wiki数据: {len(fgo_wiki_data)} 条从者记录")
    print(f"已加载Bangumi映射数据: {len(bangumi_character_map)} 条角色记录")
    
    # 2. 执行匹配
    final_output_data = {}
    unmapped_fgo_names = []
    used_bangumi_entries = set()
    
    for fgo_name, fgo_details in fgo_wiki_data.items():
        print(f"\n处理从者: {fgo_name}")
        bangumi_id = find_bangumi_id(fgo_name, fgo_wiki_data, bangumi_character_map)
        
        if bangumi_id:
            # 匹配成功
            used_bangumi_entries.add(bangumi_id)
            formatted_data = format_output_data(fgo_details)
            final_output_data[bangumi_id] = formatted_data
            print(f"成功匹配: {fgo_name} -> Bangumi ID: {bangumi_id}")
        else:
            # 匹配失败
            unmapped_fgo_names.append((fgo_name, fgo_details))
            print(f"未找到匹配: {fgo_name}")
    
    # 找出未使用的Bangumi条目
    unused_bangumi_entries = []
    for bgm_name, bgm_id in bangumi_character_map.items():
        if bgm_id not in used_bangumi_entries:
            unused_bangumi_entries.append((bgm_name, bgm_id))
    
    # 3. 保存匹配结果
    print(f"\n匹配结果统计:")
    print(f"总从者数: {len(fgo_wiki_data)}")
    print(f"成功匹配: {len(final_output_data)} ({len(final_output_data)/len(fgo_wiki_data)*100:.2f}%)")
    print(f"未匹配从者: {len(unmapped_fgo_names)}")
    print(f"未使用Bangumi条目: {len(unused_bangumi_entries)}")
    
    # 保存最终输出
    if save_json_file(final_output_data, OUTPUT_FILENAME):
        print(f"成功将匹配结果保存到: {OUTPUT_FILENAME}")
    
    # 保存未匹配的从者
    if unmapped_fgo_names:
        unmapped_data = {name: details for name, details in unmapped_fgo_names}
        if save_json_file(unmapped_data, UNMAPPED_SERVANTS_FILE):
            print(f"成功将未匹配从者保存到: {UNMAPPED_SERVANTS_FILE}")
    
    # 保存未使用的Bangumi条目
    if unused_bangumi_entries:
        unused_data = {name: {"bangumi_id": bgm_id} for name, bgm_id in unused_bangumi_entries}
        if save_json_file(unused_data, UNUSED_BANGUMI_FILE):
            print(f"成功将未使用Bangumi条目保存到: {UNUSED_BANGUMI_FILE}")
    
    print("\n脚本执行完成。") 