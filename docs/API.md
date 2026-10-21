# API约定

前缀`/api/v1`。完整请求和响应在启动后的`/docs`查看。

| 方法与路径 | 权限 | 用途 |
|---|---|---|
| GET `/health` | 公开 | 本地服务与演示状态 |
| GET `/competitions` | 公开 | 已发布列表，支持q/category/include_expired |
| GET `/competitions/{id}` | 公开 | 已发布赛事与证据 |
| POST `/auth/login` | 公开 | 用户名密码换取12小时Bearer令牌 |
| POST `/auth/logout` | 已登录 | 撤销当前令牌 |
| GET `/me` | 已登录 | 当前用户 |
| GET/PUT `/me/profile` | 已登录 | 自己的画像 |
| GET `/me/recommendations` | 已登录 | 实时规则推荐与证据理由 |
| GET/POST `/me/subscriptions` | 已登录 | 自己的订阅；POST接收competition_id与lead_hours |
| DELETE `/me/subscriptions/{id}` | 所有者 | 取消订阅和待发提醒 |
| GET `/me/notifications` | 已登录 | 自己最近100条站内记录 |
| POST `/me/notifications/{id}/read` | 所有者 | 标为已读 |
| GET `/admin/sources` | 管理员 | 来源策略 |
| GET `/admin/status` | 管理员 | 数据与任务概况 |
| POST `/admin/import-fixtures` | 管理员+演示模式 | 重新导入本地合成通知 |
| POST `/admin/run-cycle` | 管理员 | 手动执行本地到期扫描与站内消费 |
| POST `/admin/demo-trigger` | 管理员+演示模式 | 提前处理一条合成数据提醒 |
| PATCH `/admin/competitions/{id}/deadline` | 管理员+合成赛事 | 截止变更演练，要求时区和原因 |

令牌只通过`Authorization: Bearer ...`传递，不放URL。前端仅在当前会话sessionStorage保存；源码不包含真实用户令牌。

重要数据约定：

- 时间字段输出UTC ISO 8601，前端按北京时间展示。输入精确截止必须带时区。
- `deadline_precision=datetime`使用`deadline_at`；`date`使用`deadline_date`；`unknown`不填推测值。
- `score`仅是排序分；`qualification`和`warnings`单独使用。
- 当前`explanation_provider=rules`。模型真正接入并校验通过后才可显示其他来源。
- `is_demo=true`必须持续展示合成数据标记，不能作为真实报名入口。
- `delivery_status=recorded`仅代表站内保存成功。
- 订阅POST的业务键为用户与赛事，相同参数重复调用不重复建计划。

新增接口应使用同一前缀，先在任务或PR中约定类型。不要让前端猜测字段含义。
