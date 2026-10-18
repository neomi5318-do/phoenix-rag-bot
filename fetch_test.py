import requests
from bs4 import BeautifulSoup

url = "https://www.fnx.co.il/claims-customer-service/claims-car-insurance/claims-property-car-insurance/"

response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
print("סטטוס:", response.status_code)

soup = BeautifulSoup(response.text, "html.parser")

# מחיקת אזורים שהם לא תוכן
for tag in soup(["script", "style", "nav", "header", "footer"]):
    tag.decompose()

# חיפוש אזור התוכן הראשי
main = soup.find("main") or soup.find("article") or soup.body
text = main.get_text(separator="\n", strip=True)

print("אורך הטקסט:", len(text))
print(text[:2000])