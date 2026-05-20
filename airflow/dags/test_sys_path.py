import sys 
from pathlib import Path

print(sys.path)
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
print(sys.path)