import requests
import json

response = requests.get("https://jobicy.com/api/v2/remote-jobs?count=10", timeout=10)
response.raise_for_status()

data = response.json()
print(json.dumps(data, indent=4))
