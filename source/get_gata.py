import requests

USERNAME = "akarmain"
YEAR = 2025

url = f"https://github-contributions-api.jogruber.de/v4/{USERNAME}?y={YEAR}"

data = requests.get(url).json()

zero_days = []

for day in data["contributions"]:
    if day["count"] == 0:
        zero_days.append(day["date"])

print("Дни где не было contributions:")
print(zero_days)
