"""Collect a separate, source-linked media index from public news RSS search.

This index is intentionally separate from the interpreted daily brief: a news
search result is a report, not necessarily an independent policy event.
"""

import hashlib
import argparse
import json
import time
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from collector import classify, clean_text, normalize_url, parse_date, read_url
from config import COLLECTION_START_DATE
from geography import infer_province
from storage import connect, initialize, utc_now

ENGLISH_SEARCHES = [
    "open government data", "open data policy", "public data reuse",
    "data protection authority", "privacy regulator", "privacy law 2026",
    "data privacy legislation", "personal data protection", "GDPR enforcement",
    "cross border data transfer", "data sovereignty regulation", "data localization law",
    "government data sharing", "data access law", "data portability regulation",
    "AI data governance", "AI data protection", "European Data Act",
    "data space regulation", "privacy enforcement", "data protection fine",
    "public sector data governance", "data breach investigation",
    "site:dataguidance.com/news data protection",
    "site:dataguidance.com/news data transfer",
    "site:digitalpolicyalert.org data privacy regulation",
    "site:digitalpolicyalert.org cross-border data",
    "site:iapp.org/news privacy regulation",
    "2026年9月 公共数据开放", "2026年9月 公共数据授权运营",
    "2026年9月 数据要素", "2026年9月 数据产权",
    "2026年9月 数据跨境", "2026年9月 个人信息保护",
    "2026年9月 可信数据空间", "2026年9月 数据安全",
    "2026年9月 高质量数据集", "2026年9月 数据治理政策",
]

# Country-scoped queries keep Europe from collapsing into a single EU feed.
# Results still pass the same relevance filter and retain their publisher URL.
EU_COUNTRY_SEARCHES = [
    "Austria data protection authority GDPR", "Belgium data protection authority GDPR",
    "Bulgaria personal data protection commission", "Croatia data protection authority",
    "Cyprus commissioner personal data protection", "Czechia data protection authority",
    "Denmark Datatilsynet data protection", "Estonia data protection inspectorate",
    "Finland data protection ombudsman", "France CNIL data protection",
    "Germany BfDI Datenschutz data protection", "Greece Hellenic data protection authority",
    "Hungary NAIH data protection authority", "Ireland Data Protection Commission",
    "Italy Garante privacy data protection", "Latvia data state inspectorate privacy",
    "Lithuania State Data Protection Inspectorate", "Luxembourg CNPD data protection",
    "Malta Information and Data Protection Commissioner", "Netherlands Autoriteit Persoonsgegevens",
    "Poland UODO personal data protection", "Portugal CNPD data protection",
    "Romania data protection authority GDPR", "Slovakia data protection authority",
    "Slovenia Information Commissioner data protection", "Spain AEPD data protection",
    "Sweden IMY privacy data protection", "United Kingdom ICO data protection",
    "Norway Datatilsynet privacy", "Switzerland FDPIC data protection",
]

# Search terms use the language people use to publish local policy updates.
# Locale is passed to Bing News RSS; the original publisher URL is retained.
LOCAL_SEARCHES = {
    "zh": ("en-US", ["公共数据开放", "公共数据授权运营", "数据要素 政策", "数据跨境流动", "个人信息保护 执法", "数据安全 监管", "可信数据空间", "数据治理 地方政策", "site:cac.gov.cn 个人信息保护 数据安全",
                     "天津 公共数据", "河北 公共数据", "山西 公共数据", "辽宁 公共数据", "吉林 公共数据", "黑龙江 公共数据", "江西 公共数据", "广西 公共数据", "四川 公共数据", "云南 公共数据", "西藏 公共数据", "青海 公共数据", "香港 个人资料保护", "澳门 个人资料保护", "台湾 開放資料"]),
    "es": ("es-ES", ["protección de datos autoridad", "datos abiertos gobierno", "transferencia internacional de datos", "gobernanza de datos", "ley de datos personales"]),
    "fr": ("fr-FR", ["protection des données personnelles", "données ouvertes gouvernement", "transfert international de données", "gouvernance des données", "autorité de protection des données"]),
    "de": ("de-DE", ["Datenschutz Behörde", "offene Verwaltungsdaten", "grenzüberschreitende Datenübermittlung", "Datenschutz Gesetz", "Datenräume Regulierung"]),
    "pt": ("pt-BR", ["proteção de dados pessoais", "dados abertos governo", "transferência internacional de dados", "governança de dados", "autoridade nacional proteção de dados"]),
    "ja": ("ja-JP", ["個人情報保護委員会", "オープンデータ 政府", "データガバナンス 政策", "個人情報 越境移転", "データ利活用 政策"]),
    "ko": ("ko-KR", ["개인정보보호위원회", "공공데이터 개방", "데이터 거버넌스 정책", "개인정보 국외 이전", "데이터 보호 법률"]),
    "ar": ("ar-SA", ["حماية البيانات الشخصية", "البيانات الحكومية المفتوحة", "نقل البيانات عبر الحدود", "حوكمة البيانات", "قانون حماية البيانات"]),
}

