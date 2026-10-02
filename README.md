# 全球数据治理追踪器

一个面向公众的全球数据治理资讯平台。项目持续收集各国政府、监管机构、国际组织、行业协会、专业政策平台和公开媒体发布的信息，并以中文为主进行整理、检索和周度分析。

追踪范围从 **2026 年 9 月 1 日**开始，涵盖数据开放、公共数据、数据空间、跨境数据流动、隐私与个人信息保护、人工智能数据治理、数据基础设施和数据要素市场等议题。

## 主要功能

- **国际动态与国内动态**：按国家、欧盟机构和中国省市分别浏览。
- **多语种采集**：覆盖中文、英文、西班牙语、法语、德语、葡萄牙语、日语、韩语和阿拉伯语。
- **主题检索**：按关键词、主题、地区、来源和月份筛选，可查看原文并下载 CSV。
- **每周简报**：汇总周一至周日的全部收录内容，梳理主要事件、议题结构和综合趋势。
- **活力热力图**：展示本周、上周或 9 月以来各国及中国省市的资讯活跃程度。
- **来源追溯**：每条记录保留公开来源链接，周报中的事件和判断关联到具体资讯记录。
- **持续更新**：后台默认每 6 小时执行一次采集、整理、地区识别和周报更新。

网站默认公开访问，不要求注册或登录。项目同时保留可选账户模式，部署者可以按需启用。

## 数据与方法

目前接入 34 个公开机构栏目，并结合 Bing News 多语种索引、Digital Policy Alert 公开活动页和经过核验的 Google News 线索。DataGuidance 仅用于发现公开线索，不读取或复制订阅内容。

资讯报道按发布日期归入周次，政策事件按事件日期归入周次。热力指数采用以下相对值：

```text
地区热力指数 = 该地区在所选周期内的收录条数 ÷ 同图最高地区收录条数 × 100
```

该指数表示平台检出的公开资讯密度，不用于评价某个国家或地区的治理绩效。收录条数也不等同于独立政策事件数，同一事件可能同时存在机构发布、媒体报道和后续解读。

## DeepSeek 后台分析

DeepSeek 只在服务器后台运行，用于中文整理、主题分类和周报分析。浏览器不会获得 API 密钥，也不会直接请求模型接口。

```bash
export DEEPSEEK_API_KEY="your-key"
export DEEPSEEK_MODEL="deepseek-chat"
python3 server.py
```

如未配置密钥，网站仍能公开浏览并提供基于统计和代表性来源生成的周度概览。

手动生成周报：

```bash
python3 report_cli.py pending
python3 report_cli.py generate 2026-09-28
python3 report_cli.py generate-pending
```

日期参数为该周周一。

## 本地运行

项目使用 Python 标准库和 SQLite，无需安装额外 Python 依赖。

```bash
git clone https://github.com/siyahuang/global-data-governance-tracker.git
cd global-data-governance-tracker
python3 server.py
```

打开 `http://127.0.0.1:8765`。

## 自动更新流程

启用 `ENABLE_SCHEDULER=1` 后，服务按设定周期运行：

```bash
python3 collector.py
python3 media_index.py --languages all
python3 media_index.py --repair-locations
python3 dpa_index.py
python3 report_cli.py generate-pending
```

默认更新间隔为 21,600 秒，即 6 小时。可通过 `UPDATE_INTERVAL_SECONDS` 调整。

## 云端部署

仓库包含 Dockerfile 和 Render Blueprint。点击下面的按钮可以创建公开 Web Service：

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/siyahuang/global-data-governance-tracker)

部署时只需将 `DEEPSEEK_API_KEY` 填入 Render Secret。SQLite 数据库和定时任务状态保存在持久磁盘 `/var/data`；磁盘首次启动时会载入仓库内从 2026 年 9 月 1 日开始的初始资料库。

如需启用账户访问，可自行设置：

```text
REQUIRE_LOGIN=1
ALLOW_REGISTRATION=1
COOKIE_SECURE=1
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=use-a-strong-password
```

## 数据使用说明

页面摘要帮助读者快速浏览公开信息。涉及法律状态、监管要求、统计数字和生效日期时，应以链接所指向的来源原文为准。

欢迎通过 Issue 提交来源建议、数据纠错、地区识别问题和功能需求。

## 许可证

程序代码以 [MIT License](LICENSE) 发布。新闻、政策和机构材料的著作权归各自来源所有，本项目仅保存必要的索引、摘要和原始链接。
