"""Fail if private instance state or known source organization data enters a release."""
from pathlib import Path
import re
import sys
root=Path(__file__).resolve().parents[1]
errors=[]
for p in root.rglob('*'):
    relative=p.relative_to(root)
    if any(x in relative.parts for x in ['.git','.venv','__pycache__']):continue
    if not p.is_file():continue
    if (p.name.startswith('.env') and p.name!='.env.example') or p.name in ['preview.html','synology.json','credentials.json','token.json'] or p.suffix.lower() in ['.sqlite3','.sqlite','.db','.sql','.pem','.key','.p12','.pfx','.zip','.gz','.bak','.log'] or relative.parts[0] in ['data','media','logs','staticfiles','backups']:
        errors.append(str(relative)+': private runtime state');continue
    if p.suffix in ['.py','.html','.js','.css','.md','.json','.txt','.yaml','.yml','.example','.sh'] and p!=Path(__file__).resolve():
        text=p.read_text(encoding='utf-8')
        needles=['job.yamolod-mur.ru','tsentr-patriot.ru','u3452294','ProjectPlanMedia','934728128296','colleague_2026.json','Школа Ямолод','Муравленко']
        if any(x in text for x in needles):errors.append(str(relative)+': source organization reference')
        patterns = {
            'private key': r'-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----',
            'GitHub token': r'\b(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,})\b',
            'Telegram token': r'\b\d{7,12}:[A-Za-z0-9_-]{30,}\b',
            'AWS access key': r'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b',
            'Google API key': r'\bAIza[A-Za-z0-9_-]{30,}\b',
            'credentials in URL': r'https?://[^\s/\"\'<>]+:[^\s/\"\'<>]+@',
            'rendered CSRF token': r'(?i)name=[\"\']csrfmiddlewaretoken[\"\'][^>]*value=[\"\'][A-Za-z0-9]{32,64}[\"\']',
        }
        for label,pattern in patterns.items():
            if re.search(pattern,text):errors.append(str(relative)+': '+label)
if errors:
    print('\n'.join(errors));sys.exit(1)
print('Distribution contains no private runtime state or known organization references.')
