from datetime import datetime
from pprint import pprint
import requests
from bs4 import BeautifulSoup


async def get_IP():
    ip = requests.get('https://api.ipify.org')
    return str(ip.text)


async def get_flag_status():
    today = datetime.today()
    today = today.replace(hour=0, minute=0, second=0, microsecond=0)
    # pprint(today)
    status = "Flag Status Not Available"
    response = requests.get("https://en.wikipedia.org/wiki/List_of_school_shootings_in_the_United_States_(2000%E2%80%93present)")
    soup = BeautifulSoup(response.text, features="lxml")
    table = soup.find("table", id="2020s")
    tr_table = table("tr")
    tr_table.reverse()
    i = 0
    for item in tr_table:
        if i == 1:
            break
        data = item.findAll("td")
        if not data:
            break
        date = data[0].text.rstrip()
        date = datetime.strptime(date, '%B %d, %Y')

        location = data[1].text.rstrip()
        dead = data[2].text.rstrip()
        injured = str(data[3].text).rstrip()
        total = str(data[4].text).rstrip()
        desc = str(data[5].text).rstrip()

        pprint(location)
        pprint(dead)
        pprint(injured)
        pprint(total)
        pprint(desc)
        pprint(today)
        pprint(date)
        calc = (today - date).days
        pprint(calc)
        if calc < 4:
            status = ("Flag Status: Lower Flag\r\nDate: {}\r\bLocation: {}\r\nDead: {}\r\nInjured: {}\r\nTotal: {}\r\nDesc: {}"
                      .format(date, location, dead, injured, total, desc))
        else:
            status = ("Flag Status: Raise Flag\r\nDays Since: {}".format(calc))
            i += 1
        break
    return status


async def get_host_statuses():
    pprint("hosts")
    hosts = "No Hosts Found"
    return hosts


async def get_service_statuses():
    pprint("hosts")
    hosts = "No Services Found"
    return hosts