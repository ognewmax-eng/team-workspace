"""Fail if private instance state or known source organization data enters a release."""
from pathlib import Path
import sys
root=Path(__file__).resolve().parents[1]
errors=[]
for p in root.rglob('*'):
    relative=p.relative_to(root)
    if any(x in relative.parts for x in ['.git','.venv','__pycache__']):continue
    if not p.is_file():continue
    if p.name=='.env' or p.suffix in ['.sqlite3'] or relative.parts[0] in ['data','media','logs','staticfiles']:
        errors.append(str(relative)+': private runtime state');continue
    if p.suffix in ['.py','.html','.js','.css','.md','.json','.txt'] and p!=Path(__file__).resolve():
        text=p.read_text(encoding='utf-8')
        needles=['job.yamolod-mur.ru','tsentr-patriot.ru','u3452294','ProjectPlanMedia','934728128296','colleague_2026.json','Школа Ямолод','Муравленко']
        if any(x in text for x in needles):errors.append(str(relative)+': source organization reference')
if errors:
    print('\n'.join(errors));sys.exit(1)
print('Distribution contains no private runtime state or known organization references.')
