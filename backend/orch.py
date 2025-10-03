import sys
import json

if __name__ == "__main__":#must submit sbatch of containers with services and resources as well as clients
    print("hello from the orchestrator python")
    json_str = sys.argv[1]
    data = json.loads(json_str)
    print("received JSON:", data)


