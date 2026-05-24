#!/root/.openclaw/workspace/venv/bin/python3
"""
Cross-Verification Helper v1.0

Validates multi-source search results for consistency and credibility.
Usage:
    python3 cross_verify.py --file search_results.json
    python3 cross_verify.py --exa "exa_results.txt" --zsxq "zsxq_results.json"
"""

import json
import re
import argparse
from collections import defaultdict
from datetime import datetime


def extract_key_events(results: dict) -> list:
    """Extract key events from search results."""
    events = []
    
    # Parse Exa results
    exa_results = results.get('P1_Exa', [])
    for entry in exa_results:
        if isinstance(entry, dict) and 'highlights' in entry:
            title = entry.get('title', '')
            for hl in entry.get('highlights', []):
                events.append({
                    'text': f"{title}: {hl}",
                    'source': 'Exa',
                    'url': entry.get('url', ''),
                    'type': 'news'
                })
    
    # Parse zsxq results
    zsxq_results = results.get('P2_zsxq', [])
    for entry in zsxq_results:
        if isinstance(entry, dict) and 'content' in entry:
            events.append({
                'text': f"{entry.get('title', '')}: {entry.get('content', '')[:200]}",
                'source': 'zsxq',
                'date': entry.get('date', ''),
                'author': entry.get('author', ''),
                'type': 'research_note'
            })
    
    # Parse Sina results
    sina_results = results.get('P3_Sina', [])
    for entry in sina_results:
        if isinstance(entry, dict) and 'title' in entry:
            events.append({
                'text': entry.get('title', ''),
                'source': 'Sina',
                'url': entry.get('url', ''),
                'time': entry.get('time', ''),
                'type': 'news'
            })
    
    return events


def find_cross_verified_events(events: list, min_sources: int = 2) -> list:
    """Find events confirmed by multiple independent sources."""
    # Group by semantic similarity (simple keyword overlap)
    verified = []
    
    for i, event in enumerate(events):
        matches = [event]
        keywords = set(re.findall(r'[\u4e00-\u9fa5]{2,8}', event['text']))
        
        for j, other in enumerate(events[i+1:], i+1):
            other_keywords = set(re.findall(r'[\u4e00-\u9fa5]{2,8}', other['text']))
            overlap = len(keywords & other_keywords)
            total = len(keywords | other_keywords)
            
            if total > 0 and overlap / total > 0.3 and event['source'] != other['source']:
                matches.append(other)
        
        sources = set(e['source'] for e in matches)
        if len(sources) >= min_sources and event not in [v['primary'] for v in verified]:
            verified.append({
                'primary': event,
                'matches': matches[1:],
                'sources': list(sources),
                'confidence': len(sources) * 0.3 + len(matches) * 0.1
            })
    
    return sorted(verified, key=lambda x: x['confidence'], reverse=True)


def generate_verification_report(results: dict) -> str:
    """Generate a cross-verification report."""
    events = extract_key_events(results)
    verified = find_cross_verified_events(events)
    
    report = []
    report.append("# 多源搜索交叉验证报告")
    report.append("")
    report.append(f"搜索关键词: {results.get('keyword', 'N/A')}")
    report.append(f"搜索时间: {results.get('search_time', 'N/A')}")
    report.append(f"总事件数: {len(events)}")
    report.append(f"交叉验证通过: {len(verified)} 条")
    report.append("")
    
    report.append("## 交叉验证通过的事件 (≥2独立来源)")
    report.append("")
    
    for i, v in enumerate(verified[:10], 1):
        report.append(f"### {i}. {v['primary']['text'][:80]}")
        report.append(f"- 来源: {', '.join(v['sources'])}")
        report.append(f"- 置信度: {v['confidence']:.2f}")
        report.append(f"- 匹配数: {len(v['matches'])}")
        if v['primary'].get('url'):
            report.append(f"- URL: {v['primary']['url']}")
        report.append("")
    
    report.append("## 单一来源事件 (需进一步验证)")
    report.append("")
    
    single_source = [e for e in events if e['text'] not in [v['primary']['text'] for v in verified]]
    for e in single_source[:5]:
        report.append(f"- [{e['source']}] {e['text'][:100]}")
    
    return "\n".join(report)


def verify_checklist(results: dict) -> dict:
    """Check if all mandatory sources were used."""
    checklist = {
        'P1_Exa_executed': len(results.get('P1_Exa', [])) > 0,
        'P2_zsxq_executed': len(results.get('P2_zsxq', [])) > 0,
        'P3_Sina_executed': len(results.get('P3_Sina', [])) > 0,
        'cross_verification': len(find_cross_verified_events(extract_key_events(results))) > 0,
        'key_catalyst_found': False,  # Needs manual review
        'metrics_quantified': False,  # Needs manual review
    }
    
    # Auto-check for quantified metrics (numbers with % or 亿/万)
    all_text = ""
    for key in ['P1_Exa', 'P2_zsxq', 'P3_Sina']:
        for item in results.get(key, []):
            if isinstance(item, dict):
                all_text += str(item)
    
    if re.search(r'\d+[\d,]*\.?\d*\s*[亿万千兆%只]', all_text):
        checklist['metrics_quantified'] = True
    
    return checklist


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Cross-Verification Helper')
    parser.add_argument('--file', type=str, help='Input JSON file from multi_source_search.py')
    parser.add_argument('--output', type=str, help='Output report file')
    
    args = parser.parse_args()
    
    if not args.file:
        print("Usage: python3 cross_verify.py --file search_results.json")
        sys.exit(1)
    
    with open(args.file, 'r', encoding='utf-8') as f:
        results = json.load(f)
    
    report = generate_verification_report(results)
    checklist = verify_checklist(results)
    
    print(report)
    print("\n## 检查清单")
    for key, value in checklist.items():
        status = "✅" if value else "❌"
        print(f"{status} {key}")
    
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(report)
            f.write("\n\n## 检查清单\n")
            for key, value in checklist.items():
                status = "✅" if value else "❌"
                f.write(f"{status} {key}\n")
        print(f"\nReport saved to {args.output}")
