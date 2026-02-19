#!/usr/bin/env python3
"""
Markdown Token 压缩工具 - 简化版
功能：压缩 Markdown 文件以节约 LLM Token
"""

import re
import sys
import json
import argparse
from pathlib import Path

def load_config(config_path='.qmdrc.json'):
    """加载配置文件"""
    default_config = {
        "remove_extra_whitespace": True,
        "collapse_empty_lines": True,
        "trim_trailing_whitespace": True,
        "strip_comments": True,
        "max_heading_level": 4,
        "shorten_code_fences": True,
        "replace_images": True,
        "image_placeholder": "[图]"
    }
    
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
            # 合并默认配置
            for key, value in default_config.items():
                if key not in config:
                    config[key] = value
            return config
    except:
        return default_config

def compress_markdown(content, config):
    """压缩 Markdown 内容"""
    original_size = len(content)
    
    # 1. 移除 HTML 注释
    if config.get('strip_comments', True):
        content = re.sub(r'<!--.*?-->', '', content, flags=re.DOTALL)
    
    # 2. 移除多余空行
    if config.get('collapse_empty_lines', True):
        content = re.sub(r'\n{3,}', '\n\n', content)
    
    # 3. 移除行尾空格
    if config.get('trim_trailing_whitespace', True):
        content = re.sub(r'[ \t]+$', '', content, flags=re.MULTILINE)
    
    # 4. 移除多余空格
    if config.get('remove_extra_whitespace', True):
        content = re.sub(r'  +', ' ', content)
    
    # 5. 简化代码块标记
    if config.get('shorten_code_fences', True):
        content = re.sub(r'```(\w+)\n', r'```\1\n', content)
    
    # 6. 替换图片为占位符
    if config.get('replace_images', True):
        placeholder = config.get('image_placeholder', '[图]')
        content = re.sub(r'!\[.*?\]\(.*?\)', placeholder, content)
    
    # 7. 简化表格（移除多余空格）
    lines = content.split('\n')
    compressed_lines = []
    in_table = False
    
    for line in lines:
        # 检测表格行
        if line.strip().startswith('|') and line.strip().endswith('|'):
            # 简化表格行内的空格
            line = re.sub(r'\| +', '|', line)
            line = re.sub(r' +\|', '|', line)
        compressed_lines.append(line)
    
    content = '\n'.join(compressed_lines)
    
    # 8. 移除开头的空行
    content = content.lstrip('\n')
    
    compressed_size = len(content)
    
    return content, original_size, compressed_size

def analyze_content(content):
    """分析内容统计"""
    lines = content.split('\n')
    
    stats = {
        'total_lines': len(lines),
        'heading_lines': len([l for l in lines if l.strip().startswith('#')]),
        'code_blocks': len(re.findall(r'```', content)) // 2,
        'tables': len([l for l in lines if l.strip().startswith('|')]),
        'images': len(re.findall(r'!\[.*?\]\(.*?\)', content)),
        'links': len(re.findall(r'\[.*?\]\(.*?\)', content)),
        'chars': len(content),
        'words': len(content.split())
    }
    
    return stats

def main():
    parser = argparse.ArgumentParser(description='Markdown Token 压缩工具')
    parser.add_argument('command', choices=['compress', 'analyze'], help='操作命令')
    parser.add_argument('file', help='输入文件路径')
    parser.add_argument('-o', '--output', help='输出文件路径')
    parser.add_argument('--stats', action='store_true', help='显示统计信息')
    parser.add_argument('-c', '--config', default='.qmdrc.json', help='配置文件路径')
    
    args = parser.parse_args()
    
    # 加载配置
    config = load_config(args.config)
    
    # 读取输入文件
    try:
        with open(args.file, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"❌ 错误: 无法读取文件 {args.file}: {e}")
        sys.exit(1)
    
    if args.command == 'analyze':
        # 分析模式
        stats = analyze_content(content)
        print("📊 文件分析统计")
        print("=" * 40)
        print(f"总行数: {stats['total_lines']}")
        print(f"标题行: {stats['heading_lines']}")
        print(f"代码块: {stats['code_blocks']}")
        print(f"表格行: {stats['tables']}")
        print(f"图片数: {stats['images']}")
        print(f"链接数: {stats['links']}")
        print(f"字符数: {stats['chars']}")
        print(f"词数: {stats['words']}")
        print("=" * 40)
        
    elif args.command == 'compress':
        # 压缩模式
        compressed, original_size, compressed_size = compress_markdown(content, config)
        
        # 保存输出
        if args.output:
            try:
                with open(args.output, 'w', encoding='utf-8') as f:
                    f.write(compressed)
                print(f"✅ 已保存到: {args.output}")
            except Exception as e:
                print(f"❌ 错误: 无法保存文件: {e}")
                sys.exit(1)
        else:
            print(compressed)
        
        # 显示统计
        if args.stats:
            saved = original_size - compressed_size
            percent = (saved / original_size * 100) if original_size > 0 else 0
            
            print("\n" + "=" * 40)
            print("📊 压缩统计")
            print("=" * 40)
            print(f"原始大小: {original_size:,} 字符")
            print(f"压缩后:   {compressed_size:,} 字符")
            print(f"节约:     {saved:,} 字符 ({percent:.1f}%)")
            print("=" * 40)

if __name__ == '__main__':
    main()
