# 缘缘桌宠 (Yuanyuan Pet)

一只会陪伴、会对你有反应、会记得你的 AI 桌面小狗。以家里的小狗「缘缘」为原型。

## 文档

| 文档 | 内容 |
|---|---|
| [PRD-AI桌宠-缘缘.md](PRD-AI桌宠-缘缘.md) | 产品需求文档（唯一需求依据） |
| [docs/任务拆解与里程碑.md](docs/任务拆解与里程碑.md) | M1~M6 任务与验收标准 |
| [docs/宠物包格式规范-v0.md](docs/宠物包格式规范-v0.md) | 宠物包格式（引擎与创作者的合同） |
| [docs/缘缘宠物包设计.md](docs/缘缘宠物包设计.md) | 美术素材与状态映射 |
| [assets/缘缘-参考图/](assets/缘缘-参考图/) | 15 张原画参考 |

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

- [x] **M1 骨架完成（2026-10-24）**：缘缘已上桌！6 状态（idle/walk/dozy/sleep/excited/drag）、9 行为、开机问候、随机闲逛、重力弹跳、拖拽拎起、托盘菜单
- [x] 产品文档 + 设计文档（2026-10-24）
- [x] T1.1~T1.8 全部完成（详见任务拆解，含性能 PoC：整机 CPU 0.00%、内存 39MB）
- [ ] M2 养成：数值系统 → 时间演化 → 喂食互动 → 成长阶段

## 运行

```bash
python main.py                      # 默认加载 pets/ 下第一个包
python main.py --pack pets/yuanyuan # 指定缘缘
python main.py --smoke 15           # 冒烟测试：15 秒后自动退出并截图
```
