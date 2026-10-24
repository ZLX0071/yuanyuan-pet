# 缘缘桌宠 (Yuanyuan Pet)

[![CI](https://github.com/ZLX0071/yuanyuan-pet/actions/workflows/ci.yml/badge.svg)](https://github.com/ZLX0071/yuanyuan-pet/actions/workflows/ci.yml)

一只会陪伴、会对你有反应、会记得你、懂你作息的 AI 桌面小狗——以真实小狗「缘缘」为原型的开源桌宠平台。

> **定位**：最有人格的桌面陪伴 + 轻助理。陪伴是灵魂（养成/作息/记忆），助理是增值（记事/提醒/专注），创作生态是护城河（开放格式 + UGC）。全部数据本地优先，AI 纯可选。
>
> 差异化与竞争格局详见 [docs/竞品分析.md](docs/竞品分析.md)，系统设计详见 [docs/架构图.md](docs/架构图.md)。

**核心能力**：桌面常驻（拖拽/物理落点/摸头互动）· 行为感知（打字/离开回来/久坐，仅内存计算）· 养成（饱食心情亲密度/成长体型/每日首喂双倍/陪伴天数）· **作息还原**（教她你的作息，她按节奏自主生活）· AI 对话与主动搭话（OpenAI 兼容，自带 Key）· 轻助理（对话式记事/ICS 日历/番茄钟专注陪伴）· 喝水久坐提醒（全屏自动延后）· 静默模式（Ctrl+Alt+Y）· **开放创作**（宠物包格式 v1.0 冻结 + zip 导入 + 创作指南 + 模板生成器）

## 快速开始

**便携版**（推荐）：下载 Release 里的 `YuanyuanPet-portable.zip` → 解压 → 双击 `YuanyuanPet.exe`。

**源码运行**：

```bash
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

不想配 AI？跳过——除聊天外全部功能照常。

## 文档

| 文档 | 内容 |
|---|---|
| [docs/竞品分析.md](docs/竞品分析.md) | 定位、竞争格局、差异化矩阵、边界 |
| [docs/架构图.md](docs/架构图.md) | 五层架构、数据流、设计决策、质量基建 |
| [PRD-AI桌宠-缘缘.md](PRD-AI桌宠-缘缘.md) | 产品需求文档（唯一需求依据） |
| [docs/任务拆解与里程碑.md](docs/任务拆解与里程碑.md) | M1~M6 任务与验收标准 |
| [docs/宠物包格式规范.md](docs/宠物包格式规范.md) | 宠物包格式 v1.0（引擎与创作者的合同） |
| [docs/创作指南.md](docs/创作指南.md) | 不写代码做出你的桌宠（10 分钟） |
| [创作工坊/](创作工坊/) | 分享你的宠物包：Discussions 模板 + 空白模板（官方皮肤：新春版/公主版见 pets/） |
| [docs/缘缘宠物包设计.md](docs/缘缘宠物包设计.md) | 官方吉祥物缘缘的素材与状态映射 |
| [docs/发布清单-M6.md](docs/发布清单-M6.md) | 发布步骤 / B 站脚本 / 种子试用文案 |

## 目录结构（对应 PRD 五层架构）

```
src/yuanyuan/
├── engine/   # 引擎层：透明窗口、动画状态机、物理
├── sense/    # 感知层：键鼠钩子、系统事件
├── life/     # 养成层：数值、演化、存档
├── ai/       # AI 层：对话、记忆、性格
└── content/  # 内容层：宠物包加载与校验
pets/         # 宠物包（缘缘包在这里）
scripts/      # PoC 与工具脚本
```

## 快速开始

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python scripts/poc_transparent_window.py   # T1.2 透明窗口 PoC
```

## 进度

- [x] **M1 骨架**（2026-10-24）：上桌、物理、拖拽、托盘
- [x] **M2 养成**（2026-10-24）：数值/演化/喂食/成长/存档
- [x] **M2.5 养成深化**（2026-10-24）：玩球/握手/洗澡、数值耦合、每日首喂双倍、陪伴天数、体型随阶段变化
- [x] **M3 感知**（2026-10-24）：键鼠监听、迎接/催休息、喝水久坐提醒（全屏延后）、静默模式
- [x] **M4 AI 对话 MVP**（2026-10-24）：接 grok-4.7（OpenAI 兼容），气泡聊天、persona+实时状态注入、滚动记忆、月度成本护栏、SSRF 防护
- [x] **M4.5 个人助理三件套**（2026-10-24）：对话式记事（自动抽时间+到期提醒+看记事）、日历 ICS 只读接入、番茄钟专注陪伴（缘缘安静陪坐）、主动搭话（低频+每日上限）
- [x] **M4.5-X 陪伴深化**（2026-10-25）：作息还原（教缘缘你的作息，她按节奏生活）、摸头部位互动
- [x] **M5 打磨**（2026-10-24）：内存 113→63MB、文件日志+单实例锁+崩溃自动重启、设置界面（AI/提醒/专注/体型/开机自启全 GUI）、便携包 `dist/YuanyuanPet-portable.zip`（42MB 解压即用）
- [x] **M6 开放创作·技术部分**（2026-10-25）：格式 v1.0 冻结、[创作指南](docs/创作指南.md)、zip 导入+切换宠物菜单、模板生成器 + 4 只示例宠物、LICENSE（MIT，代码开源/缘缘形象除外）、[发布清单](docs/发布清单-M6.md)
- [ ] 验收：真实使用 3 天 + 72h 稳定性观察；缘缘性格细节待补充
- [ ] M6 收尾：GitHub 仓库推送 + B 站演示视频 + 种子试用（见发布清单）

## 运行

```bash
python main.py                      # 默认加载 pets/ 下第一个包
python main.py --pack pets/yuanyuan # 指定缘缘
python main.py --smoke 15           # 冒烟测试：15 秒后自动退出并截图
```
