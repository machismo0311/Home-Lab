# 🔍 Server Scraper - eBay / TechMikeNY / Bargain Hardware
**Tags:** #projects #python #automation  
**Related:** [[00 - Homelab MOC]]  
**Location:** `~/serverscraper/`  
**Status:** ✅ Built and running

---

## Overview

Custom Python scraper monitoring eBay, TechMikeNY, and Bargain Hardware for homelab server deals. Features SQLite deduplication, Ohio seller prioritization, and email alerting.

---

## Features

| Feature | Detail |
|---|---|
| Sources | eBay, TechMikeNY, Bargain Hardware |
| Deduplication | SQLite - avoids re-alerting on seen listings |
| Ohio prioritization | Scores OH sellers higher (cheaper local pickup) |
| Email alerting | Sends digest when new deals found |
| Scheduling | cron or systemd timer |

---

## File Structure

```
~/serverscraper/
├── main.py           # Orchestrator
├── scrapers/
│   ├── ebay.py       # eBay search via API / scrape
│   ├── techmikenY.py # TechMikeNY inventory
│   └── bargain.py    # Bargain Hardware
├── db.py             # SQLite interface
├── alert.py          # Email via SMTP / sendmail
├── config.py         # Keywords, filters, thresholds
└── requirements.txt
```

---

## Config (config.py)

```python
KEYWORDS = [
    "dell r730", "supermicro", "hp proliant",
    "xeon e5", "quadro rtx", "10gbe",
    "netapp", "jbod", "sfp+"
]

MAX_PRICE = 300        # USD
OHIO_BONUS = 50        # Add $50 effective discount for OH sellers
EMAIL_TO = "kyle@kylemason.org"
DB_PATH = "~/serverscraper/seen.db"
CHECK_INTERVAL_MINUTES = 60
```

---

## Running

```bash
cd ~/serverscraper
python3 main.py

# Schedule with cron (every hour)
crontab -e
# 0 * * * * /usr/bin/python3 /home/machismo/serverscraper/main.py >> /home/machismo/serverscraper/scraper.log 2>&1
```
