# 开发、打包与玩家安装

## 开发环境

Python 3.12 x64 和 `requirements-dev.txt` 是开发者依赖；玩家使用配套包私有运行时，不需要自行安装 Python/Codex。
手动运行渲染器时显式传入游戏日志路径、与 Lua 相同的握手目录：

```powershell
.\.venv\Scripts\python.exe external/overlay.py --log "D:\MySaves\log.txt" --status-dir "D:\SteamLibrary\steamapps\common\The Binding of Isaac Rebirth\data\riven_external_link" --offset 0
```

上面只是示例路径和 `riven` 示例 ID；必须替换为玩家真实路径。生产安装由 Companion 根据游戏保存路径自动处理。

## 安装开发 Mod

关闭游戏后执行（只有明确这一步才会写游戏目录）：

```powershell
.\.venv\Scripts\python.exe tools/install_mod.py --game "D:\SteamLibrary\steamapps\common\The Binding of Isaac Rebirth"
```

工具检查 REPENTOGON、游戏是否关闭以及目标身份，备份被覆盖文件并逐文件校验 SHA256，不删除目标中未知文件。游戏测试应另建测试存档；该命令不会替你创建存档。

## 构建自己的 Companion

模板不重复附带私有 Python/字体包和 Zig。可以复用完整解压的 Aatrox Companion **0.7.53 / protocol 1** 作为依赖来源，但**不能直接给新英雄安装原版剑魔 Companion**：它仍识别剑魔的前缀。

准备：

- 一份完整解压、含 `manifest.json` / `payload` 的 Companion 包（剑魔 Mod 中的 `Aatrox-Companion.zip`）。
- Zig 0.13.0 的 Windows x64 编译器，用于编译 REPENTOGON x86 桥接 DLL。
- Windows .NET Framework 的 `csc.exe`（构建脚本使用 Framework/v4.0.30319），用于维护界面。
- 更新 `hero.json` 的 `version`，同时更新 Mod metadata 和遥测版本。不要修改已有发布包。

```powershell
.\.venv\Scripts\python.exe tools/build_release.py --runtime-package "D:\Dependencies\Aatrox-Companion" --zig "D:\Tools\zig-0.13.0\zig.exe" --output "D:\Releases\Riven-Companion-0.1.0"
```

脚本校验依赖包所有文件，复用 Python/字体及其许可证，编译本英雄专属 DLL/安装器，并装入当前渲染源码与素材。输出目录必须不存在。它不会联网下载、不安装到游戏、不启动游戏。

输出中有 `<Name>Setup.exe`、`installer.py`、`manifest.json`、`payload/` 和 ZIP。维护界面保留安装、修复、更新、回退和卸载。要显式安装构建出的新包，可以运行其安装 EXE；Agent 也可使用：

```powershell
.\.venv\Scripts\python.exe companion/installer.py --action install --game "D:\SteamLibrary\steamapps\common\The Binding of Isaac Rebirth" --package "D:\Releases\Riven-Companion-0.1.0"
```

已有同英雄版本用 `--action update`。不要绕过安装器直接改运行目录，否则哈希、修复和更新记录会不一致。

## 给玩家的最终文件

将新英雄的 Companion ZIP 和一份安装说明放在新英雄 Mod 根目录。玩家订阅/下载 Mod，首次解压并运行自己的安装器，以后仍从原来的 REPENTOGON 启动器进入游戏。Steam 更新 Mod 不等于自动运行新的 Companion 安装器；更新时要明确告知玩家两部分的版本要求。

开发源码模板可以单独发布，避免每个玩家都下载开发文件。发布前保留 `EID-CREDITS.txt`、素材来源和运行时许可证，不把开发日志、存档、测试安装目录、原版 LoL 客户端或个人机器路径打进去。

## 今后的共享宿主

此模板不包含通用多英雄宿主。将来若实现：应统一安装标识、显式携带 `heroId`、按角色加载资产、维护单一窗口和输入所有者、版本化能力协商，并提供旧版迁移方案。这是独立的后续工程，不需要为了完成第一个参考分支现在重写现有剑魔。

