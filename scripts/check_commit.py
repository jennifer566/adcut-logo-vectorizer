import re
import sys
from pathlib import Path

subject = Path(sys.argv[1]).read_text(encoding="utf-8").splitlines()[0]
if not re.match(r"^(feat|fix|docs|test|chore|refactor|build|ci)(\([^)]+\))?!?: .+", subject):
    raise SystemExit("Use a conventional commit, for example: feat: add image upload")
