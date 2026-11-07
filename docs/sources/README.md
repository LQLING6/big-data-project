# 来源台账与准入检查

本目录记录候选竞赛来源的准入结论与依据，是采集开关、审核发布和定期复查的唯一依据。

## 当前状态

- 台账检查日期：2026-11-07
- 当前登记来源：6 个
- `pending`：4 个，禁止开启网络采集
- `rejected`：2 个，不得采集
- `allowed`：0 个
- 结论：C01 已完成候选来源初筛，但尚未达到 C03 的联网条件；项目中的真实采集开关继续保持关闭。

## 文件说明

- `registry.csv`：候选来源台账，记录身份、目标路径、robots、条款、状态、复查日期和证据位置。
- `first-batch.md`：首批接入顺序、待补材料和启动条件。
- `evidence/2026-11-07-source-audit.md`：本轮来源身份、robots、条款和目标页面核查记录。

## 台账字段

| 字段 | 含义 |
|---|---|
| source_id | 稳定来源编号，例如 `src-001` |
| name | 来源名称 |
| official_identity | 页面可见的主办方或主管单位 |
| base_url | 来源站点根地址 |
| target_paths | 计划检查的公开通知路径，不代表已获准采集 |
| terms_url | 服务条款、注册协议或网站声明地址；空值表示未找到公开条款 |
| robots_status | `allow`、`deny`、`absent` 或 `unknown` |
| interval_seconds | 获准后的最小采集间隔；`0` 表示当前禁止请求 |
| retention_days | 获准后的留存期限；空值表示尚未确认 |
| policy_status | `allowed`、`pending` 或 `rejected` |
| priority | 首批接入优先级 |
| checked_at | 本轮核查日期 |
| review_date | 下一次复查日期 |
| evidence_path | 对应证据记录位置 |
| notes | 准入结论和限制说明 |

## 状态规则

- `allowed`：身份、条款、robots、路径、频率和留存要求均已确认，并经过指定审查人复核。
- `pending`：存在未确认项，必须保持 `network_enabled=false`。
- `rejected`：明确禁止、无法安全访问或不符合项目约束，不得通过更换 User-Agent、代理或登录方式绕过。
- `robots.txt` 缺失、为空、返回登录页或无法解析时，不等同于采集授权。
- 站点明确禁止 AI/LLM 爬虫时，本项目不得通过自定义 User-Agent 规避限制，直接拒绝或暂停。
- 只接受 HTTPS 来源；HTTPS 地址降级到 HTTP 时暂停接入。

## 当前复审要求

1. `src-001` 至 `src-004` 需要补充条款或授权依据，并由 B 复核后才能转为 `allowed`。
2. 转为 `allowed` 前不得运行真实网络采集。
3. 首次真实联网验证必须显式启用，不能进入普通测试或 CI。
4. 每次复查更新 `policy_status`、`review_date`、`notes` 和证据文件。