## Native resource check / 原生资源检查

Run `python tools/check_native_resources.py mod` before packaging, and run the same checker on the final staged mod folder. Unused music.xml must be removed, not replaced with `<music />`; Isaac requires its root attribute even when there are no tracks. Verify every registered music/sound file. Use fresh staging directories so removed configs do not survive. For upgrades, document removal of obsolete files; ZIP overwrite alone does not delete them. These checks do not prove a successful live startup.

打包前及最终暂存目录各运行一次上述检查。没有自定义音乐就删除 music.xml，不要写成 `<music />`；检查注册音频是否齐全。使用新暂存目录，升级时明确清理废弃配置，单纯覆盖 ZIP 不会删除旧文件。检查通过不等于游戏启动已验证。

## 玩家 ZIP 目录 / Player ZIP layout
ZIP 顶层只能有实际 Mod 文件夹（如 yasuo_isaac），不要用 Yasuo-in-Isaac-0.1.4 再套一层。INSTALL.txt、CONSOLE-COMMANDS.txt 和 Companion ZIP 都在里面，与 main.lua 同级。若解压软件自动生成压缩包名称目录，玩家只需要把内层实际 Mod 文件夹放到 mods。
The archive has one top-level actual mod directory (e.g. yasuo_isaac), containing main.lua, INSTALL.txt, CONSOLE-COMMANDS.txt and the Companion ZIP. Do not add a release-name wrapper. If the extraction app adds one, move only the inner mod folder into mods.

python tools/package_player.py --mod mod --mod-name riven_isaac --companion dist/Riven-Companion.zip --install INSTALL.txt --commands CONSOLE-COMMANDS.txt --output dist/Riven-in-Isaac.zip

此工具会检查单一顶层、main.lua 和内置说明。仍需按上节检查原生资源，安装说明使用本英雄实际文件名。
The helper validates the single top-level folder, main.lua and nested instructions. Also run the native resource check above and use the real hero filenames in instructions.


content/items.xml 即使只注册复活用的 null 效果，根节点也必须写成 <items gfxroot="gfx/items/" version="1">，不能省略 version 或 gfxroot；缺少 version 会在 Lua 加载前导致原生崩溃。
Even a null-only content/items.xml must use <items gfxroot="gfx/items/" version="1">. Do not omit version or gfxroot; missing version crashes the native loader before Lua runs.
最终成品打包和安装脚本会自动运行资源检查，检查失败必须修正后再交付，不要跳过检查。
The final player packager and mod installer run resource checks automatically; fix failures before delivery rather than bypassing the check.

## 黑屏兼容模式 / Black-screen compatibility

新英雄模板包含标准 glfw 与 layered 兼容渲染两条路径。保持 external/presentation.json、layered_surface.py、overlay.py 的参数/渲染/隐藏/释放分支，以及 Companion 的 display_arguments 和安装器模式保存完整。构建清单必须声明 displayModes 并包含默认配置；build_release.py 在构建前运行 check_display_support.py，缺少接入时直接失败。

玩家模型和 UI 正常但地图黑屏时：关闭游戏，从包含兼容支持的新配套 ZIP 完整解压，运行安装器，选择黑屏兼容模式并更新；已有支持的版本可使用“应用显示方式”。显示正常的玩家保持标准模式，无需仅为此重新安装。旧版配套不能仅添加清单标记：渲染器也必须实现对应路径。升级不应覆盖玩家已选择的模式。

The template includes both standard GLFW and layered compatibility presentation. Keep CLI forwarding, renderer lifecycle, presentation.json, installer preference persistence and manifest displayModes connected. The release builder checks source wiring before packaging. For a black map with a working model/HUD, close Isaac and update from a complete compatible Companion package with Black-screen compatibility selected. Working installations do not need to switch modes. Mock/offscreen checks do not prove compatibility on the affected player's GPU.
