"""Editorial taxonomy and public feeds for the data governance monitor."""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("DATA_DIR", str(BASE_DIR / "data"))).expanduser().resolve()
DB_PATH = DATA_DIR / "news.sqlite3"
COLLECTION_START_DATE = "2026-09-01"

# These names follow the headings in the August 2026 DMG monthly report.
SECTIONS = [
    {"id": "open", "name": "数据开放国际动态", "categories": [
        {"id": "law", "name": "数据开放法制建设"},
        {"id": "plan", "name": "数据开放行动计划"},
        {"id": "scope", "name": "数据开放内容范围"},
        {"id": "platform", "name": "数据开放平台建设"},
        {"id": "service", "name": "数据开放服务体系"},
        {"id": "activity", "name": "数据开放促进活动"},
        {"id": "outcome", "name": "数据开放利用成果"},
        {"id": "international", "name": "国际组织及其他机构的数据开放活动"},
    ]},
    {"id": "related", "name": "与数据开放相关的其他举措", "categories": [
        {"id": "dataspace", "name": "数据空间"},
        {"id": "intermediary", "name": "数据中介"},
        {"id": "commons", "name": "数据公地"},
        {"id": "crossborder", "name": "数据跨境流动"},
        {"id": "privacy", "name": "隐私与个人信息保护"},
        {"id": "ai", "name": "人工智能"},
    ]},
]

