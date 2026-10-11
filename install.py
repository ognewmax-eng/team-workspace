#!/usr/bin/env python3
"""Interactive first installation. Never resets an existing instance."""
import argparse,getpass,json,os,secrets,subprocess,sys
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
ROOT=Path(__file__).resolve().parent
def run(*args):subprocess.run(list(args),cwd=ROOT,check=True)
def configure():
    path=Path(os.environ.get('WORKSPACE_CONFIG',ROOT/'.env')).resolve()
    if path.exists():
        print('Используется существующий файл настроек. Он не будет заменён.')
        return
    name=input('Название организации: ').strip()
    if not name or len(name)>200:raise SystemExit('Укажите название до 200 символов.')
    url=input('Адрес сайта [http://localhost:8080]: ').strip() or 'http://localhost:8080'
    p=urlsplit(url)
    if p.scheme not in ['http','https'] or not p.hostname or p.username or p.password or p.path not in ['','/'] or p.query or p.fragment:raise SystemExit('Нужен адрес http(s) без пути и пароля.')
    if p.scheme=='http' and p.hostname not in ['localhost','127.0.0.1']:raise SystemExit('Для внешнего домена используйте HTTPS.')
    zone=input('Часовой пояс [Europe/Moscow]: ').strip() or 'Europe/Moscow'
    try:ZoneInfo(zone)
    except ZoneInfoNotFoundError:
        if os.name != "nt":raise SystemExit("Неизвестный часовой пояс или отсутствует системная база tzdata.")
        print("Windows: база часовых поясов будет установлена вместе с зависимостями.")
    values={'ORGANIZATION_NAME':name,'SITE_URL':url.rstrip('/'),'ALLOWED_HOSTS':p.hostname,'TIME_ZONE':zone,'SECRET_KEY':secrets.token_urlsafe(64),'DEBUG':'False','DOMAIN':p.hostname,'TRUST_PROXY':'True' if p.scheme=='https' else 'False'}
    path.parent.mkdir(parents=True,exist_ok=True)
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w',encoding='utf-8') as f:
        for key,value in values.items():f.write(key+'='+json.dumps(value,ensure_ascii=False)+'\n')
    print('Настройки созданы. SMTP и интеграции подключаются отдельно.')
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--mode',choices=['python','docker'],default='python');args=parser.parse_args()
    if sys.version_info<(3,12):raise SystemExit('Установщик требует Python 3.12 или новее.')
    configure()
    if args.mode=='docker':
        run('docker','compose','up','--build','-d','--wait','web','mailings')
        run('docker','compose','exec','web','python','manage.py','initialize_instance')
        print('Для HTTPS на сервере: docker compose --profile server up -d proxy')
    else:
        env=ROOT/'.venv';py=env/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
        if not py.exists():run(sys.executable,'-m','venv',str(env))
        run(str(py),'-m','pip','install','-r','requirements.txt')
        for command in [('migrate','--noinput'),('check',),('collectstatic','--noinput'),('initialize_instance',)]:run(str(py),'manage.py',*command)
        print('Готово. Локальный запуск: '+str(py)+' manage.py runserver 127.0.0.1:8080')
        print('Для хостинга настройте Passenger; инструкции — docs/HOSTING.md.')
if __name__=='__main__':
    try:main()
    except (OSError,ValueError,subprocess.CalledProcessError) as e:raise SystemExit('Установка остановлена: '+str(e)) from None
