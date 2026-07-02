"""서버 실행 진입점"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import uvicorn

if __name__ == "__main__":
    uvicorn.run("web.app:app", host="0.0.0.0", port=3000, reload=True,
                reload_dirs=[str(Path(__file__).parent)])
