# 近期运行时修复与避坑（2026-11-14）

本页是制作时的约束，不是要求玩家完成的长验收表。按英雄实际涉及的功能检查；不能运行游戏时说明待试玩，不强制提供截图或录像。

## 已接入参考代码

- **母亲二阶段相机**：`scripts/aatrox_camera.lua` 在 POST_UPDATE 恢复原生相机焦点。只处理单人、本英雄、未暂停、人物存活且可操作、未清空的 Boss 房内活跃敌对 912.10 本体，等待其进入活动状态。沙漏加载时跳过；有自定义死亡/转场冻结时传入 frozen=true。不能把它扩展成每个房间永久锁相机，也不能只移动外部模型假装修复镜头。
- **镜中世界**：`aatrox_screen.lua` 在发送前变换世界位置和朝向。Lua 命中、寻路仍用世界坐标；鼠标到世界的逆变换只镜像一次。HUD、商店及屏幕鼠标不再镜像。手柄世界瞄准点显示另做屏幕变换。新增世界特效必须加入转换列表；模板函数不会自动理解自创遥测字段。房间矩形须反射后交换左右边界；原生遮挡掩模须反转每行并考虑矩形宽度，不能仅改模型位置。参考代码目前没有铁男专属房间/遮挡字段，不代表这些扩展已自动完成。
- **击飞**：保留传给原生渲染的 Vector 强引用，并在下一帧原位更新，避免只返回临时 userdata。只抬升贴图，不写实体 Position、SpriteOffset 或物理高度；短硬直保持原生实体和动画，不强行播放可能不存在的“击飞动画”。不要改变碰撞位置来配合视觉。位移中受击、连续命中、死亡、换房和沙漏回退需能结束。模板保留其既有抬升幅度；新英雄按玩家要求设置。此修复针对返回值生命周期，不声称已证明所有历史位移问题只有这一个原因。

## 按功能采用的经验

### 召唤、复活与沙漏

这些规则只适用于有召唤物的英雄，不要给所有英雄附加铁男军团。
存档重建实体可能改变 InitSeed，Lua GetData 也不保证跨原生还原存活；利用 REPENTOGON EntitySaveStateManager 持久化所有权，或使用经过验证的等价方案。记录父/生成者、派生投射物与 ExtraSource；原生 AI 可能生成 Parent/SpawnerEntity 都为空的子代，生成上下文必须限定在所属实体的更新范围，并及时清空。
回退按快照恢复并在有限时间内收敛，不要无限重扫或清除所有魅惑怪物。清理自己的后代前先收集身份；避免误删道具友军、其他玩家或其他 Mod 的实体。明确士兵击杀是否允许连锁复活，默认不要无界连锁。特殊怪物需要统一资格判断，覆盖拾取、直接召唤、存档载入和派生生成入口；铁男的 Bishop(805)、复活邪教徒(885.0)、黄蜘蛛(884) 排除经验可作参考，不能机械推广到所有设计。
接触伤害不能假设原生回调一定造成了伤害；必要的兜底需真实碰撞范围、节流、去重，原生已成功命中则不再补伤害。共享每帧敌人查询，避免每个士兵反复扫描房间。

### 商店与数值

合成候选超出可见数量时必须分页或滚动，绘制和点击使用同一个裁剪范围；选择变化后重置/夹紧偏移，首尾可达，窗口尺寸变化后边界正确。不能只裁切图片却仍接受区域外点击。保留旧 Companion 的遥测布局和行为；新增滚动条协议必须可选。
回血检查区分被动回血、吸血、装备等来源，保留小数，核对倍率只作用一次；不能根据低血量敌人死亡后 HUD 的整数变化就判断倍率失效。明确按实际伤害还是理论伤害计算，避免过量击杀伤害重复计入。不要把其他英雄的数值公式照搬过来。

### 配套、安装与交付

已经发布的英雄更新应兼容玩家现有 Companion，不能提高最低版本而让已有商店/HUD 失效，也不能静默重装配套绕过兼容要求。新英雄首次安装仍按自己的包提供安装步骤。旧配套不支持的新字段必须可选；无法兼容的改动明确报告，不能声称只更新 Mod 即可。
重复手动安装与工坊副本需避免双重回调、输入和光标绘制；清理仅针对可确认归属的旧安装，保留配置、存档和其他英雄。日志定位区分 Repentance 与 Repentance+，考虑重定向的 Documents；不能把“安装成功”当成渲染器已启动。
玩家 ZIP 顶层只放实际 Mod 文件夹，INSTALL.txt 与 CONSOLE-COMMANDS.txt 和 main.lua 同级。工坊上传使用干净暂存目录，不使用安装后的目录（可能含解压的 EXE/DLL/PYD）。保持各英雄 workshop ID 独立，不能沿用作者剑魔的 ID。原生 XML/资源检查在暂存成品上再做一次。

## 最小检查与报告

自动检查覆盖发生变化的逻辑、命名空间、导出文件清单和旧协议；试玩时只查本次相关场景：母亲二阶段镜头、镜面鼠标方向/技能对齐、移动怪物受击或商店边界。模拟通过与实际试玩分开写；未测试项如实列出，不扩大成强制全游戏验收。

## English summary

Preserve the included scoped Mother phase-2 native camera follow, mirror telemetry/input separation, and retained render-offset userdata. Extend reflection explicitly for new world-space events, room rectangles and silhouette masks; never mirror screen HUD/cursor twice. Pass custom transition/death freeze state to the camera guard. Summon ownership must survive native saves/rewinds and seed changes, include descendants, avoid unrelated allies, and bound reconciliation/damage fallback. Keep shop hit regions clipped with rendering and make overflow reachable. Separate healing sources and test fractional multipliers once. Preserve existing Companion compatibility; first-install instructions remain hero-specific. Package a clean workshop stage and a single-folder player ZIP. Run focused checks and honestly distinguish mock/offscreen tests from live play; screenshots/video are not mandatory.
