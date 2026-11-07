# 来源核查记录：2026-11-07

## 检查范围与方法

- 检查日期：2026-11-07（Asia/Shanghai）
- User-Agent：`CampusCompAI-source-audit/0.1`
- 每个来源仅检查主页、候选通知列表、`robots.txt` 和公开条款页面，未批量抓取通知正文。
- 请求使用 10—20 秒超时并跟随有限重定向；未使用代理、账号、验证码或任何访问控制绕过方式。
- 记录仅保留 URL、HTTP 状态、页面标题和判断依据，不保存来源全文。

## 汇总

| 来源 | robots | 条款/授权 | 目标页面 | 结论 |
|---|---|---|---|---|
| src-001 中国大学生计算机设计大赛 | 404，缺失 | 仅版权声明，未找到采集授权 | `/dsdt.htm` 可公开访问，静态列表 | pending |
| src-002 全国大学生数学建模竞赛 | 200，空文件 | 未找到公开条款 | 历程与动态页面可公开访问，静态列表 | pending |
| src-003 全国大学生电子设计竞赛 | 404，缺失 | 注册协议和隐私条款，未明确允许采集 | `/index/news` 可公开访问 | pending |
| src-004 全国大学生创业服务网 | 重定向至登录页，无效 | 未找到公开条款 | SPA 页面，公开入口存在登录项 | pending |
| src-005 挑战杯 | 200，明确禁止多种 AI 爬虫并限制 `/project/` | 无采集授权 | 不继续检查 | rejected |
| src-006 教育部政府门户网站 | 404，缺失 | 网站声明限制商业性原版转载 | HTTPS 入口降级至 HTTP | rejected |

## src-001 中国大学生计算机设计大赛

- 官方身份：页脚显示“版权所有©中国大学生计算机设计大赛组织委员会”。
- 主页：`https://jsjds.blcu.edu.cn/`，HTTP 200。
- 候选路径：`https://jsjds.blcu.edu.cn/dsdt.htm`，HTTP 200，标题“大赛动态-中国大学生计算机设计大赛”，页面未见登录或验证码。
- 联系方式：`https://jsjds.blcu.edu.cn/gyds1/lxfs.htm`，HTTP 200。
- robots：`https://jsjds.blcu.edu.cn/robots.txt` 返回 404 HTML，因此记为 `absent`，不是授权。
- 条款：页面只有版权声明，未找到公开服务条款或明确采集授权。
- 结论：`pending`。适合作为首个静态列表适配器候选，但必须先补齐授权依据并由 B 复核。

## src-002 全国大学生数学建模竞赛

- 官方身份：竞赛组织页面显示 Organizor 为中国工业与应用数学学会。
- 主页：`https://www.mcm.edu.cn/`，HTTP 200。
- 候选路径：`https://www.mcm.edu.cn/html_cn/section/a657eb64216f6fd724196d37bcb5c1c4.html`，HTTP 200，标题“全国大学生数学建模竞赛”，页面包含“通知与公告”栏目。
- robots：`https://www.mcm.edu.cn/robots.txt` 返回 HTTP 200 空文件，记为 `absent`，不等同于授权。
- 条款：未找到公开服务条款或采集授权。
- 结论：`pending`。页面结构简单，可作为第二批静态列表候选，但需先确认条款。

## src-003 全国大学生电子设计竞赛

- 官方身份：页脚显示“全国大学生电子设计竞赛组织委员会 版权所有”。
- 主页：`https://www.nuedc-training.com.cn/`，HTTP 200。
- 候选路径：`https://www.nuedc-training.com.cn/index/news`，HTTP 200，标题“信息发布-全国大学生电子设计竞赛培训网”，通知列表公开可见。
- robots：`https://www.nuedc-training.com.cn/robots.txt` 返回 404 HTML，记为 `absent`。
- 条款：存在注册协议和隐私条款，但未明确允许自动采集或内容留存：
  - `https://www.nuedc-training.com.cn/index/common/reg`
  - `https://www.nuedc-training.com.cn/index/common/privacy`
- 结论：`pending`。仅检查公开通知列表，不进入登录区域；条款确认前禁止联网采集。

## src-004 全国大学生创业服务网（中国国际大学生创新大赛）

- 官方身份：页脚显示“版权所有：教育部学生服务与素质发展中心”。
- 主页：`https://cy.ncss.cn/`，HTTP 200。
- 候选路径：`https://cy.ncss.cn/information/dsdt?typeCode=CYDS_2TH_DSDT`，HTTP 200，标题“大赛动态”，页面为前端应用并提示使用 Chrome 最新版。
- robots：`https://cy.ncss.cn/robots.txt` 重定向到学信网登录页，未取得有效 robots 规则，记为 `unknown`。
- 条款：未找到公开采集条款；页面存在登录入口。
- 结论：`pending`。需要先确认公开数据接口或静态列表路径；不得通过登录、验证码或浏览器自动化绕过访问控制。

## src-005 挑战杯

- 官方身份：页脚显示“挑战杯全国大学生课外学术科技作品竞赛 / 挑战杯中国大学生创业计划竞赛 竞赛组委会 版权所有”。
- robots：`https://www.tiaozhanbei.net/robots.txt` 返回 HTTP 200。
- 规则明确禁止 `GPTBot`、`ChatGPT-User`、`OAI-SearchBot`、`ClaudeBot`、`Claude-SearchBot`、`anthropic-ai`、`CCBot` 等 AI/LLM 爬虫，并禁止 `/project/` 相关路径。
- 结论：`rejected`。不得通过自定义 User-Agent 规避站点对 AI 爬虫的限制。

## src-006 中华人民共和国教育部政府门户网站

- 官方身份：页脚显示“版权所有：中华人民共和国教育部”。
- 网站声明：`http://www.moe.gov.cn/jyb_sy/s3634/201005/t20100504_87292.html`，限制商业性原版原式转载。
- HTTPS 检查：访问 `https://www.moe.gov.cn/` 最终降级到 `http://www.moe.gov.cn/`。
- robots：`/robots.txt` 返回 404。
- 结论：`rejected`。HTTPS 降级不满足项目的 HTTPS-only 传输约束；如后续网站支持稳定 HTTPS，可重新审查。

## 附加说明

- 本轮没有确认任何 `allowed` 来源。
- 未确认来源不得创建网络适配器、开启 `network_enabled` 或加入普通 CI。
- 下一步应先由 B 复核本台账，再由团队决定是否联系来源维护方确认条款或授权。
