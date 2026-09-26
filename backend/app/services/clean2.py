"""车厢清洗业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

import threading
from typing import Any

from app.store import store

MODULE = "clean2"
REQUIRED_FIELDS = ["清洗编号", "清洗车辆", "清洗方式"]
LEDGER_FIELDS = ["清洗编号", "清洗车辆", "清洗方式", "消毒药剂", "清洗人员", "清洗日期", "下次清洗日"]
STATUS_ORDER = ["待清洗", "清洗中", "已清洗", "已验收"]
CLOSED_STATUS = STATUS_ORDER[-1]  # 已验收：清洗周期结束，记录只读
# 动作 -> (允许的前置状态, 目标状态)，只能按顺序流转
ACTION_RULES = {
    "安排清洗": ("待清洗", "清洗中"),
    "消毒登记": ("清洗中", "已清洗"),
    "验收完成": ("已清洗", "已验收"),
}
# 执行动作时允许随表单一并落账的字段
ACTION_FIELDS = ["消毒药剂", "清洗人员", "清洗日期", "下次清洗日"]


class Clean2Service:
    def __init__(self) -> None:
        self._lock = threading.Lock()

    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("清洗编号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
        """登记清洗记录：同一辆车同期只留一条在办记录，重复提交合并而不是新建。

        返回 (entry, message)；entry 为 None 时 message 是失败原因。
        """
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, f"缺少必填字段：{'、'.join(missing)}"
        number = str(values["清洗编号"]).strip()
        vehicle = str(values["清洗车辆"]).strip()
        with self._lock:
            rows = store.rows(MODULE)
            same_number = next(
                (row for row in rows if str(row.get("清洗编号", "")).strip() == number),
                None,
            )
            in_progress = next(
                (
                    row
                    for row in rows
                    if str(row.get("清洗车辆", "")).strip() == vehicle and row.get("status") != CLOSED_STATUS
                ),
                None,
            )
            if same_number is not None and same_number is not in_progress:
                return None, f"清洗编号 {number} 已存在于台账，历史清洗周期不能覆盖，请更换编号"
            if in_progress is not None:
                # 在办记录只补登字段，编号随车走，避免编号与人员错位
                self._fill(in_progress, values, fields=[f for f in LEDGER_FIELDS if f != "清洗编号"])
                return in_progress, (
                    f"车辆 {vehicle} 已有在办清洗记录 {in_progress.get('清洗编号')}，"
                    "本次提交已合并更新，未新建台账"
                )
            entry: dict[str, Any] = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
            entry["status"] = STATUS_ORDER[0]
            entry["pending"] = True
            entry["abnormal"] = False
            self._fill(entry, values, fields=LEDGER_FIELDS)
            rows.append(entry)
            return entry, "清洗记录已登记"

    def run_action(
        self,
        entry_id: int,
        action: str,
        values: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"清洗记录 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于车厢清洗可执行范围"
        if entry.get("status") == CLOSED_STATUS:
            return None, f"清洗记录 {entry.get('清洗编号', entry_id)} 已验收归档，只能查看不能再改动"
        source, target = ACTION_RULES[action]
        current = str(entry.get("status") or "")
        if current != source:
            return None, f"当前状态为「{current}」，「{action}」只能从「{source}」流转"
        values = values or {}
        if action == "消毒登记" and not str(values.get("消毒药剂") or "").strip() \
                and not str(entry.get("消毒药剂") or "").strip():
            return None, "请先填写消毒药剂，再完成消毒登记"
        with self._lock:
            for field in ACTION_FIELDS:
                text = str(values.get(field) or "").strip()
                if text:
                    entry[field] = text
            entry["status"] = target
            entry["pending"] = target != CLOSED_STATUS
            entry["abnormal"] = False
            entry["清洗状态"] = target
        return entry, f"清洗记录已{action}，状态更新为「{target}」"

    @staticmethod
    def _fill(entry: dict[str, Any], values: dict[str, Any], *, fields: list[str]) -> None:
        for field in fields:
            text = str(values.get(field) or "").strip()
            if text:
                entry[field] = text
        entry["清洗状态"] = entry["status"]
