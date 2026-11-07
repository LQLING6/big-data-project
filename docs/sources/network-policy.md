# C03 安全网络策略与适配器骨架

版本：`c03-v1`  
检查日期：2026-11-07

## 当前状态

C03 的安全网络基础设施和离线测试已完成，但真实来源适配器尚未开启：

- C01 当前 `allowed=0`
- 所有真实来源保持网络关闭
- `ApprovedStaticPageAdapter` 默认 fail closed
- 普通测试只使用 `httpx.MockTransport`，不访问互联网
- “首个获准官方来源”的站点级字段解析仍需在 C01 出现 `allowed` 来源后完成

## 代码位置

```text
backend/app/crawlers/network_policy.py
backend/app/crawlers/approved_source.py
backend/app/crawlers/base.py
backend/tests/test_source_network_policy.py
backend/tests/test_approved_source_adapter.py
```

## 已实现的停止条件

1. 未批准来源或 `network_enabled=false` 时，在发出任何 HTTP/DNS 请求前拒绝。
2. 仅允许 HTTPS，禁止 URL 账号信息和非 443 端口。
3. 域名必须精确命中白名单。
4. 路径必须命中配置前缀，`robots.txt` 仅作为协议检查例外。
5. 每一跳重定向都重新验证协议、域名、路径和解析后的 IP。
6. 解析后的所有 IP 必须是公网地址；本机、内网、链路本地、保留和元数据地址全部拒绝。
7. 默认 `trust_env=false`，不读取代理环境变量，不通过代理轮换绕过限制。
8. 连接和读取设置超时，响应设置字节上限。
9. robots.txt 被拒绝、401/403、验证码或登录要求均停止。
10. 429 按 `Retry-After` 退避，超过允许等待时间即暂停。
11. 域名级最小请求间隔在进程内执行。
12. 不执行网页脚本。

## 明确限制

- 当前只实现进程内限速，跨 Worker 的分布式限速必须在完整模式中另行验证。
- `ApprovedStaticPageAdapter` 只负责发现和保留列表页、详情页证据，尚不提取资格、截止等业务字段。
- 站点级解析器必须在 C01 来源变为 `allowed` 后，基于获准样本实现和回归。
- C03 目前不能标记为完成，只能标记为“基础设施完成、等待获准来源”。
