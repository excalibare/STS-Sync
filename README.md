# STS Sync

`STS Sync` 是一个本地命令行工具，用于在 Windows PC 与 Android 平板之间，通过 ADB 半自动同步《杀戮尖塔》（Slay the Spire）存档。

[↓ 省流用法](#省流用法)

工具设计重点：

- 优先同步 `preferences`
- `saves` 不会被 `sync-safe` 自动同步
- `push-save` 默认需要 `--force`
- 每次 `pull` / `push` / `sync-safe` 前后都会备份
- 备份以压缩文件形式保存，减少空间占用
- 本地重要目录使用临时目录 + 原子替换，尽量避免损坏
- 仅依赖 Python 标准库与 ADB，不做游戏内模组，不依赖 root

## 目录结构

```text
sts_syn/
├── README.md
├── config.example.json
├── launch_gui.bat
└── sts_syn/
    ├── __init__.py
    ├── __main__.py
    ├── adb_client.py
    ├── backup.py
    ├── config.py
    ├── file_ops.py
    ├── gui.py
    ├── main.py
    ├── manifest.py
    ├── models.py
    ├── service.py
    ├── commands/
    │   ├── __init__.py
    │   ├── status.py
    │   ├── sync_ops.py
    │   └── sync_safe.py
    ├── ui/
    │   ├── __init__.py
    │   └── main_window.py
    └── utils/
        ├── __init__.py
        ├── logging_utils.py
        └── time_utils.py
```

## 环境要求

此项目只在以下环境中运行正常，其他环境还请自行适配

- Windows 11
- Python 3.11.5
- Android Debug Bridge version 1.0.41 （Version 36.0.2-14143358）

## 安装 Python

1. 打开 [Python 官网](https://www.python.org/downloads/windows/)
2. 安装 Python 3.11 或更新版本
3. 安装时勾选 `Add python.exe to PATH`
4. 在 PowerShell 中确认：

```powershell
python --version
```

## 安装 ADB / platform-tools

1. 从 [Android SDK Platform Tools](https://developer.android.com/studio/releases/platform-tools) 下载 Windows 版本
2. 解压到例如 `C:\Program Files\platform-tools`
3. 把 `adb.exe` 所在目录加入系统 `PATH`，或在配置文件里写入完整路径
4. 确认：

```powershell
adb version
```

## 开启 Android USB 调试

1. 在 Android 平板中打开“开发者选项”
2. 开启“USB 调试”
3. 用 USB 线连接 PC
4. 在设备上允许本机调试授权
5. 再执行：

```powershell
adb devices
```

首次建议优先使用 USB 调试，确认稳定后再考虑未来扩展到无线 ADB。无线 ADB 不是本项目的必需功能，但当前代码结构保留了以后扩展的空间。

## 配置文件

复制 `config.example.json` 为 `config.json`，按你的实际路径修改。

```powershell
Copy-Item .\config.example.json .\config.json
```

推荐配置项：

- `adb_path`
- `device_serial`
- `pc_root`
- `pc_preferences_dir`
- `pc_saves_dir`
- `pc_runs_dir`
- `android_root`
- `android_preferences_dir`
- `android_saves_dir`
- `android_runs_dir`
- `android_root_candidates`
- `backup_root`
- `temp_root`
- `log_root`
- `backup_keep`

示例配置见项目根目录 `config.example.json`。

## 运行 status

```powershell
python -m sts_syn --config .\config.json status
```

`status` 会显示：

- 是否检测到 `adb`
- 是否检测到设备
- Android 根目录是否存在
- PC 目录是否存在
- `preferences` / `saves` / `runs` 的存在情况
- 文件数量
- 最近修改时间（能取到时显示）

## 运行 pull-progress / push-progress

```powershell
python -m sts_syn --config .\config.json pull-progress
python -m sts_syn --config .\config.json push-progress
```

这两个命令只处理 `preferences`，适合长期进度同步。

只预览执行步骤：

```powershell
python -m sts_syn --config .\config.json --dry-run pull-progress
```

## 运行 pull-save / push-save

```powershell
python -m sts_syn --config .\config.json pull-save
python -m sts_syn --config .\config.json push-save --force
```

注意：

- `saves` 代表当前进行中的对局
- 不建议自动同步 `saves`
- `push-save` 默认会阻止执行，必须加 `--force`
- 如果本地或安卓端存在 `saves`，日志会给出明显警告
- 强烈建议同步前先退出游戏，避免覆盖正在写入的存档

## 运行 pull-runs / push-runs

```powershell
python -m sts_syn --config .\config.json pull-runs
python -m sts_syn --config .\config.json push-runs
```

`runs` 优先级低于 `preferences`，通常用于历史记录同步。

## 运行 sync-safe

```powershell
python -m sts_syn --config .\config.json sync-safe
```

`sync-safe` 只同步 `preferences`，并执行：

- 预检 ADB / 设备
- 备份 Android 与 PC 对应目录
- 从 Android 拉取到临时目录
- 原子替换 PC 本地目录
- 结果写入 `manifest.json`
- 执行后置备份

## GUI 用法

现在支持一个简单的 Windows Tkinter GUI：

```powershell
python -m sts_syn --config .\config.json gui
```

GUI 主窗口包含：

- 当前配置文件路径
- ADB 状态
- 设备状态
- Android 路径状态
- PC 路径状态
- 多行日志输出框

主按钮：

- 检测设备
- pull-progress
- push-progress
- sync-safe

次按钮：

- pull-save
- push-save
- 打开日志目录
- 打开备份目录

说明：

- GUI 启动时会自动做一次轻量检测
- 所有 ADB / 同步操作都在后台线程执行，不会卡住主窗口
- 操作进行中会暂时禁用按钮
- `push-save` 会先弹两次确认框，且底层仍走原有危险保护与备份逻辑
- 如果检测到多台设备，会提示你先在下拉框选择 serial

## 单独执行全量备份

```powershell
python -m sts_syn --config .\config.json backup
```

备份目录结构类似：

```text
backups/
└── 2026-04-01_213000_pull-progress/
    ├── pre.zip
    ├── post.zip
    └── manifest.json
```

`backup` 子命令则会对 `preferences` / `saves` / `runs` 三类目录都做快照，并写入：

```text
backups/
└── 2026-04-01_213000_backup/
    ├── snapshot.zip
    └── manifest.json
```

压缩包内部仍保持清晰结构，例如：

```text
pc/preferences/...
android/preferences/...
android/saves/...
```

## 日志与 manifest

- 控制台日志：实时显示
- 文件日志：`logs/sts_sync.log`
- 每次实际同步后会在对应备份目录写入 `manifest.json`
- 每个备份阶段会保存为 `pre.zip` / `post.zip` / `snapshot.zip`

日志会记录：

- 执行时间
- 命令名
- 设备 serial
- 操作结果
- 异常信息

## 常见错误排查

### 1. `adb` 未找到

- 确认 `adb.exe` 已安装
- 确认 `adb_path` 正确，或已经加入系统 `PATH`

### 2. `adb devices` 看不到设备

- 确认 USB 调试已开启
- 确认设备弹出的授权提示已经点击允许
- 可以尝试重新插拔 USB，或执行：

```powershell
adb kill-server
adb start-server
adb devices
```

### 3. Android 11+ 无法访问 `Android/data`

Android 11+ 对 `Android/data` 访问限制更严格，不同设备 ROM 行为可能存在差异。此工具依赖 ADB 访问对应目录，若设备系统限制较强，可能出现目录不可见或拉取失败。

建议：

- 优先使用 USB 连接进行调试
- 在 `status` 中先确认目录存在
- 在配置文件中尝试调整 `android_root`
- 必要时使用 `android_root_candidates` 做自动探测

### 4. 同步后进度异常

- 先检查 `backups/` 中对应时间戳目录
- 解压查看 `pre.zip` / `post.zip` / `snapshot.zip`
- 查看 `logs/sts_sync.log`
- 优先把 `preferences` 作为长期进度同步对象
- 尽量不要频繁自动覆盖 `saves`

### 5. 建议的使用习惯

- 同步前先退出 PC 和 Android 端游戏
- 长期进度优先同步 `preferences`
- `saves` 仅在你明确知道自己要覆盖当前对局时，才使用 `push-save --force`
- 首次先用 `status` 和 `pull-progress` 验证流程

# 省流用法

## cli 用法

```powershell
python -m sts_syn --config .\config.json pull-progress
python -m sts_syn --config .\config.json push-progress
```

## 双击启动 GUI

项目根目录新增了 `launch_gui.bat`，双击即可启动：

```text
launch_gui.bat
```

默认它会使用项目根目录下的 `config.json`：

```batch
python -m sts_syn --config "%~dp0config.json" gui
```

如果你还没有 `config.json`，请先从 `config.example.json` 复制一份再修改。
