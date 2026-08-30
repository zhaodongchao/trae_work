# Windows 系统垃圾清理工具

一款适用于 **Windows 10 / Windows 11** 的图形化系统垃圾清理工具，基于 Python 标准库 **tkinter** 开发，无需额外安装第三方依赖即可直接运行。

## 功能特性

- **多线程异步扫描**：不阻塞 UI，实时统计垃圾大小与文件数量。
- **分类展示**：树形列表展示每一类垃圾，支持勾选/取消勾选，默认全部选中。
- **详情展开**：点击分类项可查看部分样例文件路径。
- **二次确认**：清理前弹窗汇总本次清理范围、文件数量、占用空间，必须手动确认才执行删除。
- **实时进度**：进度条 + 当前处理文件路径实时刷新。
- **运行日志**：实时记录扫描与清理动作，支持导出为 txt 文件。
- **异常安全**：自动跳过被占用、权限不足的文件；不删除用户文档、桌面等重要数据；回收站单独提示。

## 扫描范围

| 分类 | 说明 |
|------|------|
| 用户临时文件 (%TEMP%) | 当前用户临时目录 |
| Windows 系统临时文件 | `C:\Windows\Temp` |
| Edge 浏览器缓存 | Edge 默认配置缓存 |
| Chrome 浏览器缓存 | Chrome 默认配置缓存 |
| 浏览器下载缓存 | 下载临时文件 |
| 回收站 | `C:\$Recycle.Bin` |
| 系统与应用程序日志 | `.log` 等日志文件 |
| Windows 更新缓存 | `C:\Windows\SoftwareDistribution\Download` |
| 缩略图缓存 | Windows 资源管理器缩略图数据库 |

## 环境要求

- Python 3.8 或更高版本
- Windows 10 / Windows 11
- 清理部分系统目录（如 `C:\Windows\Temp`、Windows 更新缓存）可能需要管理员权限

## 依赖安装

本工具使用 tkinter（Python 标准库），通常无需安装依赖：

```bash
# 验证 tkinter 是否可用
python -c "import tkinter; print(tkinter.Tcl().eval('info version'))"
```

如需打包成 exe，请安装 PyInstaller：

```bash
pip install pyinstaller
```

## 运行方式

### 直接运行源码

```bash
python system_clear.py
```

### 使用一键打包脚本（推荐）

双击运行 `build.bat`，脚本会自动创建虚拟环境、安装依赖并打包：

```bash
build.bat
```

打包完成后，可执行文件位于：

```text
dist/SystemClear.exe
```

### 手动 PyInstaller 打包

```bash
pyinstaller --onefile --noconsole --name SystemClear --clean system_clear.py
```

如需添加图标：

```bash
pyinstaller --onefile --noconsole --name SystemClear --icon icon.ico --clean system_clear.py
```

## 文件说明

```text
common_util/system_clear/
├── system_clear.py    # 主程序源码
├── build.py           # Python 打包脚本
├── build.bat          # Windows 一键打包批处理
├── requirements.txt   # 可选依赖（主要用于打包）
└── README.md          # 使用说明
```

## 风险提示

1. **建议先关闭占用临时文件的软件**（如浏览器、下载工具、Office 等），否则部分文件可能因被占用而无法清理。
2. 清理回收站会**永久删除**其中的文件，无法恢复，请提前确认。
3. 本工具**不会**扫描或删除用户的文档、桌面、图片、下载等个人数据目录，请放心使用。
4. 清理 `C:\Windows\Temp`、Windows 更新缓存等系统目录时，建议以管理员身份运行程序，否则可能因权限不足而跳过。

## 代码结构

- `AppLogger`：日志记录与导出。
- `JunkScanner`：垃圾文件扫描，支持多分类与样例收集。
- `JunkCleaner`：安全删除文件，异常捕获与回收站特殊处理。
- `SystemClearApp`：tkinter 主界面与交互逻辑。
