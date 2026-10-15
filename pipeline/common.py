"""Setari comune pentru pipeline-ul zilnic."""
import os, datetime, zoneinfo

HERE = os.path.dirname(os.path.abspath(__file__))
TODAY = os.environ.get('TODAY') or datetime.datetime.now(zoneinfo.ZoneInfo('Europe/Bucharest')).date().isoformat()
TTL_DAYS = int(os.environ.get('MARKET_TTL_DAYS', '7'))  # cat de des se reimprospateaza anunturile de pe storia.ro
