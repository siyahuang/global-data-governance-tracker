"""Save Google News RSS search results as leads, never as published articles.

Google News RSS currently exposes an opaque Google link rather than the direct
publisher URL. A lead needs original-source verification before publication.
"""

import argparse
import json
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from collector import clean_text, parse_date, read_url
from config import BASE_DIR, COLLECTION_START_DATE
from media_index import classify_result, title_key
from storage import connect, initialize


SEARCHES = [
    ("en-US", "US", "US:en", "data protection authority"),
    ("en-US", "US", "US:en", "open government data"),
    ("en-US", "US", "US:en", "cross border data transfer"),
    ("en-US", "US", "US:en", "data governance regulation"),
    ("en-US", "US", "US:en", "AI data governance privacy"),
    ("zh-CN", "CN", "CN:zh-Hans", "公共数据 授权运营"),
    ("zh-CN", "CN", "CN:zh-Hans", "数据要素 数据产权"),
    ("zh-CN", "CN", "CN:zh-Hans", "个人信息保护 执法"),
    ("es-ES", "ES", "ES:es", "protección de datos autoridad"),
    ("fr-FR", "FR", "FR:fr", "protection des données personnelles autorité"),
    ("de-DE", "DE", "DE:de", "Datenschutz Behörde"),
    ("pt-BR", "BR", "BR:pt-419", "proteção de dados pessoais autoridade"),
    ("ja-JP", "JP", "JP:ja", "個人情報保護委員会 データ"),
    ("ko-KR", "KR", "KR:ko", "개인정보보호위원회 데이터"),
    ("ar", "SA", "SA:ar", "حماية البيانات الشخصية هيئة"),
    ("de-DE", "AT", "AT:de", "site:dsb.gv.at Datenschutz"),
    ("fr-FR", "BE", "BE:fr", "site:autoriteprotectiondonnees.be protection des données"),
    ("nl-BE", "BE", "BE:nl", "site:gegevensbeschermingsautoriteit.be persoonsgegevens"),
    ("bg-BG", "BG", "BG:bg", "site:cpdp.bg защита на личните данни"),
    ("hr-HR", "HR", "HR:hr", "site:azop.hr zaštita osobnih podataka"),
    ("el-GR", "CY", "CY:el", "site:dataprotection.gov.cy personal data protection"),
    ("cs-CZ", "CZ", "CZ:cs", "site:uoou.gov.cz ochrana osobních údajů"),
    ("da-DK", "DK", "DK:da", "site:datatilsynet.dk databeskyttelse"),
    ("et-EE", "EE", "EE:et", "site:aki.ee andmekaitse"),
    ("fi-FI", "FI", "FI:fi", "site:tietosuoja.fi tietosuoja"),
    ("fr-FR", "FR", "FR:fr", "site:cnil.fr protection des données"),
    ("de-DE", "DE", "DE:de", "site:bfdi.bund.de Datenschutz"),
    ("el-GR", "GR", "GR:el", "site:dpa.gr προστασία δεδομένων"),
    ("hu-HU", "HU", "HU:hu", "site:naih.hu adatvédelem"),
    ("en-IE", "IE", "IE:en", "site:dataprotection.ie data protection"),
    ("it-IT", "IT", "IT:it", "site:garanteprivacy.it protezione dei dati"),
    ("lv-LV", "LV", "LV:lv", "site:dvi.gov.lv datu aizsardzība"),
    ("lt-LT", "LT", "LT:lt", "site:vdai.lrv.lt asmens duomenys"),
    ("fr-FR", "LU", "LU:fr", "site:cnpd.lu protection des données"),
    ("en-MT", "MT", "MT:en", "site:idpc.org.mt data protection"),
    ("nl-NL", "NL", "NL:nl", "site:autoriteitpersoonsgegevens.nl persoonsgegevens"),
    ("pl-PL", "PL", "PL:pl", "site:uodo.gov.pl ochrona danych"),
    ("pt-PT", "PT", "PT:pt", "site:cnpd.pt proteção de dados"),
    ("ro-RO", "RO", "RO:ro", "site:dataprotection.ro protecția datelor"),
    ("sk-SK", "SK", "SK:sk", "site:dataprotection.gov.sk osobné údaje"),
    ("sl-SI", "SI", "SI:sl", "site:ip-rs.si osebni podatki"),
    ("es-ES", "ES", "ES:es", "site:aepd.es protección de datos"),
    ("sv-SE", "SE", "SE:sv", "site:imy.se personuppgifter"),
    ("en-GB", "GB", "GB:en", "site:ico.org.uk data protection"),
    ("no-NO", "NO", "NO:no", "site:datatilsynet.no personvern"),
    ("de-CH", "CH", "CH:de", "site:edoeb.admin.ch Datenschutz"),
]

