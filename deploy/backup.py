"""Consistent SQLite backup. Run as beerhappy, outside the public checkout."""
import os,sqlite3,sys
from pathlib import Path
os.umask(0o077)
source=os.environ.get('DATABASE_PATH','/var/lib/beerhappy/beerhappy.sqlite3')
target=Path(sys.argv[1]);target.parent.mkdir(parents=True,exist_ok=True)
with sqlite3.connect(source) as a,sqlite3.connect(target) as b:a.backup(b)
print('Backup complete')
