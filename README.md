# 赛知 CampusComp AI · 四人协作基础工程

这是可以本地运行、适合四个人继续扩充的项目基架。默认无须连接竞赛网站、模型API或邮件服务，也不需要付费密钥。

**先跑通演示，再分别领取一项任务：[四人任务分配](docs/TEAM_TASKS.md)。**

## 已能使用

- Vue 3 + TypeScript 网页：赛事筛选、详情与证据、画像、推荐、订阅、通知、来源后台。
- FastAPI：学生与管理员登录、12小时会话、个人数据隔离、受保护的管理接口。
- SQLAlchemy + Alembic：可迁移的数据模型，支持本地SQLite和完整模式PostgreSQL。
- 按专业、培养层次、年级限制过滤，按技能、兴趣、专业与已知时间信息排序；缺失信息明确提示。
- 仅精确截止时间生成提醒；重复订阅不重复建任务；退订取消旧任务；截止变更重排。
- 数据库Outbox、幂等站内通知、到期扫描、已投递未完成事件补偿和有限重试。
- 离线合成通知适配器、通知版本与内容去重、来源准入的拒绝默认策略。
- Docker Compose、CI配置、业务测试、四份可直接转为GitHub Issue的任务书。

## 扩展边界

**这不是已完成的正式服务。** 当前只有合成赛事，推荐由规则计算，真实网页采集、外部模型、邮件发送尚未接入。UI会明确说明，不把占位地址当报名入口。

源码中的扩展接口和四人任务用于把这些能力补齐。修改`AI_PROVIDER`或`EMAIL_PROVIDER`不会自动实现对应功能。`DEMO_MODE=false`仅关闭演示入口；正式发布前仍需完成账号管理、限流、邮箱验证、来源审核、部署安全与故障验证。不要把已种入演示账号的数据库直接开放到公网。

## 最快启动：只需要Python

建议Python 3.12。压缩包已包含前端构建产物`frontend-dist/`，首次运行不需要Node或Docker。

在项目根目录打开终端，Windows执行：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements-dev.txt
.\.venv\Scripts\python.exe scripts\run_demo.py
```

macOS / Linux：

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements-dev.txt
.venv/bin/python scripts/run_demo.py
```

然后打开：

- 网页：http://127.0.0.1:8000
- API文档：http://127.0.0.1:8000/docs

演示账号：

| 身份 | 用户名 | 密码 |
|---|---|---|
| 学生 | `student` | `CampusComp-demo-2026!` |
| 管理员 | `admin` | `CampusComp-admin-2026!` |

页面提供演示账号快捷入口。退出启动程序按`Ctrl+C`，启动器会停止自己创建的API和本地Worker。后台Worker日志位于`data/local-worker.log`。

## 五分钟验证闭环

1. 进入学生体验，查看赛事详情里的合成证据。
2. 进入“我的画像”，修改兴趣，再查看“为你推荐”。本科生不应被推荐仅限研究生的演示赛事。
3. 订阅“校园数据洞察挑战赛”。立即收到订阅确认，生成一条未来站内提醒计划。
4. 切换管理员，进入“来源与运行”，点击“提前处理一条演示提醒”。这仅提前处理合成数据任务，不修改真实截止日期，不发邮件。
5. 切回学生，进入通知中心。刷新后可见提醒，标为已读。
6. 取消订阅。未发送的旧提醒会取消。
7. API文档可用管理员令牌调用截止更新接口，观察版本、变更通知与提醒重排。

仅日期或未知截止时间可以订阅，但不生成精确提醒。订阅时已经错过的提前量不补发历史提醒。

## 开发方式

开发前端需要Node >=22.18，推荐pnpm 11。已提交`pnpm-lock.yaml`。

```sh
cd frontend
pnpm install --frozen-lockfile
pnpm dev
```

开发服务器默认为http://127.0.0.1:5173，通过代理访问8000端口API。后端在另一个终端运行：

```sh
cd backend
python -m app.cli init-demo
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

以上`python`须指向项目虚拟环境。单独启动本地提醒Worker：

```sh
cd backend
python -m app.cli worker
```

前端改好后，回到项目根目录执行`python scripts/build_frontend.py`，重新生成单进程演示所用的`frontend-dist/`。从Git仓库重新获取代码时，构建目录被忽略，需要先完成这一步。

## 完整模式：PostgreSQL + Redis + Celery

准备Docker与Compose，在根目录执行：

```sh
docker compose up --build
```

打开同一个8000端口。Compose包含数据库、Redis、一次性迁移/演示初始化、API、Worker和**单实例**Beat。数据库与Redis不向主机公开端口；API只绑定本机。

增加一个Worker：

```sh
docker compose up -d --scale worker=2
```

集群消费应使用PostgreSQL。SQLite仅用于单机单Worker教学演示，不用于验证多节点并发可靠性。跨主机扩展还需专用网络、认证与访问控制；本项目不宣称已经具备数据库或队列高可用。

`.env.example`用于Compose配置参考；本地Python默认读取进程环境变量，不会自动执行或读取`.env`。

## 验证

```sh
cd backend
python -m pytest -q
python -m alembic check
```

```sh
cd frontend
pnpm build
```

如果全局Python环境的无关pytest插件冲突，请使用项目虚拟环境；也可设置`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`后运行。测试均在独立内存数据库执行，不访问外网、不发送邮件、不改变演示数据库。

本次实际验证结果见[验证记录](docs/VALIDATION.md)。启动器还支持`python scripts/run_demo.py --check`：临时启动并检查后自动停止。

界面预览：[桌面](docs/screenshots/desktop.png)、[手机](docs/screenshots/mobile.png)。

## 目录与协作

```text
backend/app/routers/       HTTP接口，B主要维护
backend/app/models.py     共享数据模型；改动须先沟通并提交迁移
backend/app/crawlers/     采集适配器，C主要维护
backend/app/services/     推荐、提醒、导入等业务服务
backend/tests/            关键业务验证
frontend/src/             Vue页面与组件，A主要维护
scripts/                  本地启动与构建
docs/tasks/               A/B/C/D各一份首轮任务
docs/                     架构、接口、采集合规和协作说明
.github/                  CI与PR模板
```

读完[架构说明](docs/ARCHITECTURE.md)、[接口约定](docs/API.md)和[协作流程](CONTRIBUTING.md)后开始开发。所有任务书已提供文件入口、交付物、验收标准和PR建议。

仓库创建、权限邀请、分支保护和Issue发布由你们后续在自己的GitHub中操作；此工程未连接、读取或修改任何外部仓库。