CHINA_REGIONS = [
    "北京", "天津", "河北", "山西", "内蒙古", "辽宁", "吉林", "黑龙江", "上海",
    "江苏", "浙江", "安徽", "福建", "江西", "山东", "河南", "湖北", "湖南",
    "广东", "广西", "海南", "重庆", "四川", "贵州", "云南", "西藏", "陕西",
    "甘肃", "青海", "宁夏", "新疆", "香港", "澳门", "台湾",
]
SEARCHES.extend(("zh-CN", "CN", "CN:zh-Hans", f"{region} 数据局 公共数据 数据治理")
                for region in CHINA_REGIONS)

OUTPUT = BASE_DIR / "data" / "google-leads.json"


def collect(limit=500):
    initialize()
    cutoff = datetime.fromisoformat(COLLECTION_START_DATE).replace(
        tzinfo=ZoneInfo("Asia/Shanghai")).astimezone(timezone.utc)
    with connect() as db:
        seen = {title_key(row[0]) for row in db.execute(
            "SELECT title FROM articles UNION ALL SELECT title FROM media_index")}
    leads = []
    errors = []
    per_query_limit = max(10, limit // len(SEARCHES))
    for language, country, edition, query in SEARCHES:
        query_count = 0
        q = query + " after:" + COLLECTION_START_DATE
        url = "https://news.google.com/rss/search?" + urllib.parse.urlencode(
            {"q": q, "hl": language, "gl": country, "ceid": edition})
        try:
            root = ET.fromstring(read_url(url, "application/rss+xml, application/xml"))
        except Exception as exc:
            errors.append({"query": query, "error": f"{type(exc).__name__}: {str(exc)[:90]}"})
            continue
        for node in root.findall(".//item"):
            title = clean_text(node.findtext("title", ""))
            source_node = node.find("source")
            publisher = clean_text(source_node.text or "") if source_node is not None else ""
            if publisher and title.endswith(" - " + publisher):
                title = title[:-(len(publisher) + 3)].strip()
            published_at = parse_date(node.findtext("pubDate", ""))
            google_url = node.findtext("link", "")
            if not title or not published_at or not google_url:
                continue
            if datetime.fromisoformat(published_at) < cutoff or not classify_result(title, language.split("-")[0]):
                continue
            key = title_key(title)
            if key in seen:
                continue
            seen.add(key)
            leads.append({"title": title, "publisher": publisher, "publisher_home":
                          source_node.attrib.get("url", "") if source_node is not None else "",
                          "published_at": published_at, "google_url": google_url,
                          "query": query})
            query_count += 1
            if len(leads) >= limit or query_count >= per_query_limit:
                break
        print(f"Google News: {query}, cumulative {len(leads)}", flush=True)
        if len(leads) >= limit:
            break
    payload = {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "start_date": COLLECTION_START_DATE, "status": "leads_only",
               "note": "Verify the original publisher article URL and date before adding to the public database.",
               "items": leads, "errors": errors}
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"leads": len(leads), "errors": errors, "output": str(OUTPUT)}, ensure_ascii=False))
    return payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=500)
    args = parser.parse_args()
    collect(min(max(args.limit, 1), 500))