# Tested as public RSS/Atom endpoints on 2026-09-26. Source regions describe
# the publisher, not necessarily the place discussed in an individual story.
SOURCES = [
    {"id": "eu-data-portal", "name": "欧洲数据门户", "region": "欧洲", "country": "欧盟", "kind": "公开网页", "url": "https://data.europa.eu/en/news-events/news"},
    {"id": "eu-digital", "name": "欧盟数字战略", "region": "欧洲", "country": "欧盟", "kind": "RSS", "url": "https://digital-strategy.ec.europa.eu/en/rss.xml"},
    {"id": "korea-pipc", "name": "韩国个人信息保护委员会", "region": "亚洲", "country": "韩国", "kind": "公开网页", "url": "https://pipc.go.kr/eng/user/ltn/new/noticeList.do?pageIndex=1"},
    {"id": "australia-oaic", "name": "澳大利亚信息专员办公室", "region": "大洋洲", "country": "澳大利亚", "kind": "公开网页", "url": "https://www.oaic.gov.au/news/media-centre"},
    {"id": "us-ftc", "name": "美国联邦贸易委员会", "region": "北美洲", "country": "美国", "kind": "RSS", "url": "https://www.ftc.gov/feeds/press-release.xml"},
    {"id": "uk-open", "name": "英国政府·开放数据", "region": "欧洲", "country": "英国", "kind": "Atom", "url": "https://www.gov.uk/search/news-and-communications.atom?keywords=open+data"},
    {"id": "uk-sharing", "name": "英国政府·数据共享", "region": "欧洲", "country": "英国", "kind": "Atom", "url": "https://www.gov.uk/search/news-and-communications.atom?keywords=data+sharing"},
    {"id": "ogp", "name": "开放政府伙伴关系", "region": "国际组织", "country": "国际组织", "kind": "RSS", "url": "https://www.opengovpartnership.org/feed/"},
    {"id": "cnil", "name": "法国 CNIL", "region": "欧洲", "country": "法国", "kind": "RSS", "url": "https://www.cnil.fr/en/rss.xml"},
    {"id": "italy-garante", "name": "意大利个人数据保护局", "region": "欧洲", "country": "意大利", "kind": "公开网页", "url": "https://www.garanteprivacy.it/it/home/stampa-comunicazione/newsletter"},
    {"id": "sweden-imy", "name": "瑞典隐私保护局", "region": "欧洲", "country": "瑞典", "kind": "公开网页", "url": "https://www.imy.se/en/news/"},
    {"id": "privacy-international", "name": "Privacy International", "region": "国际组织", "country": "国际组织", "kind": "RSS", "url": "https://www.privacyinternational.org/rss.xml"},
    {"id": "edpb-news", "name": "欧洲数据保护委员会资讯", "region": "欧洲", "country": "欧盟", "kind": "RSS", "url": "https://www.edpb.europa.eu/feed/news_en"},
    {"id": "canada-opc", "name": "加拿大隐私专员办公室", "region": "北美洲", "country": "加拿大", "kind": "RSS", "url": "https://www.priv.gc.ca/en/rss/news/"},
    {"id": "ireland-dpc", "name": "爱尔兰数据保护委员会", "region": "欧洲", "country": "爱尔兰", "kind": "公开网页", "url": "https://www.dataprotection.ie/en/news-media/latest-news"},
    {"id": "netherlands-ap", "name": "荷兰个人数据保护局", "region": "欧洲", "country": "荷兰", "kind": "RSS", "url": "https://autoriteitpersoonsgegevens.nl/nl/rss"},
    {"id": "nz-privacy", "name": "新西兰隐私专员办公室", "region": "大洋洲", "country": "新西兰", "kind": "RSS", "url": "https://www.privacy.org.nz/tuhono-connect/statements-media-releases/rss/"},
    {"id": "brazil-anpd", "name": "巴西国家数据保护局", "region": "南美洲", "country": "巴西", "kind": "公开网页", "url": "https://www.gov.br/anpd/pt-br"},
    {"id": "philippines-npc", "name": "菲律宾国家隐私委员会", "region": "亚洲", "country": "菲律宾", "kind": "RSS", "url": "https://privacy.gov.ph/feed/"},
    {"id": "spain-aepd", "name": "西班牙数据保护局", "region": "欧洲", "country": "西班牙", "kind": "公开网页", "url": "https://www.aepd.es/prensa-y-comunicacion/notas-de-prensa"},
    {"id": "iapp-news", "name": "国际隐私专业人士协会", "region": "北美洲", "country": "美国", "kind": "公开网页", "url": "https://iapp.org/news"},
    {"id": "nda-local", "name": "国家数据局·地方动态", "region": "中国", "country": "中国", "kind": "公开网页", "url": "https://www.nda.gov.cn/sjj/swdt/dfdt/list/index_pc_1.html"},
    {"id": "nda-data-news", "name": "国家数据局·数据动态", "region": "中国", "country": "中国", "kind": "公开网页", "url": "https://www.nda.gov.cn/sjj/swdt/sjdt/list/index_pc_1.html"},
    {"id": "nda-notices", "name": "国家数据局·通知公告", "region": "中国", "country": "中国", "kind": "公开网页", "url": "https://www.nda.gov.cn/sjj/zwgk/tzgg/list/index_pc_1.html"},
    {"id": "nda-international", "name": "国家数据局·国际交流合作", "region": "中国", "country": "中国", "kind": "公开网页", "url": "https://www.nda.gov.cn/sjj/ywpd/gjjlhz/list/index_pc_1.html"},
    {"id": "nda-release", "name": "国家数据局·新闻发布", "region": "中国", "country": "中国", "kind": "公开网页", "url": "https://www.nda.gov.cn/sjj/swdt/xwfb/list/index_pc_1.html"},
    {"id": "nda-media", "name": "国家数据局·媒体声音", "region": "中国", "country": "中国", "kind": "公开网页", "url": "https://www.nda.gov.cn/sjj/swdt/mtsy/list/index_pc_1.html"},
    {"id": "shanghai-news", "name": "上海市数据局·工作动态", "region": "中国", "country": "中国", "province": "上海", "kind": "公开网页", "url": "https://sdb.sh.gov.cn/index.html"},
    {"id": "shanghai-notices", "name": "上海市数据局·公示公告", "region": "中国", "country": "中国", "province": "上海", "kind": "公开网页", "url": "https://sdb.sh.gov.cn/gsgg/"},
    {"id": "beijing-policy", "name": "北京市政务服务和数据管理局·政策文件", "region": "中国", "country": "中国", "province": "北京", "kind": "公开网页", "url": "https://zwfwj.beijing.gov.cn/zwgk/2024zcwj/"},
    {"id": "jiangsu-data", "name": "江苏省数据局·要闻与公告", "region": "中国", "country": "中国", "province": "江苏", "kind": "公开网页", "url": "https://jszwb.jiangsu.gov.cn/"},
    {"id": "guangdong-news", "name": "广东省政务服务和数据管理局·要闻速递", "region": "中国", "country": "中国", "province": "广东", "kind": "公开网页", "url": "https://zfsg.gd.gov.cn/xxfb/ywsd/index.html"},
    {"id": "guangdong-data", "name": "广东省政务服务和数据管理局·数据要闻", "region": "中国", "country": "中国", "kind": "公开网页", "url": "https://zfsg.gd.gov.cn/xxfb/sjyw/index.html"},
    {"id": "guangdong-local", "name": "广东省政务服务和数据管理局·动态新闻", "region": "中国", "country": "中国", "province": "广东", "kind": "公开网页", "url": "https://zfsg.gd.gov.cn/xxfb/dtxw/index.html"},
]

