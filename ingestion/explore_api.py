import requests
import json

JOBICY = "https://jobicy.com/api/v2/remote-jobs?count=10"
HIMALAYAS = "https://himalayas.app/jobs/api?limit=10"
ARBEITNOW = "https://www.arbeitnow.com/api/job-board-api"
response = requests.get(HIMALAYAS, timeout=10)
response.raise_for_status()

data = response.json()
print(json.dumps(data, indent=4))