LANGUAGE_CATEGORIES = {
    "es": {"privacy": ("protección de datos", "datos personales"), "scope": ("datos abiertos",), "crossborder": ("transferencia internacional de datos",), "law": ("ley de datos",), "service": ("gobernanza de datos",)},
    "fr": {"privacy": ("protection des données", "données personnelles"), "scope": ("données ouvertes",), "crossborder": ("transfert international de données",), "service": ("gouvernance des données",)},
    "de": {"privacy": ("datenschutz",), "scope": ("offene verwaltungsdaten",), "crossborder": ("datenübermittlung",), "dataspace": ("datenräume",)},
    "pt": {"privacy": ("proteção de dados", "dados pessoais"), "scope": ("dados abertos",), "crossborder": ("transferência internacional de dados",), "service": ("governança de dados",)},
    "ja": {"privacy": ("個人情報保護", "個人情報"), "scope": ("オープンデータ",), "crossborder": ("越境移転",), "service": ("データガバナンス", "データ利活用")},
    "ko": {"privacy": ("개인정보보호", "개인정보"), "scope": ("공공데이터 개방",), "crossborder": ("국외 이전",), "service": ("데이터 거버넌스",)},
    "ar": {"privacy": ("حماية البيانات", "البيانات الشخصية"), "scope": ("البيانات الحكومية المفتوحة",), "crossborder": ("نقل البيانات",), "service": ("حوكمة البيانات",)},
}


def search_plan(languages):
    if languages == "all":
        selected = ["en", *LOCAL_SEARCHES]
    else:
        selected = [part.strip() for part in languages.split(",")]
    invalid = set(selected) - {"en", *LOCAL_SEARCHES}
    if invalid:
        raise ValueError("Unsupported languages: " + ", ".join(sorted(invalid)))
    plan = []
    if "en" in selected:
        plan.extend(("en", "en-US", query) for query in ENGLISH_SEARCHES)
        plan.extend(("en", "en-US", query) for query in EU_COUNTRY_SEARCHES)
    for language in selected:
        if language in LOCAL_SEARCHES:
            market, queries = LOCAL_SEARCHES[language]
            plan.extend((language, market, query) for query in queries)
    return plan


def classify_result(title, language):
    if language in ("en", "zh"):
        result = classify(title, "")
        if result:
            return result
    lower = title.casefold()
    for category, terms in LANGUAGE_CATEGORIES.get(language, {}).items():
        if any(term.casefold() in lower for term in terms):
            return category, 65, "标题议题词"
    return classify(title, "")


def title_key(title):
    return "".join(char for char in title.casefold() if char.isalnum())


def is_china_publisher(url, language):
    host = urllib.parse.urlsplit(url).netloc.lower().removeprefix("www.")
    chinese_hosts = ("sohu.com", "qq.com", "people.com.cn", "chinadaily.com.cn",
                     "thepaper.cn", "163.com", "ifeng.com", "xinhuanet.com",
                     "chinanews.com", "eastmoney.com")
    return (language == "zh" or host.endswith(".cn") or any(
        host == known or host.endswith("." + known) for known in chinese_hosts))


