# Codex Windows Manager

这是一个给 Windows 用的 Codex 多账号管理/切换工具，现在包含两种入口：
- 命令行版：`codex_windows_manager.py`
- 小窗口 GUI 版：`codex_windows_manager_gui.py`

它的设计目标很直接：
- 先用 `codex login` 登录某个账号
- 再把当前 `.codex/auth.json` 导入到本地账号池
- 以后通过脚本或小窗口一键切换不同账号
- 切换本质上是重写当前用户的 `.codex/auth.json`

适合场景：
- 一台 Windows 电脑上要频繁切多个 Codex 账号
- 不想每次都重新扫码/重新登录
- 想保留多个账号快照，按邮箱、label、序号切换

安全提醒：
- 这个脚本会把多个账号的 token 保存在本机 `%APPDATA%\\CodexAccountManager\\accounts.json`
- 当前版本是明文 JSON 存储，不是 DPAPI/凭据管理器加密版
- 所以只建议在你自己可控的 Windows 账号环境里使用，不要放在多人共用机器上
- 切号时会直接覆盖当前 `.codex/auth.json`

不做的事：
- 这个 Windows 版脚本目前不负责完整 OAuth 登录流程
- 它是“导入当前登录态 + 管理 + 切换”模式

也就是说，第一次录入某个账号时，先手动执行：

```powershell
codex login
```

然后再导入：

```powershell
python codex_windows_manager.py add
```

或者如果你已经把别处的 `auth.json` 拷过来了：

```powershell
python codex_windows_manager.py add --auth-file D:\tmp\auth.json --label work-1
```

## 存储位置

默认会使用这些 Windows 路径：

- 账号池：`%APPDATA%\CodexAccountManager\accounts.json`
- 状态文件：`%APPDATA%\CodexAccountManager\state.json`
- 当前 Codex 登录态：`%USERPROFILE%\.codex\auth.json`

如果设置了 `CODEX_HOME`，则当前登录态改为：

- `%CODEX_HOME%\auth.json`

## 命令

### 1. 导入当前账号

```powershell
python codex_windows_manager.py add
python codex_windows_manager.py add --label main
python codex_windows_manager.py add --auth-file D:\tmp\auth.json --label backup
```

说明：
- 会读取当前 `auth.json`
- 尝试从 `id_token` / `access_token` 里识别邮箱
- 若识别到邮箱，会默认拿邮箱当 label
- 导入后会自动把它设成当前活动账号

### 2. 查看账号列表

```powershell
python codex_windows_manager.py list
python codex_windows_manager.py list --json
```

### 3. 切换账号

支持这些目标：
- 序号
- id
- 邮箱
- label

例子：

```powershell
python codex_windows_manager.py switch 1
python codex_windows_manager.py switch 8f2c1a3b
python codex_windows_manager.py switch you@example.com
python codex_windows_manager.py switch main
```

切换后会直接重写当前用户的 `.codex/auth.json`。

### 4. 删除账号

```powershell
python codex_windows_manager.py remove 1
python codex_windows_manager.py remove you@example.com
```

### 5. 检查当前状态

```powershell
python codex_windows_manager.py doctor
python codex_windows_manager.py doctor --json
```

它会检查：
- 本地账号池里谁是活动账号
- 当前 `.codex/auth.json` 是否存在
- 当前 `.codex/auth.json` 是否和活动账号一致

## 图形界面（GUI）

如果你更想点按钮，不想敲命令，现在可以直接用 Tkinter 小窗口版：

```powershell
python codex_windows_manager_gui.py
```

如果已经安装成脚本入口，也可以直接运行：

```powershell
codex-windows-manager-gui
```

仓库里还带了一个 BAT 启动器：

```text
scripts\codex-windows-manager-gui.bat
```

GUI 版目前支持：
- 查看账号列表
- 高亮当前活动账号
- 导入当前登录态（支持预填或手选 auth.json）
- 一键切换选中账号
- 删除选中账号
- 右侧实时显示 doctor 诊断结果
- 一键复制当前 `.codex/auth.json` 路径

提示：GUI 版本质上复用的还是同一套底层逻辑，所以和命令行版用的是同一份账号池与状态文件。

## BAT 启动器

仓库里带了两个 Windows 启动器：

```text
scripts\codex-windows-manager.bat
scripts\codex-windows-manager-gui.bat
```

命令行版用法示例：

```cmd
codex-windows-manager.bat list
codex-windows-manager.bat add
codex-windows-manager.bat switch you@example.com
```

GUI 版用法示例：

```cmd
codex-windows-manager-gui.bat
codex-windows-manager-gui.bat --auth-file D:\tmp\auth.json
```

这两个 bat 都会优先调用：
- `py -3`
- 否则回退 `python`

## 推荐使用流程

第一次收录一个新账号：

```powershell
codex login
python codex_windows_manager.py add
```

切到另一个账号：

```powershell
python codex_windows_manager.py list
python codex_windows_manager.py switch 2
```

切完后验证：

```powershell
codex login status
```

提示：上面的 `.bat` 启动器是仓库内附带的便捷脚本；如果你是用打包/安装方式分发，优先直接使用 `codex-windows-manager` / `codex-windows-manager-gui` 这两个 Python 入口。

如果你后面还想继续往下做，小哈建议下一步补：
- PyInstaller 打包成 EXE 的说明或一键打包脚本
- Windows DPAPI / Credential Manager 加密存储，别再明文放 token
