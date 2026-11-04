"""Flag Status monitor feature based on customizable Wikipedia articles and incident trigger rules."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional
from bs4 import BeautifulSoup
import aiohttp

from home_notifications.features.base import BaseFeature

logger = logging.getLogger(__name__)

DEFAULT_FLAG_SOURCES = [
    {
        "id": "school_shootings_2020s",
        "name": "US School Shootings (2020s)",
        "url": "https://en.wikipedia.org/wiki/List_of_school_shootings_in_the_United_States_(2020s)",
        "enabled": True,
    },
    {
        "id": "school_shootings_2000s",
        "name": "US School Shootings (2000–present)",
        "url": "https://en.wikipedia.org/wiki/List_of_school_shootings_in_the_United_States_(2000%E2%80%93present)",
        "enabled": True,
    },
]


def parse_date_string(date_raw: str) -> Optional[datetime]:
    """Parse various date formats from Wikipedia tables."""
    cleaned = re.sub(r"\[.*?\]", "", date_raw).replace("\xa0", " ").strip()
    if not cleaned:
        return None

    # Handle date ranges like "October 24–25, 2026" or "October 30 – November 1, 2026"
    range_match = re.match(
        r"([A-Za-z]+)\s+\d+\s*[–—\-]\s*([A-Za-z]+)?\s*(\d+),\s*(\d{4})", cleaned
    )
    if range_match:
        m1, m2, d2, y = range_match.groups()
        month = m2 if m2 else m1
        cleaned = f"{month} {d2}, {y}"

    formats = [
        "%B %d, %Y",
        "%b %d, %Y",
        "%Y-%m-%d",
        "%d %B %Y",
        "%d %b %Y",
        "%m/%d/%Y",
        "%B %d %Y",
        "%b %d %Y",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(cleaned, fmt)
        except ValueError:
            pass

    # Regex search for Month Day, Year if there is extra text around it
    m = re.search(r"([A-Z][a-z]+)\s+(\d{1,2}),\s+(\d{4})", cleaned)
    if m:
        for fmt in ("%B %d, %Y", "%b %d, %Y"):
            try:
                return datetime.strptime(m.group(0), fmt)
            except ValueError:
                pass

    return None


def parse_int_count(val_str: Any) -> int:
    """Extract integer count from a table cell, ignoring footnote brackets and text."""
    cleaned = re.sub(r"\[.*?\]", "", str(val_str)).strip()
    if not cleaned or cleaned.lower() in ("none", "n/a", "-", "—"):
        return 0
    digits = re.findall(r"\d+", cleaned)
    if digits:
        return int(digits[0])
    return 0


def extract_incidents_from_soup(
    soup: BeautifulSoup,
    source_name: str,
    source_url: str,
    today: Optional[datetime] = None,
) -> List[dict]:
    """Dynamically detects table headers and extracts incident rows from Wikipedia tables."""
    if today is None:
        today = datetime.today().replace(hour=0, minute=0, second=0, microsecond=0)

    incidents: List[dict] = []
    tables = soup.find_all("table", {"class": "wikitable"})
    if not tables:
        return incidents

    for table in reversed(tables):
        rows = table.find_all("tr")
        if not rows:
            continue

        col_map: Dict[str, int] = {}
        header_row_idx = -1

        # Check the first few rows for header labels
        for idx, row in enumerate(rows[:4]):
            ths = row.find_all(["th", "td"])
            header_texts = [
                re.sub(r"\[.*?\]", "", th.get_text()).replace("\xa0", " ").strip().lower()
                for th in ths
            ]
            has_date = any("date" in h or "day" in h for h in header_texts)
            has_dead = any(
                "dead" in h or "death" in h or "fatal" in h or "kill" in h for h in header_texts
            )
            if has_date or has_dead:
                header_row_idx = idx
                for col_idx, h in enumerate(header_texts):
                    if ("date" in h or "day" in h) and "date" not in col_map:
                        col_map["date"] = col_idx
                    elif ("city" in h) and "city" not in col_map:
                        col_map["city"] = col_idx
                    elif ("state" in h) and "state" not in col_map:
                        col_map["state"] = col_idx
                    elif (
                        "location" in h or "place" in h or "where" in h or "area" in h
                    ) and "location" not in col_map:
                        col_map["location"] = col_idx
                    elif (
                        "dead" in h or "death" in h or "fatal" in h or "kill" in h
                    ) and "dead" not in col_map:
                        col_map["dead"] = col_idx
                    elif ("injur" in h or "wound" in h) and "injured" not in col_map:
                        col_map["injured"] = col_idx
                    elif (
                        "total" in h or "casualt" in h or "victim" in h
                    ) and "total" not in col_map:
                        col_map["total"] = col_idx
                    elif (
                        "desc" in h
                        or "incident" in h
                        or "summary" in h
                        or "note" in h
                        or "detail" in h
                        or "circumstance" in h
                    ) and "desc" not in col_map:
                        col_map["desc"] = col_idx
                break

        # Positional fallback if no date column matched
        if "date" not in col_map:
            col_map = {
                "date": 0,
                "location": 1,
                "dead": 2,
                "injured": 3,
                "total": 4,
                "desc": 5,
            }

        data_rows = rows[header_row_idx + 1 :] if header_row_idx >= 0 else rows
        for row in reversed(data_rows):
            tds = row.find_all("td")
            if not tds or len(tds) < 3:
                continue

            def get_cell(idx_key: str, default: str = "") -> str:
                col_i = col_map.get(idx_key)
                if col_i is not None and col_i < len(tds):
                    return (
                        re.sub(r"\[.*?\]", "", tds[col_i].get_text())
                        .replace("\xa0", " ")
                        .strip()
                    )
                return default

            date_raw = get_cell("date")
            dt = parse_date_string(date_raw)
            if not dt:
                continue

            loc = get_cell("location")
            if not loc:
                city = get_cell("city")
                state = get_cell("state")
                loc = f"{city}, {state}".strip(", ") if (city or state) else "Unknown"

            dead_raw = get_cell("dead", "0")
            dead_count = parse_int_count(dead_raw)

            injured_raw = get_cell("injured", "0")
            injured_count = parse_int_count(injured_raw)

            total_raw = get_cell("total", "")
            total_count = (
                parse_int_count(total_raw) if total_raw else (dead_count + injured_count)
            )

            desc = get_cell("desc")
            days_ago = (today - dt).days

            incidents.append(
                {
                    "source_name": source_name,
                    "source_url": source_url,
                    "date": dt.strftime("%B %d, %Y"),
                    "date_iso": dt.strftime("%Y-%m-%d"),
                    "days_ago": days_ago,
                    "location": loc,
                    "dead": dead_count,
                    "dead_str": dead_raw,
                    "injured": injured_count,
                    "injured_str": injured_raw,
                    "total": total_count,
                    "desc": desc,
                }
            )

    return incidents


class FlagStatusFeature(BaseFeature):
    """Monitors configurable Wikipedia articles and incident rules to determine half-staff flag status."""

    def __init__(self, config, state, notifier):
        super().__init__("flag_status", config, state, notifier)

    def get_sources(self) -> List[dict]:
        """Retrieve configured Wikipedia sources."""
        sources = self.feature_config.get("sources")
        if isinstance(sources, str):
            try:
                sources = json.loads(sources)
            except Exception:
                sources = DEFAULT_FLAG_SOURCES
        if not sources or not isinstance(sources, list):
            sources = DEFAULT_FLAG_SOURCES
        return sources

    def get_rules(self) -> Dict[str, Any]:
        """Retrieve configured threshold and filter rules."""
        try:
            duration_days = int(self.feature_config.get("duration_days", 4))
        except (ValueError, TypeError):
            duration_days = 4

        try:
            min_deaths = int(self.feature_config.get("min_deaths", 1))
        except (ValueError, TypeError):
            min_deaths = 1

        try:
            min_casualties = int(self.feature_config.get("min_casualties", 1))
        except (ValueError, TypeError):
            min_casualties = 1

        state_filter = str(self.feature_config.get("state_filter", "")).strip()

        return {
            "duration_days": duration_days,
            "min_deaths": min_deaths,
            "min_casualties": min_casualties,
            "state_filter": state_filter,
        }

    @staticmethod
    async def test_url(url: str) -> dict:
        """Probe an arbitrary Wikipedia article URL and extract sample incidents."""
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 HomeNotifications/2.0"
        }
        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(
                    url, timeout=aiohttp.ClientTimeout(total=12.0)
                ) as resp:
                    if resp.status != 200:
                        return {
                            "success": False,
                            "url": url,
                            "error": f"HTTP response status {resp.status}",
                            "tables_found": 0,
                            "sample_incidents": [],
                        }
                    html = await resp.text()
                    soup = BeautifulSoup(html, "lxml")
                    tables = soup.find_all("table", {"class": "wikitable"})
                    today = datetime.today().replace(hour=0, minute=0, second=0, microsecond=0)
                    incidents = extract_incidents_from_soup(
                        soup, source_name="Test Source", source_url=url, today=today
                    )
                    return {
                        "success": True,
                        "url": url,
                        "tables_found": len(tables),
                        "total_incidents_parsed": len(incidents),
                        "sample_incidents": incidents[:10],
                        "message": (
                            f"Successfully parsed {len(incidents)} incident(s) across "
                            f"{len(tables)} table(s)."
                        ),
                    }
        except Exception as e:
            logger.debug("Failed testing URL %s: %s", url, e)
            return {
                "success": False,
                "url": url,
                "error": str(e),
                "tables_found": 0,
                "sample_incidents": [],
            }

    @classmethod
    async def fetch_flag_details(
        cls,
        sources: Optional[List[dict]] = None,
        duration_days: int = 4,
        min_deaths: int = 1,
        min_casualties: int = 1,
        state_filter: str = "",
    ) -> dict:
        """Fetch and evaluate flag status across all enabled sources."""
        if sources is None:
            sources = DEFAULT_FLAG_SOURCES

        enabled_sources = [s for s in sources if s.get("enabled", True)]
        if not enabled_sources:
            return {
                "status_text": "Flag Status: Raise Flag\nNo enabled sources configured.",
                "status_type": "RAISE",
                "active_incident": None,
                "recent_incidents": [],
            }

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 HomeNotifications/2.0"
        }
        today = datetime.today().replace(hour=0, minute=0, second=0, microsecond=0)
        all_incidents: List[dict] = []

        async with aiohttp.ClientSession(headers=headers) as session:
            for src in enabled_sources:
                url = src.get("url", "")
                name = src.get("name", "Wikipedia")
                if not url:
                    continue
                try:
                    async with session.get(
                        url, timeout=aiohttp.ClientTimeout(total=10.0)
                    ) as resp:
                        if resp.status != 200:
                            continue
                        html = await resp.text()
                        soup = BeautifulSoup(html, "lxml")
                        extracted = extract_incidents_from_soup(
                            soup, source_name=name, source_url=url, today=today
                        )
                        all_incidents.extend(extracted)
                except Exception as e:
                    logger.debug("Failed fetching flag status from %s: %s", url, e)

        if not all_incidents:
            return {
                "status_text": "Flag Status Not Available",
                "status_type": "UNKNOWN",
                "active_incident": None,
                "recent_incidents": [],
            }

        # Deduplicate incidents by (date_iso, location, dead, injured)
        seen = set()
        deduped = []
        for inc in all_incidents:
            key = (inc["date_iso"], inc["location"].lower(), inc["dead"], inc["injured"])
            if key not in seen:
                seen.add(key)
                deduped.append(inc)

        # Sort incidents: most recent (lowest days_ago) first
        deduped.sort(key=lambda x: (x["days_ago"], -x["dead"]))

        # Filter states if configured
        state_list = [s.strip().lower() for s in state_filter.split(",") if s.strip()]

        active_incident: Optional[dict] = None
        for inc in deduped:
            if state_list:
                loc_lower = inc["location"].lower()
                if not any(st in loc_lower for st in state_list):
                    continue

            # Check if within half-staff duration window and casualty threshold
            if (
                0 <= inc["days_ago"] < duration_days
                and (inc["dead"] >= min_deaths or inc["total"] >= min_casualties)
            ):
                active_incident = inc
                break

        if active_incident:
            status_type = "LOWER"
            status_text = (
                f"Flag Status: Lower Flag\n"
                f"Date: {active_incident['date']}\n"
                f"Location: {active_incident['location']}\n"
                f"Dead: {active_incident['dead']}\n"
                f"Injured: {active_incident['injured']}\n"
                f"Total: {active_incident['total']}\n"
                f"Desc: {active_incident['desc']}"
            )
        else:
            status_type = "RAISE"
            days_since = deduped[0]["days_ago"] if deduped else "N/A"
            status_text = f"Flag Status: Raise Flag\nDays Since Last Incident: {days_since}"

        return {
            "status_text": status_text,
            "status_type": status_type,
            "active_incident": active_incident,
            "recent_incidents": deduped[:25],
        }

    @classmethod
    async def fetch_flag_status(
        cls,
        instance_or_sources: Any = None,
        duration_days: int = 4,
        min_deaths: int = 1,
        min_casualties: int = 1,
        state_filter: str = "",
    ) -> str:
        """Fetch flag status text for backward-compatible bot and function calls."""
        if isinstance(instance_or_sources, FlagStatusFeature):
            sources = instance_or_sources.get_sources()
            rules = instance_or_sources.get_rules()
            res = await cls.fetch_flag_details(
                sources=sources,
                duration_days=rules["duration_days"],
                min_deaths=rules["min_deaths"],
                min_casualties=rules["min_casualties"],
                state_filter=rules["state_filter"],
            )
            return res["status_text"]
        elif isinstance(instance_or_sources, list):
            sources = instance_or_sources
        else:
            sources = DEFAULT_FLAG_SOURCES

        res = await cls.fetch_flag_details(
            sources=sources,
            duration_days=duration_days,
            min_deaths=min_deaths,
            min_casualties=min_casualties,
            state_filter=state_filter,
        )
        return res["status_text"]

    async def execute(self, force: bool = False) -> str:
        if not self.is_enabled and not force:
            return "Flag status check disabled"

        try:
            sources = self.get_sources()
            rules = self.get_rules()
            res = await self.fetch_flag_details(
                sources=sources,
                duration_days=rules["duration_days"],
                min_deaths=rules["min_deaths"],
                min_casualties=rules["min_casualties"],
                state_filter=rules["state_filter"],
            )

            status_text = res["status_text"]
            status_type = res["status_type"]
            active_inc = res["active_incident"]
            recent_incs = res["recent_incidents"]

            old_status = self.state.get_last_flag_status()
            changed = self.state.update_flag_status(
                status=status_text,
                status_type=status_type,
                active_incident=active_inc,
                recent_incidents=recent_incs,
            )
            await self.state.save()

            notify_mode = self.feature_config.notify_mode

            if changed and old_status is not None:
                if status_type == "LOWER" and active_inc:
                    msg = (
                        f"🚩 <b>Half-Staff Flag Alert: Lower Flags</b>\n\n"
                        f"📅 <b>Date:</b> {active_inc['date']}\n"
                        f"📍 <b>Location:</b> {active_inc['location']}\n"
                        f"💀 <b>Fatalities:</b> {active_inc['dead']} | <b>Injured:</b> {active_inc['injured']}\n"
                        f"📝 <b>Details:</b> {active_inc['desc']}\n"
                        f"🔗 <b>Source:</b> <a href=\"{active_inc['source_url']}\">{active_inc['source_name']}</a>"
                    )
                    level = "WARNING"
                else:
                    msg = (
                        f"🏳️ <b>Flag Status: Full-Staff (Raise Flags)</b>\n\n"
                        f"{status_text}"
                    )
                    level = "SUCCESS"

                await self.notifier.notify(
                    category=self.name,
                    title="Flag Status Alert",
                    message=msg,
                    level=level,
                )
            elif notify_mode == "periodic":
                await self.notifier.notify(
                    category=self.name,
                    title="Flag Status Report",
                    message=f"<pre>{status_text}</pre>",
                    level="INFO",
                )

            return status_text
        except Exception as e:
            logger.error("Error checking flag status: %s", e)
            return f"Error checking flag status: {e}"