def publisher_country(url, language):
    if is_china_publisher(url, language):
        return "中国"
    host = urllib.parse.urlsplit(url).netloc.lower().removeprefix("www.")
    known_publishers = {
        "fnnews.com": "韩国", "boannews.com": "韩国", "newstomato.com": "韩国",
        "meconomynews.com": "韩国", "newsis.com": "韩国", "ajunews.com": "韩国",
        "bloter.net": "韩国", "smartbizn.com": "韩国", "daum.net": "韩国",
        "journaldunet.com": "法国", "village-justice.com": "法国",
        "irishtimes.com": "爱尔兰", "thestar.com.my": "马来西亚",
        "spa.gov.sa": "沙特阿拉伯", "livelaw.in": "印度",
        "note.com": "日本", "techrepublic.com": "美国", "forbes.com": "美国",
        "iapp.org": "美国", "techtarget.com": "美国", "law.com": "美国",
        "kcur.org": "美国", "jurist.org": "美国", "consumerreports.org": "美国",
        "darkreading.com": "美国", "thebaynet.com": "美国", "statescoop.com": "美国",
        "eweek.com": "美国", "dbta.com": "美国", "fedscoop.com": "美国",
        "cryptobriefing.com": "美国", "ijr.com": "美国", "hitconsultant.net": "美国",
        "pinsentmasons.com": "英国", "iflr.com": "英国", "phoneworld.com.pk": "巴基斯坦",
        "opensourceforu.com": "印度", "togofirst.com": "多哥", "vetogate.com": "埃及",
        "elbalad.news": "埃及", "dostor.org": "埃及", "negocios.com": "西班牙",
        "elespanol.com": "西班牙", "cincodias.elpais.com": "西班牙", "latercera.cl": "智利",
        "lasillavacia.com": "哥伦比亚", "valor.globo.com": "巴西", "foz.portaldacidade.com": "巴西",
        "kpenews.com": "韩国", "mc-doualiya.com": "法国", "cybernews.com": "立陶宛",
        "veronoticias.com": "墨西哥", "aip.ci": "科特迪瓦",
        "newspim.com": "韩国", "yna.co.kr": "韩国",
    }
    for known, country in known_publishers.items():
        if host == known or host.endswith("." + known):
            return country
    for suffix, name in ((".kr", "韩国"), (".jp", "日本"), (".de", "德国"),
                         (".fr", "法国"), (".es", "西班牙"), (".br", "巴西"),
                         (".pt", "葡萄牙"), (".mx", "墨西哥"), (".cl", "智利"),
                         (".ar", "阿根廷"), (".co", "哥伦比亚"), (".uk", "英国"),
                         (".ca", "加拿大"), (".au", "澳大利亚"), (".ph", "菲律宾"),
                         (".it", "意大利"), (".nl", "荷兰"), (".at", "奥地利"),
                         (".be", "比利时"), (".bg", "保加利亚"), (".hr", "克罗地亚"),
                         (".cy", "塞浦路斯"), (".cz", "捷克"), (".dk", "丹麦"),
                         (".ee", "爱沙尼亚"), (".fi", "芬兰"), (".gr", "希腊"),
                         (".hu", "匈牙利"), (".ie", "爱尔兰"), (".lv", "拉脱维亚"),
                         (".lt", "立陶宛"), (".lu", "卢森堡"), (".mt", "马耳他"),
                         (".pl", "波兰"), (".ro", "罗马尼亚"), (".sk", "斯洛伐克"),
                         (".si", "斯洛文尼亚"), (".se", "瑞典"), (".no", "挪威"),
                         (".ch", "瑞士"), (".eu", "欧盟")):
        if host.endswith(suffix):
            return name
    return ""


def original_link(bing_url):
    query = urllib.parse.parse_qs(urllib.parse.urlsplit(bing_url).query)
    candidates = query.get("url", [])
    return normalize_url(candidates[0]) if candidates else ""


