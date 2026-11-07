# C02 通知输入规范与字段映射

版本：`c02-v1`  
检查日期：2026-11-07

## 1. 目标

C02 为 B 的入库与 D 的推荐提供同一套、可校验的通知输入结构。字段缺失时保留未知，不补造默认值。该结构不负责联网，也不直接操作数据库。

实现位置：

```text
backend/app/crawlers/normalized.py
backend/app/fixtures/source_samples.json
```

## 2. Schema 主要字段

| 字段 | 含义 | 缺失策略 |
|---|---|---|
| `schema_version` | 输入结构版本 | 固定为 `c02-v1` |
| `sample_type` | `synthetic` 或 `real` | 必填，不能混用 |
| `source_id` | 来源台账编号 | 必填 |
| `external_key` | 同一来源内的稳定业务键 | 必填 |
| `title` | 通知标题 | 必填 |
| `organizer` | 主办方 | 必填 |
| `category` | 赛事分类 | 必填 |
| `edition` | 届次/年份 | 必填，不能用标题猜 |
| `track` | 赛道 | 必填，不能用标题猜 |
| `school_scope` | 适用学校 | 未公布时为 `null` |
| `allowed_levels` | 培养层次 | 未公布时为空列表 |
| `allowed_majors` | 专业范围 | 未公布时为空列表 |
| `grade_min` / `grade_max` | 年级范围 | 未公布时为 `null` |
| `deadlines` | 多个截止项 | 至少一项；未知项保留 `unknown` |
| `entry_url` | 报名入口 | 未公布时为 `null`，禁止占位链接 |
| `event_date` | 比赛日期 | 未公布时为 `null` |
| `field_evidence` | 字段到原文证据的映射 | 至少一项 |
| `body` | 去噪后的正文/摘要输入 | 必填，不能替代原文证据 |
| `notice_version` | 通知版本 | 从 1 开始，内容变化时递增 |
| `parser_version` | 解析器版本 | 必填，便于回归 |

## 3. 截止项规范

每个截止项包含：

```json
{
  "kind": "organizer_registration",
  "precision": "datetime",
  "at": "2027-03-15T18:00:00+08:00",
  "on_date": null,
  "evidence": {}
}
```

- `kind`：
  - `school_selection`：校内选拔
  - `organizer_registration`：主办方报名
  - `competition_schedule`：比赛日程
- `precision=datetime`：只能提供带时区的 `at`，`on_date` 为空。
- `precision=date`：只能提供 `on_date`，`at` 为空。
- `precision=unknown`：两个值都为空，不能推测为 `23:59`。
- 校内截止、主办方截止和比赛日程必须并列保存，不能互相覆盖。

## 4. 与当前数据库模型的映射

| C02 字段 | 当前 `Competition` 字段 | 处理 |
|---|---|---|
| `title` | `title` | 直接映射 |
| `organizer` | `organizer` | 直接映射 |
| `category` | `category` | 直接映射 |
| `summary` | `summary` | 直接映射 |
| `edition` | `edition` | 直接映射 |
| `school_scope` | `allowed_school` | 直接映射 |
| `allowed_levels` | `allowed_levels` | JSON 映射 |
| `allowed_majors` | `allowed_majors` | JSON 映射 |
| `grade_min` / `grade_max` | 同名字段 | 直接映射 |
| `entry_url` | 当前无独立字段 | C04 前需与 B 确认入口字段 |
| `deadlines` | 当前仅有单组截止字段 | **需要 B 扩展为多截止项模型或关联表** |
| `field_evidence` | `evidence` | 合并为 JSON 证据映射 |
| `notice_version` | `version` | 入库时同步 |
| `sample_type` | `is_demo` | `synthetic→true`，`real→false` 仅作转换提示 |

> 当前 B 分支的模型仍只有一组 `deadline_*` 字段，尚不能保存多个截止项。C04 开始前必须与 B 确认多截止项迁移，不能由 C 私自复制模型。

## 5. 离线样本

`backend/app/fixtures/source_samples.json` 当前包含 12 份合成样本：

- 正常精确时间
- 仅日期
- 未知截止
- 多截止项
- 专业缺失
- 年级缺失
- 延期后的第二版本
- 跨届
- 跨赛道
- 不同学校范围
- 报名入口缺失
- 仅比赛日程

全部样本均为 `sample_type=synthetic`，当前真实样本数量为 0。普通测试只读取该文件，不访问网络，也不把合成样本计入真实采集量。

## 6. 审查要求

- B：确认字段可入库、缺失值不会被默认填充、多截止项迁移方案明确。
- D：确认资格、时间精度和证据字段足够使用。
- 审查通过前不得把本 Schema 宣称为真实来源解析结果。
