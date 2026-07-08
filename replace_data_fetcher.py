#!/usr/bin/env python3
"""Replace embedded multi-source data functions in v41 and v42 with import from data_fetcher"""

import re

# Files to process
files = [
    '/root/.openclaw/workspace/skills/chanlun-analysis/scripts/chanlun_v41.py',
    '/root/.openclaw/workspace/skills/chanlun-analysis/scripts/chanlun_v42_review.py',
]

replacement = """# =====================================================
# 多数据源获取（优先级：tdxrs > 长桥 > tushare > efinance）
from data_fetcher import fetch_data, fetch_longbridge
# =====================================================
"""

for filepath in files:
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Find the block from "# =====================================================" after imports
    # to the end of "def fetch_data(...)" block
    # We want to replace from "# =====================================================\n\ndef _parse_symbol" 
    # to the end of the fetch_data function (until next "def ma(" or "# =====================================================")
    
    pattern = r'(# =====================================================\n\n?def _parse_symbol\(.*?)(?=\n# =+\n# 级别合成|\n# =+\n# v\d+\.\d+ |\n# =+\n# v\d+\.\d+核心|\n# =+\n# 指标计算|\n# =+\n# v\d+\.\d+ |\n# =+\n# 段数分解)'
    
    match = re.search(pattern, content, re.DOTALL)
    if match:
        old_block = match.group(1)
        new_content = content[:match.start()] + replacement + content[match.end():]
        
        with open(filepath, 'w') as f:
            f.write(new_content)
        print(f"✅ Replaced data functions in {filepath.split('/')[-1]}")
    else:
        # Try alternate pattern: find from first "# =====================================================" after imports
        lines = content.split('\n')
        import_idx = -1
        for i, line in enumerate(lines):
            if 'from data_fetcher import' in line or 'from longport.openapi' in line:
                import_idx = i
        
        # Look for the block starting with "# =====================================================" then "def _parse_symbol"
        for i in range(import_idx + 1, len(lines)):
            if lines[i].strip() == '# =====================================================' and i+1 < len(lines) and 'def _parse_symbol' in lines[i+1]:
                start = i
                # Find end: next major section marker
                end = None
                for j in range(start+1, len(lines)):
                    if lines[j].strip() == '# =====================================================' and j+1 < len(lines):
                        next_line = lines[j+1].strip()
                        if next_line.startswith('# 级别合成') or next_line.startswith('# 指标计算') or next_line.startswith('# v') or next_line.startswith('# 段数') or next_line.startswith('# 数据获取') or next_line.startswith('# 级别合成') or next_line.startswith('# MACD'):
                            end = j
                            break
                if end:
                    new_lines = lines[:start] + ['# =====================================================', '# 多数据源获取（优先级：tdxrs > 长桥 > tushare > efinance）', 'from data_fetcher import fetch_data, fetch_longbridge', '# ====================================================='] + lines[end:]
                    with open(filepath, 'w') as f:
                        f.write('\n'.join(new_lines))
                    print(f"✅ Replaced data functions in {filepath.split('/')[-1]} (line-based)")
                break
        else:
            print(f"⚠️ Could not find pattern in {filepath.split('/')[-1]}, skipping")

# Verify
print("\n--- Verification ---")
for filepath in files:
    name = filepath.split('/')[-1]
    with open(filepath, 'r') as f:
        lines = f.readlines()
    import_count = sum(1 for l in lines if 'from data_fetcher' in l)
    def_count = sum(1 for l in lines if l.startswith('def _parse_symbol') or l.startswith('def fetch_tdxrs') or l.startswith('def fetch_tushare') or l.startswith('def fetch_efinance') or l.startswith('def fetch_data('))
    call_count = sum(1 for l in lines if 'fetch_data(' in l and 'def ' not in l)
    print(f"{name}: import={import_count}, local_data_funcs={def_count}, calls={call_count}")
