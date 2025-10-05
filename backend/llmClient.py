
import sys
import json

# it must submit requests to the ollama server or servers
if __name__ == "__main__":
    print("hello I'm a client!")
    queryParams = sys.argv[1]
    data = json.loads(json_str)

    print("received JSON:", data) #print statements will be shown in .out file