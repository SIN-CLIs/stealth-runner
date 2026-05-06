# Plan SR-36: Generated Docs De-Duplication & Quality Check

## Overview
470+ generated doc files across 24 repos. Most are empty boilerplate. Audit, score, deduplicate, cleanup.

## Audit Script

```python
# scripts/audit_docs.py

import os, json, hashlib
from pathlib import Path

REPOS_DIR = Path("/Users/jeremy/dev")
STEALTH_PATTERN = lambda d: 'stealth' in d.lower() or d.startswith('playstealth') or d == 'OpenSIN-stealth-browser'

def audit_all():
    results = {}
    for repo_dir in REPOS_DIR.iterdir():
        if not repo_dir.is_dir() or not STEALTH_PATTERN(repo_dir.name):
            continue
        if not (repo_dir / '.git').exists():
            continue
        
        for md_file in repo_dir.glob("*.md"):
            content = md_file.read_text()
            size = len(content)
            
            results[str(md_file)] = {
                'repo': repo_dir.name,
                'file': md_file.name,
                'size': size,
                'lines': content.count('\n'),
                'word_count': len(content.split()),
                'hash': hashlib.sha256(content.encode()).hexdigest(),
                'has_code_blocks': '```' in content,
                'has_headings': content.count('##'),
            }
    
    # Save report
    with open('doc_audit_report.json', 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    # Summary
    total = len(results)
    empty = sum(1 for v in results.values() if v['lines'] < 5)
    low_quality = sum(1 for v in results.values() if v['lines'] < 20)
    print(f"Total: {total} docs")
    print(f"Empty (<5 lines): {empty}")
    print(f"Low quality (<20 lines): {low_quality}")
    print(f"Good (>100 lines): {total - low_quality - empty}")
    
    return results
```

## Quality Score

```python
def score_doc(filepath: Path) -> int:
    """Score 0-100 for documentation quality."""
    content = filepath.read_text()
    score = 0
    
    # Length
    lines = content.count('\n')
    if lines > 200: score += 20
    elif lines > 100: score += 15
    elif lines > 50: score += 10
    elif lines > 20: score += 5
    
    # Structure
    headings = content.count('##')
    score += min(headings * 3, 15)
    
    # Code examples
    code_blocks = content.count('```')
    score += min(code_blocks * 5, 15)
    
    # Links
    links = content.count('](')
    score += min(links * 2, 10)
    
    # Specific content (not boilerplate)
    boilerplate_phrases = ['WAS', 'WO', 'WANN', 'WOMIT', 'ZWECK']
    has_boilerplate = any(bp in content for bp in boilerplate_phrases)
    if not has_boilerplate and lines > 50:
        score += 20
    
    # File purpose clear
    if content.strip().startswith('# '):
        score += 10
    
    return min(score, 100)
```

## De-Duplication

```python
def find_duplicates(results):
    """Group identical files by hash."""
    groups = {}
    for path, info in results.items():
        h = info['hash']
        groups.setdefault(h, []).append(path)
    
    duplicates = {h: paths for h, paths in groups.items() if len(paths) > 1}
    
    for h, paths in duplicates.items():
        print(f"\n{len(paths)}× identical ({paths[0].split('/')[-1]}):")
        for p in paths[:5]:
            print(f"  {p}")
    
    return duplicates
```

## Cleanup Strategy

```
Score 0-10  → Löschen (leer / boilerplate)
Score 10-30 → Review (eventuell löschen)
Score 30-60 → Behalten (basic content)
Score 60-100 → Behalten (good content)

Priority: Keep files in stealth-runner first (central repo).
Files in other repos that are duplicates of stealth-runner → delete.
```

## Implementation: ~2h