CATEGORY_NAMES = {c["id"]: c["name"] for s in SECTIONS for c in s["categories"]}
SECTION_BY_CATEGORY = {c["id"]: s["id"] for s in SECTIONS for c in s["categories"]}

# Editorial relevance is intentionally strict: broad "AI" or "digital" news
# should not crowd out items that actually concern data governance.
DATA_TERMS = [
    "open data", "public data", "government data", "data governance",
    "data sharing", "data access", "data portability", "data space",
    "data spaces", "data intermediary", "data commons", "data protection",
    "personal data", "privacy", "dataset", "datasets", "data infrastructure",
    "data reuse", "data re-use", "data stewardship", "data quality",
    "interoperability", "cross-border data", "data transfer", "data flows",
    "personal information", "information access", "freedom of information",
    "disclosure log", "consumer data right", "pipa",
    "privacy rights", "privacy commissioner", "privacy oversight", "privacy law",
    "privacy regulation", "privacy enforcement", "data breach", "data security",
    "gdpr", "ai governance", "ai act",
    "数据开放", "公共数据", "数据治理", "数据共享", "个人信息", "数据空间",
    "数据要素", "数据资源", "数据流通", "数据安全", "数据集", "数据出境",
    "隐私保护", "个人信息保护", "个人数据保护", "数据保护", "网络数据", "数据产权",
    "个人資料", "個人資料保護", "个人资料保护", "開放資料", "公共資料", "資料治理",
    "protection des données", "données personnelles", "données ouvertes", "gouvernance des données",
    "datenschutz", "personenbezogene daten", "offene daten", "datenverwaltung",
    "protección de datos", "datos personales", "datos abiertos", "gobernanza de datos",
    "proteção de dados", "dados pessoais", "dados abertos", "governança de dados",
    "protezione dei dati", "dati personali", "dati aperti", "governance dei dati",
    "gegevensbescherming", "persoonsgegevens", "open data", "gegevensbeheer",
    "ochrona danych", "dane osobowe", "otwarte dane", "zarządzanie danymi",
    "databeskyttelse", "personoplysninger", "åbne data", "datastyring",
    "dataskydd", "personuppgifter", "öppna data", "datastyrning",
    "personvern", "personopplysninger", "åpne data", "datastyring",
    "tietosuoja", "henkilötiedot", "avoindata", "tiedonhallinta",
    "ochrana osobních údajů", "osobní údaje", "otevřená data",
    "protecția datelor", "date personale", "date deschise",
    "zaštita osobnih podataka", "osobni podaci", "otvoreni podaci",
    "προστασία δεδομένων", "προσωπικά δεδομένα", "ανοικτά δεδομένα",
    "защита на личните данни", "лични данни", "отворени данни",
    "andmekaitse", "isikuandmed", "avatud andmed",
    "duomenų apsauga", "asmens duomenys", "atviri duomenys",
    "datu aizsardzība", "personas dati", "atvērtie dati",
    "adatvédelem", "személyes adatok", "nyílt adatok",
    "ochrana osobných údajov", "osobné údaje", "otvorené údaje",
    "varstvo osebnih podatkov", "osebni podatki", "odprti podatki",
    "数字政府", "数字经济", "数字化转型", "数据局", "数字领域", "数字总通道", "数字出海",
]

