# MEMORY.md - 重要决策与规范

## 🐍 Venv使用规范（2026-03-04 固化）

### 核心原则
**所有Python代码必须使用venv运行，这是硬性要求，不得违反！**

### 关键记忆点
- venv Python路径: `/root/.openclaw/workspace/venv/bin/python3`
- runner脚本: `./venv_runner.sh` （最推荐，自动处理环境变量）
- 长桥环境变量文件: `.longbridge.env`

### 决策原因
1. 包含长桥SDK (`longport`) — 系统Python没有
2. 包含金融数据包 (`efinance`, `qteasy`, `tushare`)
3. 确保所有依赖一致性
4. 避免运行时缺少包的错误

### 运行方式（优先级）
1. `./venv_runner.sh script.py` ✅ （自动加载.longbridge.env）
2. `/root/.openclaw/workspace/venv/bin/python3 script.py` ✅
3. `source venv/bin/activate && python3 script.py` ✅

### 绝对禁止
- `python3 script.py` ❌
- `/usr/bin/python3 script.py` ❌

### 检查清单（每次运行Python前）
- [ ] 脚本shebang是否正确？`#!/root/.openclaw/workspace/venv/bin/python3`
- [ ] 是否需要长桥API？→ 使用 `./venv_runner.sh`
- [ ] 是否使用了正确的Python路径？

### 自动化工具（已创建）
- `venv_runner.sh` — 通用运行脚本
- `check_venv_compliance.sh` — 合规性检查
- `fix_shebang.sh` — 自动修复shebang
- `VENV_GUIDE.md` — 完整指南

### 历史教训
**2026-03-04**: 曾因未使用venv导致长桥API调用失败，用户指出后修复。已固化到SOUL.md铁律和MEMORY.md。

---

## 长桥API Token问题（2026-05-27 记录）

### 问题
- Token于 **2026-05-21** 过期
- 错误码: `401003`（Token无效）
- 影响: 所有依赖长桥API的报告降级为简化版

### 受影响报告
| 报告 | 时间 | 影响 |
|:---|:---|:---|
| A+H开盘前瞻 | 09:30 | 港股数据缺失 |
| 收盘深度报告 | 15:05 | 全市场→15只样本股，缺板块/龙虎榜/个股 |
| 美股隔夜 | 08:30 | 可能同样降级 |

### 修复方案
1. 前往 https://open.longportapp.com 刷新 Access Token
2. 更新 `.longbridge.env` 中的 `LONGPORT_ACCESS_TOKEN`
3. 验证：运行 `python3 -c "from longport import ..."` 测试连接

### 备用数据源
- Tushare: A股历史数据 ✅（但不支持实时+港股）
- 腾讯API: 指数数据 ✅（仅指数，无板块/个股深度）
- 需要长桥Token才能恢复全功能

---

## 其他重要决策

### 长桥API使用
- Token位置: `.longbridge.env`
- 加载方式: `export $(grep -v '^#' .longbridge.env | xargs)`
- SDK路径: `/root/.openclaw/workspace/venv/lib/python3.x/site-packages/longport/`

### API优先级（数据源）
1. 长桥API — 首选，实时性好
2. efinance — 次选，A股实时
3. 腾讯API — 备选，指数数据稳定
4. Tushare — 历史数据

### 数据回补进度（2026-03-04）
- 2026年价格数据: ✅ 已完成
- 2026年估值数据: ✅ 已完成
- 2026年因子数据: 🔄 计算中
- 2018-2025历史数据: 🔄 回补中

### 收盘报告生成
- 完整版脚本: `tools/daily_market_report_full_v4.py`
- 数据源: 长桥API (5190只股票)
- 报告路径: `data/daily_report_full_YYYYMMDD.md`
