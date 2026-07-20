@echo off
rem Автобэкап nocturne (задача 61) — обёртка для Планировщика задач Windows.
rem backup_db.py использует только стандартную библиотеку, venv не нужен.
rem Лог пишется в backups\backup.log (дозапись).
cd /d %~dp0
if not exist backups mkdir backups
echo [%date% %time%] запуск бэкапа >> backups\backup.log
py -3 backup_db.py >> backups\backup.log 2>&1
