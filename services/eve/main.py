import sys
from pathlib import Path

# Add src directory to Python path
src_dir = Path(__file__).parent / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from eve_agent.app import create_app

app = create_app()

if __name__ == '__main__':
    import uvicorn
    from eve_agent.config import get_settings
    
    settings = get_settings()
    uvicorn.run(app, host=settings.api_host, port=settings.api_port, log_level="info")
