#!/usr/bin/env python3
"""Fix scripts that have both 'from data_fetcher import fetch_data' and local 'def fetch_data(...)'"""
import re
import sys

files = [
    '/root/.openclaw/workspace/skills/chanlun-analysis/scripts/chanlun_v40_revised.py',
    '/root/.openclaw/workspace/skills/chanlun-analysis/scripts/chanlun_v40_revised_backup.py',
    '/root/.openclaw/workspace/skills/chanlun-analysis/scripts/chanlun_v40_full.py',
    '/root/.openclaw/workspace/skills/chanlun-analysis/scripts/chanlun_v41_upgraded.py',
]

for filepath in files:
    with open(filepath, 'r') as f:
        content = f.read()
    
    original = content
    
    # Remove duplicate "from data_fetcher import fetch_data" lines (keep first)
    lines = content.split('\n')
    seen_import = False
    cleaned_lines = []
    for line in lines:
        if 'from data_fetcher import fetch_data' in line:
            if not seen_import:
                seen_import = True
                cleaned_lines.append(line)
            # else skip duplicate
        else:
            cleaned_lines.append(line)
    content = '\n'.join(cleaned_lines)
    
    # Remove local def fetch_data(...) blocks (keep the imported one)
    # Pattern: from "def fetch_data" to the next blank line before another def/class
    if seen_import:
        # Remove the block starting with "def fetch_data(..." until next top-level definition
        pattern = r'(def fetch_data\(symbol, period, count\):.*?)(?=\n(def |class |# ===|\n# =+|\n# v\d+\.))'
        match = re.search(pattern, content, re.DOTALL)
        if match:
            # Also remove preceding comments about "多数据源获取"
            block_start = match.start()
            # Look back for comment lines before the def
            prefix = content[:block_start]
            # Remove trailing empty lines and comment lines about data source
            prefix_lines = prefix.rstrip().split('\n')
            # Remove lines that are empty or comment about data source, going backward
            while prefix_lines and (prefix_lines[-1].strip() == '' or '多数据源' in prefix_lines[-1] or '数据获取' in prefix_lines[-1] or prefix_lines[-1].strip() == '# ====================================================='):
                prefix_lines.pop()
            prefix = '\n'.join(prefix_lines) + '\n\n'
            content = prefix + content[match.end():]
    
    # Remove extra comment lines about 多数据源获取
    content = re.sub(r'# 多数据源获取（优先级：tdxrs > 长桥 > tushare > efinance）\n', '', content)
    content = re.sub(r'# =====================================================\n# 多数据源获取（优先级：tdxrs > 长桥 > tushare > efinance）\nfrom data_fetcher import fetch_data\n# =====================================================\n# 数据获取\n# =====================================================\n# 多数据源获取（优先级：tdxrs > 长桥 > tushare > efinance）\n# =====================================================\n', 
                     '# =====================================================\n# 多数据源获取（优先级：tdxrs > 长桥 > tushare > efinance）\nfrom data_fetcher import fetch_data\n# =====================================================\n', content)
    
    if content != original:
        with open(filepath, 'w') as f:
            f.write(content)
        print(f"Fixed: {filepath}")
    else:
        print(f"No changes needed: {filepath}")

# Verify
print("\n--- Verification ---")
for filepath in files:
    name = filepath.split('/')[-1]
    with open(filepath, 'r') as f:
        lines = f.readlines()
    import_count = sum(1 for l in lines if 'from data_fetcher import fetch_data' in l)
    def_count = sum(1 for l in lines if l.startswith('def fetch_data('))
    call_count = sum(1 for l in lines if 'fetch_data(' in l and 'def ' not in l)
    print(f"{name}: import={import_count}, local_def={def_count}, calls={call_count}")