def feed_items(content):
    root = ET.fromstring(content)
    for node in root.findall(".//item"):
        title = clean_text(node.findtext("title", ""))
        bing_url = node.findtext("link", "")
        url = original_link(bing_url)
        published = parse_date(node.findtext("pubDate", ""))
        publisher = clean_text(node.findtext("source", "")) or urllib.parse.urlsplit(url).netloc
        if publisher and title.endswith(" - " + publisher):
            title = title[:-(len(publisher) + 3)].strip()
        if title and url and published:
            yield {"title": title, "url": url, "published_at": published,
                   "publisher": publisher[:120]}


def repair_locations():
    """Fill only locations determinable from a known publisher domain."""
    initialize()
    updated = 0
    with connect() as db:
        rows = db.execute("""SELECT id,title,title_zh,url,language,country,province,scope
            FROM media_index WHERE status='published'
            AND (country='' OR (scope='china' AND province=''))""").fetchall()
        for row in rows:
            country = row[5] or publisher_country(row[3], row[4])
            if not country:
                continue
            scope = "china" if country == "中国" else "international"
            province = (row[6] or infer_province(row[2] or row[1], "", {"country": country})) if scope == "china" else ""
            updated += db.execute("""UPDATE media_index SET country=?,scope=?,province=?
                WHERE id=? AND (country='' OR (scope='china' AND province=''))""",
                (country, scope, province, row[0])).rowcount
    return {"updated": updated}


def collect(backfill=False, languages="all"):
    initialize()
    cutoff = datetime.fromisoformat(COLLECTION_START_DATE).replace(
        tzinfo=ZoneInfo("Asia/Shanghai")).astimezone(timezone.utc)
    pages = (1, 11, 21) if backfill else (1,)
    added = checked = 0
    errors = []
    with connect() as db:
        seen_titles = {title_key(row[0]) for row in db.execute("SELECT title FROM media_index")}
    plan = search_plan(languages)
    by_language = {}
    for index, (language, market, query) in enumerate(plan, 1):
        query_added = 0
        for first in pages:
            params = urllib.parse.urlencode({"q": query, "format": "rss", "first": first, "mkt": market})
            url = "https://www.bing.com/news/search?" + params
            try:
                entries = list(feed_items(read_url(url, "application/rss+xml, application/xml")))
            except Exception as exc:
                errors.append(f"{query} / {first}: {type(exc).__name__}: {str(exc)[:90]}")
                continue
            checked += len(entries)
            if not entries:
                break
            with connect() as db:
                for item in entries:
                    if datetime.fromisoformat(item["published_at"]) < cutoff:
                        continue
                    category = classify_result(item["title"], language)
                    if not category:
                        continue
                    key = title_key(item["title"])
                    if not key or key in seen_titles:
                        continue
                    item_id = hashlib.sha256(item["url"].encode()).hexdigest()[:24]
                    scope = "china" if is_china_publisher(item["url"], language) else "international"
                    province = infer_province(item["title"], "", {"country": "中国"}) if scope == "china" else ""
                    country = publisher_country(item["url"], language)
                    cursor = db.execute("""INSERT OR IGNORE INTO media_index
                        (id,title,url,publisher,published_at,category_id,language,scope,province,country,collected_at)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                        (item_id, item["title"], item["url"], item["publisher"],
                         item["published_at"], category[0], language, scope, province, country, utc_now()))
                    if cursor.rowcount:
                        added += 1
                        query_added += 1
                        by_language[language] = by_language.get(language, 0) + 1
                        seen_titles.add(key)
            time.sleep(0.25)
        print(f"{index}/{len(plan)} [{language}] {query}: +{query_added}", flush=True)
    result = {"added": added, "checked": checked, "by_language": by_language, "errors": errors}
    print(json.dumps(result, ensure_ascii=False), flush=True)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--backfill", action="store_true")
    parser.add_argument("--repair-locations", action="store_true")
    parser.add_argument("--languages", default="all")
    args = parser.parse_args()
    if args.repair_locations:
        print(json.dumps(repair_locations(), ensure_ascii=False))
    else:
        collect(args.backfill, args.languages)
