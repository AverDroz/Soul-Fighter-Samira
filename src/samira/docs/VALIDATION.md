# 验证与验收

使用项目自己的虚拟环境。不要依赖原作者的 Codex 路径、旁边的其他 Mod 工程或开发机 PATH。

```powershell
.\.venv\Scripts\python.exe tools/check_project.py
.\.venv\Scripts\python.exe tools/test.py
.\.venv\Scripts\python.exe external/test_bridge.py
.\.venv\Scripts\python.exe external/test_status.py
.\.venv\Scripts\python.exe external/test_visibility.py
.\.venv\Scripts\python.exe companion/test_installer.py
```

上述 Lua 测试大部分验证**剑魔参考行为**，包括固定动作数量和伤害预期。新英雄机制不同，应以对应设计更新测试，不要直接删掉失败断言来获得“全绿”。`check_project.py` 也保留了原始剑魔片段名检查；更换 GLB 后应改为新资源要求。

有 GPU 时运行相关离屏测试：

```powershell
.\.venv\Scripts\python.exe external/overlay.py --self-test
.\.venv\Scripts\python.exe external/test_transition_render.py
.\.venv\Scripts\python.exe external/test_damage_screen.py
```

这些测试不启动/控制实际游戏。创建新英雄后应建立与它有关的命中、动作、特效测试。不要反复重跑所有昂贵检查，先跑改动相关项，再在发布前做一轮总验收。

## 新英雄复用时的短检查

- 模块依赖在初始化时加载并保留引用；不要在装备恢复、属性计算或伤害回调里首次 `include`。命名空间必须覆盖装备、金身、伤害与存档的数据键，不能只改文件名。
- 测试技能的实际命中结算，不只测试按键返回成功。长条、扇形、圆形范围分别使用自己的参数；碎石逻辑不能假设所有英雄 Q 都有圆心和半径。
- 原生资源先运行 `check_native_resources.py`；特别是 `items.xml` 的 `version` 和 `gfxroot`，Lua 语法检查无法发现引擎读 XML 时的崩溃。
- 特效的 SKN/SKL/ANM 组合需要骨骼动画，不能退化为通用白色四边形。地下网格、模板测试和实机遮挡分别验证；外部叠加层不自动拥有游戏的深度缓冲。

Check actual impact/terrain paths, initialize module dependencies before callbacks, validate native XML, and preserve animated particle mesh semantics. If live testing is unavailable, report that plainly and provide short player test steps; screenshots/recordings are not mandatory evidence.

## 必须在游戏中确认

| 场景 | 验收点 |
|---|---|
| 进入/退出角色 | 原来的 REPENTOGON 启动方式可用；自动接管；其他角色正常 |
| 反复换房、传送、rewind | 不重刷房间，不跨房间插值瞬移，无多层人物或 HUD 闪烁 |
| 暂停、黑屏、下层、CG | 人物不盖在过场上；回退和外部模型不会同时出现 |
| 技能、普攻、被动 | 指示器、动画接触点、伤害帧一致，攻速/范围属性有效 |
| 拾取/卖出/撤回装备 | 属性与衍生物同步撤销，不复制金币/血量 |
| 原生道具和控制 | 主动、卡牌、炸弹、长按 Ctrl、手柄、飞行、变大变小 |
| 语言与分辨率 | 中英文字和语音，窗口/无边框/不同缩放，鼠标恢复 |
| Companion 缺失或退出 | 原生回退可玩；恢复后只在确认就绪时接管 |
| 安装/修复/更新/卸载 | 只操作本英雄文件，不删除游戏、其他 Mod、存档 |

模板的独立命名空间减少冲突，但不替代多 Mod 同开验证。尤其共享的引擎菜单资源、全局音乐和鼠标显示等需要在目标组合中验证。多人/合作模式没有通用外部多角色渲染实现。

交付说明列明：自动测试、离屏 GPU、实际游戏分别测过哪些；剩余问题和不支持的场景。不要把三个级别混为一谈。
