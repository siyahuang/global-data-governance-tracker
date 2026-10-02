"""Conservative publisher-location attribution for China local news."""

PROVINCE_ALIASES = {
    "北京": ("北京",), "天津": ("天津",), "河北": ("河北",), "山西": ("山西",),
    "内蒙古": ("内蒙古", "呼和浩特", "包头", "鄂尔多斯"), "辽宁": ("辽宁", "沈阳", "大连", "鞍山"), "吉林": ("吉林", "长春"),
    "黑龙江": ("黑龙江",), "上海": ("上海",), "江苏": ("江苏", "南京", "苏州", "常州", "无锡", "南通"),
    "浙江": ("浙江", "杭州", "温州", "宁波"), "安徽": ("安徽", "合肥", "滁州", "芜湖", "蚌埠"),
    "福建": ("福建", "八闽", "福州", "厦门"), "江西": ("江西", "南昌"),
    "山东": ("山东", "济南", "青岛", "日照", "临沂", "威海", "烟台", "潍坊"), "河南": ("河南", "郑州", "洛阳"),
    "湖北": ("湖北", "武汉"), "湖南": ("湖南", "长沙"),
    "广东": ("广东", "广州", "深圳", "东莞"), "广西": ("广西", "南宁", "柳州"),
    "海南": ("海南", "海口"), "重庆": ("重庆",), "四川": ("四川", "成都"),
    "贵州": ("贵州", "贵阳"), "云南": ("云南", "昆明"),
    "西藏": ("西藏",), "陕西": ("陕西", "西安"),
    "青海": ("青海", "西宁"), "宁夏": ("宁夏", "银川"),
    "甘肃": ("甘肃", "兰州", "陇南"), "新疆": ("新疆", "乌鲁木齐"), "香港": ("香港",), "澳门": ("澳门",),
    "台湾": ("台湾",),
}


def infer_province(title, summary, source):
    """Prefer the publisher's declared province, then one unambiguous place in text."""
    if source.get("province"):
        return source["province"]
    if source.get("country") != "中国":
        return ""
    for text in (title, summary[:180]):
        matches = [province for province, aliases in PROVINCE_ALIASES.items()
                   if any(alias in text for alias in aliases)]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            return ""
    return ""
