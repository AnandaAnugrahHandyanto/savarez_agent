#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import codex_windows_manager as manager_mod

APP_NAME = "codex-windows-manager-gui"


class CodexWindowsManagerController:
    def __init__(self, manager=manager_mod):
        self.manager = manager

    def load_rows(self) -> list[dict[str, Any]]:
        return list(self.manager._rows_for_display())

    def add_current_account(self, label: str | None = None, auth_file: str | Path | None = None):
        auth_path = Path(auth_file) if auth_file else None
        return self.manager.add_current_account(label=label, auth_path=auth_path)

    def switch_by_row_index(self, row_index: int):
        rows = self.load_rows()
        if not 0 <= row_index < len(rows):
            raise self.manager.ManagerError("请选择一个有效账号。")
        return self.manager.switch_account(rows[row_index]["id"])

    def remove_by_row_index(self, row_index: int):
        rows = self.load_rows()
        if not 0 <= row_index < len(rows):
            raise self.manager.ManagerError("请选择一个有效账号。")
        return self.manager.remove_account(rows[row_index]["id"])

    def doctor_payload(self) -> dict[str, Any]:
        return dict(self.manager.doctor())

    def doctor_summary(self) -> str:
        payload = self.doctor_payload()
        active = payload.get("active_account") or {}
        lines = [
            f"检查时间：{payload.get('checked_at', '-')}",
            f"账号总数：{payload.get('account_count', 0)}",
            f"活动账号：{active.get('email') or active.get('label') or '无'}",
            f"Codex auth 文件：{'存在' if payload.get('codex_auth_present') else '不存在'}",
            f"活动账号一致性：{'一致' if payload.get('codex_auth_matches_active') else '不一致'}",
        ]
        if payload.get("codex_auth_error"):
            lines.append(f"读取错误：{payload['codex_auth_error']}")
        return "\n".join(lines)


