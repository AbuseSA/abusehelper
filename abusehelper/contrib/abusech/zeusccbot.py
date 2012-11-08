"""
abuse.ch Zeus C&C RSS feed bot.

Maintainer: Lari Huttunen <mit-code@huttu.net>
"""

import re
from abusehelper.core import bot, events
from abusehelper.contrib.rssbot.rssbot import RSSBot

from . import is_ip, resolve_level


class ZeusCcBot(RSSBot):
    feeds = bot.ListParam(default=["https://zeustracker.abuse.ch/rss.php"])
    # If treat_as_dns_source is set, the feed ip is dropped.
    treat_as_dns_source = bot.BoolParam()

    def create_event(self, **keys):
        event = events.Event()
        # handle link data
        link = keys.get("link", None)
        if link:
            event.add("description url", link)
        # handle title data
        title = keys.get("title", None)
        if title:
            t = []
            t = title.split()
            host = t[0]
            date = " ".join(t[1:])
            if is_ip(host):
                event.add("ip", host)
            else:
                event.add("host", host)
            br = re.compile('[()]')
            date = br.sub('', date)
            date = date + " UTC"
            event.add("source time", date)
        # handle description data
        description = keys.get("description", None)
        if description:
            for part in description.split(","):
                pair = part.split(":", 1)
                if len(pair) < 2:
                    continue
                key = pair[0].strip()
                value = pair[1].strip()
                if not key or not value:
                    continue
        # handle description data
        description = keys.get("description", None)
        if description:
            for part in description.split(","):
                pair = part.split(":", 1)
                if len(pair) < 2:
                    continue
                key = pair[0].strip()
                value = pair[1].strip()
                if not key or not value:
                    continue
                if key == "Status":
                    event.add(key.lower(), value)
                elif key == "level":
                    event.update("description", resolve_level(value))
                elif key == "SBL" and value != "Not listed":
                    key = key.lower() + " id"
                    event.add(key, value)
                elif key == "IP address":
                    if not self.treat_as_dns_source:
                        event.add("ip", value)
        event.add("feed", "abuse.ch")
        event.add("malware", "ZeuS")
        event.add("type", "c&c")
        return event

if __name__ == "__main__":
    ZeusCcBot.from_command_line().execute()