CATEGORY_TERMS = {
    "law": ["regulation", "directive", "legislation", "law", "legal", "act", "compliance", "enforcement", "rulebook", "法案", "法规", "立法", "办法", "条例", "规定", "政策文件"],
    "plan": ["action plan", "strategy", "roadmap", "programme", "program", "initiative", "framework", "行动计划", "战略", "路线图", "实施方案", "试点", "规划"],
    "scope": ["high-value dataset", "high value dataset", "dataset release", "data release", "new dataset", "open dataset", "数据集", "开放范围", "数据目录", "开放清单", "開放資料"],
    "platform": ["portal", "platform", "dashboard", "catalogue", "catalog", "repository", "api", "infrastructure", "门户", "平台", "基础设施", "算力网"],
    "service": ["standard", "metadata", "interoperability", "service", "guidance", "guide", "support centre", "assistant", "licensing", "licence", "支持", "服务", "标准", "登记", "授权运营", "資料治理"],
    "activity": ["consultation", "workshop", "conference", "event", "campaign", "training", "seminar", "academy", "webinar", "研讨", "咨询", "活动", "大赛", "培训", "会议"],
    "outcome": ["use case", "reuse", "re-use", "impact", "application", "benefit", "innovation", "in action", "practical", "exploring", "成果", "应用", "利用", "案例", "上线", "发布"],
    "international": ["united nations", "unesco", "world bank", "oecd", "open government partnership", "international", "global", "联合国", "国际组织"],
    "dataspace": ["data space", "data spaces", "dataspace", "数据空间"],
    "intermediary": ["data intermediary", "data intermediation", "data broker", "data trust", "数据中介", "数据信托"],
    "commons": ["data commons", "data common", "data cooperative", "数据公地", "数据合作社"],
    "crossborder": ["cross-border", "cross border", "international data transfer", "data flow", "data flows", "without borders", "non-eu collaboration", "跨境", "跨国数据"],
    "privacy": ["privacy", "data protection", "personal data", "personal information", "gdpr", "breach", "隐私", "个人信息", "个人数据保护", "数据保护", "数据安全", "個人資料", "个人资料", "資料保護", "protection des données", "données personnelles", "datenschutz", "personenbezogene daten", "protección de datos", "datos personales", "proteção de dados", "dados pessoais", "protezione dei dati", "dati personali", "gegevensbescherming", "persoonsgegevens", "ochrona danych", "dane osobowe", "databeskyttelse", "personoplysninger", "dataskydd", "personuppgifter", "personvern", "personopplysninger", "tietosuoja", "henkilötiedot", "ochrana osobních údajů", "osobní údaje", "protecția datelor", "date personale", "zaštita osobnih podataka", "osobni podaci", "προστασία δεδομένων", "προσωπικά δεδομένα", "защита на личните данни", "лични данни", "andmekaitse", "isikuandmed", "duomenų apsauga", "asmens duomenys", "datu aizsardzība", "personas dati", "adatvédelem", "személyes adatok", "ochrana osobných údajov", "osobné údaje", "varstvo osebnih podatkov", "osebni podatki"],
    "ai": ["ai-ready data", "ai ready data", "training data", "artificial intelligence", "machine learning", "ai model", "generative ai", "ai", "人工智能", "模型训练"],
}
