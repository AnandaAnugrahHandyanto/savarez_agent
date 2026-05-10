import { isMac, isRemoteShell } from '../lib/platform.js'

const action = isMac ? 'Cmd' : 'Ctrl'
const paste = isMac ? 'Cmd' : 'Alt'

const copyHotkeys: [string, string][] = isMac
  ? [
      ['Cmd+C', '复制选中'],
      ['Ctrl+C', '中断 / 清除草稿 / 退出']
    ]
  : isRemoteShell()
    ? [
        ['Cmd+C', '终端转发时复制选中'],
        ['Ctrl+C', 'copy selection / interrupt / clear draft / exit']
      ]
    : [['Ctrl+C', 'copy selection / interrupt / clear draft / exit']]

export const HOTKEYS: [string, string][] = [
  ...copyHotkeys,
  [action + '+D', '退出'],
  [action + '+G / Alt+G', '打开编辑器（VSCode/Cursor 用 Alt+G）'],
  [action + '+L', '重绘界面'],
  [paste + '+V / /paste', '粘贴文本；/paste 附加剪贴板图片'],
  ['Tab', '应用补全'],
  ['↑/↓', '补全 / 队列编辑 / 历史'],
  ['Ctrl+X', '删除正在编辑的队列消息（Esc 取消编辑）'],
  [action + '+A/E', '行首 / 行尾'],
  [action + '+Z / ' + action + '+Y', '撤销 / 重做输入'],
  [action + '+W', '删除单词'],
  [action + '+U/K', '删除到行首 / 行尾'],
  [action + '+←/→', '跳单词'],
  ['Home/End', '行首 / 行尾'],
  ['Shift+Enter / Alt+Enter', '插入换行'],
  ['\\+Enter', '多行续写（备用）'],
  ['!<cmd>', '运行 shell 命令（如 !ls、!git status）'],
  ['{!<cmd>}', '内联 shell 输出（如 "branch is {!git branch --show-current}"）']
]
