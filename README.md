# 全球数据治理追踪器

面向公众的全球数据治理资讯平台，持续汇集数据开放、数据空间、跨境数据流动、隐私与个人信息保护、人工智能数据治理等公开动态。追踪从 **2026 年 9 月 1 日**开始。

页面包括主题浏览、国际动态、国内动态、每周简报、收藏和动态活力热力图。读者可按关键词、主题、欧盟或国家、中国省市、来源和月份筛选，查看原文，下载 CSV，并把资讯收藏在当前浏览器中。

## 当前产品逻辑

- 国际与国内分别设置入口。欧盟机构单列为“欧盟”，法国、英国、德国等国家分别归档。
- 每周简报按周一至周日汇总本周全部已收录资讯；本周周报统计截至当天。简报先归并并梳理主要事件，再形成带来源依据的整合分析。
- 活力热力图默认显示本周热度，也可切换上周或 9 月以来。指数为该范围内地区收录条数除以最高地区收录条数再乘 100，反映平台检出的资讯密度，不评价治理绩效。
- 机构发布、公开报道和 Digital Policy Alert 政策事件保留原始链接。报道按发布日期归入周次，政策事件按事件日期归入周次。
- 云端模式支持邮箱注册、登录、退出和 14 天会话；密码使用 PBKDF2 加盐保存，服务端不会存储明文密码。

## 本地运行

```bash
python3 server.py
```

打开 [http://127.0.0.1:8765](http://127.0.0.1:8765)。macOS 登录后自动启动可运行：

```bash
python3 install_server.py
```

## 每 6 小时更新

云端设置 `ENABLE_SCHEDULER=1` 后，服务每 6 小时依次运行：

```bash
python3 collector.py
python3 media_index.py --languages all
python3 media_index.py --repair-locations
python3 dpa_index.py
python3 report_cli.py generate-pending
```

前四步采集和修复公开资讯；最后一步使用 DeepSeek 为需要更新的周次生成中文周报。任务会校验周报引用的资讯 ID；每项主要事件和分析判断均可追溯到本周来源。未配置 DeepSeek 密钥时，网站仍提供基于统计和代表性来源的周度概览，但不会调用模型生成深度周报。

已接入 34 个公开机构栏目，并结合 Bing News 多语种索引、Digital Policy Alert 公开活动页和经核验的 Google News 线索。检索语言包括中文、英文、西班牙语、法语、德语、葡萄牙语、日语、韩语和阿拉伯语。DataGuidance 仅用于发现公开线索，不读取或复制订阅内容。

## DeepSeek 配置

模型调用使用 DeepSeek 的 OpenAI 兼容接口：

```bash
export DEEPSEEK_API_KEY="你的密钥"
export DEEPSEEK_MODEL="deepseek-chat"
```

也可通过 `DEEPSEEK_BASE_URL` 覆盖默认的 `https://api.deepseek.com`。密钥只放在环境变量或云平台 Secret 中，不要提交到代码仓库。

手动生成周报：

```bash
python3 report_cli.py pending
python3 report_cli.py generate 2026-09-28
python3 report_cli.py generate-pending
```

日期参数必须是该周周一。

## 登录模式

云端建议设置：

```bash
REQUIRE_LOGIN=1
ALLOW_REGISTRATION=1
COOKIE_SECURE=1
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=请使用高强度密码
```

`ALLOW_REGISTRATION=0` 可关闭公开注册，只保留已有账号和环境变量创建的初始管理员账号。本地默认不强制登录；如在 HTTP 本地测试登录，应临时设置 `COOKIE_SECURE=0`。

## Render 云端部署

项目包含 `Dockerfile` 和 `render.yaml`。Render Blueprint 会创建一个带 2 GB 持久磁盘的 Web Service，并开启登录、DeepSeek 周报和每 6 小时采集。

部署时需要在 Render Secret 中填写：

- `DEEPSEEK_API_KEY`
- `ADMIN_EMAIL`
- `ADMIN_PASSWORD`

SQLite 数据库和定时任务状态保存在 `/var/data`。应用启动时，如果持久磁盘为空，会先复制仓库内的 9 月以来初始资料库，随后继续增量更新。

## 数据说明

来源覆盖仍在扩展，收录数字表示资讯记录数，不表示独立政策事件数。同一事件可能存在机构发布、媒体报道或不同政策条款。后续应继续扩展国家监管机构和中国省市官方栏目，并完善跨来源事件合并。

页面摘要用于快速了解内容，政策状态、数字和日期应以来源原文为准。