class CodexWindowsManagerGUI:
    def __init__(self, controller: CodexWindowsManagerController, prefill_auth_file: str | None = None):
        import tkinter as tk
        from tkinter import filedialog, messagebox, ttk

        self.tk = tk
        self.ttk = ttk
        self.filedialog = filedialog
        self.messagebox = messagebox
        self.controller = controller
        self.root = tk.Tk()
        self.root.title("Codex 账号管理器")
        self.root.geometry("860x520")
        self.root.minsize(760, 420)

        self.label_var = tk.StringVar()
        self.auth_file_var = tk.StringVar(value=prefill_auth_file or "")
        self.status_var = tk.StringVar(value="准备好了。先手动 codex login，再点“导入当前登录态”。")

        self.tree = None
        self.status_text = None
        self._build_layout()
        self.refresh_rows(select_active=True)
        self.refresh_doctor()

    def _build_layout(self):
        root = self.root
        ttk = self.ttk

        frame = ttk.Frame(root, padding=12)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(0, weight=3)
        frame.columnconfigure(1, weight=2)
        frame.rowconfigure(1, weight=1)
        frame.rowconfigure(3, weight=1)

        top = ttk.LabelFrame(frame, text="导入当前 Codex 登录态", padding=10)
        top.grid(row=0, column=0, columnspan=2, sticky="nsew", pady=(0, 10))
        top.columnconfigure(1, weight=1)

        ttk.Label(top, text="备注 / Label").grid(row=0, column=0, sticky="w")
        ttk.Entry(top, textvariable=self.label_var).grid(row=0, column=1, sticky="ew", padx=(8, 8))
        ttk.Button(top, text="浏览 auth.json", command=self.choose_auth_file).grid(row=0, column=2, sticky="ew")

        ttk.Label(top, text="导入文件").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(top, textvariable=self.auth_file_var).grid(row=1, column=1, sticky="ew", padx=(8, 8), pady=(8, 0))
        ttk.Button(top, text="导入当前登录态", command=self.handle_add).grid(row=1, column=2, sticky="ew", pady=(8, 0))

        left = ttk.LabelFrame(frame, text="账号列表", padding=10)
        left.grid(row=1, column=0, sticky="nsew", padx=(0, 10))
        left.columnconfigure(0, weight=1)
        left.rowconfigure(0, weight=1)

        columns = ("active", "index", "email", "label", "id", "source")
        tree = ttk.Treeview(left, columns=columns, show="headings", selectmode="browse")
        self.tree = tree
        headings = {
            "active": "当前",
            "index": "序号",
            "email": "邮箱",
            "label": "Label",
            "id": "ID",
            "source": "来源",
        }
        widths = {"active": 55, "index": 55, "email": 210, "label": 180, "id": 120, "source": 120}
        for key in columns:
            tree.heading(key, text=headings[key])
            tree.column(key, width=widths[key], anchor="w")
        tree.grid(row=0, column=0, sticky="nsew")
        tree.bind("<<TreeviewSelect>>", lambda _event: self.refresh_doctor())

        scrollbar = ttk.Scrollbar(left, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.grid(row=0, column=1, sticky="ns")

        buttons = ttk.Frame(left)
        buttons.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        for i in range(4):
            buttons.columnconfigure(i, weight=1)
        ttk.Button(buttons, text="刷新", command=self.refresh_rows).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ttk.Button(buttons, text="切换选中账号", command=self.handle_switch).grid(row=0, column=1, sticky="ew", padx=6)
        ttk.Button(buttons, text="删除选中账号", command=self.handle_remove).grid(row=0, column=2, sticky="ew", padx=6)
        ttk.Button(buttons, text="复制当前 auth 路径", command=self.copy_auth_path).grid(row=0, column=3, sticky="ew", padx=(6, 0))

        right = ttk.LabelFrame(frame, text="诊断 / Doctor", padding=10)
        right.grid(row=1, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.rowconfigure(0, weight=1)

        text = tk.Text(right, wrap="word", height=16)
        self.status_text = text
        text.grid(row=0, column=0, sticky="nsew")
        text.configure(state="disabled")
        right_scroll = ttk.Scrollbar(right, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=right_scroll.set)
        right_scroll.grid(row=0, column=1, sticky="ns")
        ttk.Button(right, text="刷新诊断", command=self.refresh_doctor).grid(row=1, column=0, sticky="ew", pady=(10, 0))

        bottom = ttk.Label(frame, textvariable=self.status_var, relief="sunken", anchor="w")
        bottom.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(10, 0))

    def choose_auth_file(self):
        path = self.filedialog.askopenfilename(
            title="选择要导入的 auth.json",
            filetypes=[("JSON 文件", "*.json"), ("所有文件", "*.*")],
        )
        if path:
            self.auth_file_var.set(path)

    def _selected_row_index(self) -> int:
        selection = self.tree.selection()
        if not selection:
            raise self.controller.manager.ManagerError("请先在左侧列表选中一个账号。")
        item_id = selection[0]
        row_index = self.tree.index(item_id)
        return int(row_index)

    def refresh_rows(self, select_active: bool = False):
        rows = self.controller.load_rows()
        selected_active_iid = None
        current_selection = self.tree.selection()
        selected_iid = current_selection[0] if current_selection else None
        selected_values = self.tree.item(selected_iid, "values") if selected_iid else None
        selected_account_id = selected_values[4] if selected_values and len(selected_values) > 4 else None

        for item in self.tree.get_children():
            self.tree.delete(item)

        fallback_iid = None
        for index, row in enumerate(rows):
            iid = self.tree.insert(
                "",
                "end",
                values=(
                    "是" if row["active"] else "",
                    row["index"],
                    row["email"] or "",
                    row["label"],
                    row["id"],
                    row["source"],
                ),
            )
            if fallback_iid is None:
                fallback_iid = iid
            if row["active"]:
                selected_active_iid = iid
            if selected_account_id and row["id"] == selected_account_id:
                fallback_iid = iid

        chosen_iid = None
        if select_active and selected_active_iid:
            chosen_iid = selected_active_iid
        elif fallback_iid:
            chosen_iid = fallback_iid
        if chosen_iid:
            self.tree.selection_set(chosen_iid)
            self.tree.focus(chosen_iid)
        self.status_var.set(f"已加载 {len(rows)} 个账号。")
        return rows

    def refresh_doctor(self):
        summary = self.controller.doctor_summary()
        self.status_text.configure(state="normal")
        self.status_text.delete("1.0", "end")
        self.status_text.insert("1.0", summary)
        self.status_text.configure(state="disabled")
        return summary

    def handle_add(self):
        try:
            account = self.controller.add_current_account(
                label=self.label_var.get().strip() or None,
                auth_file=self.auth_file_var.get().strip() or None,
            )
        except Exception as exc:
            self.messagebox.showerror("导入失败", str(exc))
            self.status_var.set(f"导入失败：{exc}")
            return
        self.refresh_rows(select_active=True)
        self.refresh_doctor()
        self.status_var.set(f"已导入账号：{account.email or account.label} [{account.id}]")
        self.messagebox.showinfo("导入成功", f"已导入账号：{account.email or account.label}")

    def handle_switch(self):
        try:
            account = self.controller.switch_by_row_index(self._selected_row_index())
        except Exception as exc:
            self.messagebox.showerror("切换失败", str(exc))
            self.status_var.set(f"切换失败：{exc}")
            return
        self.refresh_rows(select_active=True)
        self.refresh_doctor()
        self.status_var.set(f"已切换到：{account.email or account.label} [{account.id}]")

    def handle_remove(self):
        try:
            row_index = self._selected_row_index()
            rows = self.controller.load_rows()
            row = rows[row_index]
        except Exception as exc:
            self.messagebox.showerror("删除失败", str(exc))
            self.status_var.set(f"删除失败：{exc}")
            return
        target_name = row.get("email") or row.get("label") or row.get("id")
        confirmed = self.messagebox.askyesno("确认删除", f"确定删除账号：{target_name}？")
        if not confirmed:
            self.status_var.set("已取消删除。")
            return
        try:
            removed = self.controller.remove_by_row_index(row_index)
        except Exception as exc:
            self.messagebox.showerror("删除失败", str(exc))
            self.status_var.set(f"删除失败：{exc}")
            return
        self.refresh_rows(select_active=True)
        self.refresh_doctor()
        self.status_var.set(f"已删除账号：{removed.email or removed.label} [{removed.id}]")

    def copy_auth_path(self):
        path = str(self.controller.manager.codex_auth_file())
        self.root.clipboard_clear()
        self.root.clipboard_append(path)
        self.status_var.set(f"已复制路径：{path}")

    def run(self):
        self.root.mainloop()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=APP_NAME,
        description="Windows 版 Codex 账号管理 GUI：小窗口查看账号、导入、切换、删除、doctor 诊断。",
    )
    parser.add_argument("--auth-file", help="启动时预填一个 auth.json 路径，便于直接导入")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    app = CodexWindowsManagerGUI(
        controller=CodexWindowsManagerController(),
        prefill_auth_file=args.auth_file,
    )
    app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
