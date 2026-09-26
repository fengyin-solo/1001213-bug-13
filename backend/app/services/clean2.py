"""车厢清洗业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

from typing import Any

from app.store import store

MODULE = "clean2"
# 台账字段全集：登记时一次落库，避免清洗编号与清洗人员错位、下次清洗日丢失
LEDGER_FIELDS = ["清洗编号", "清洗车辆", "清洗方式", "消毒药剂", "清洗人员", "清洗日期", "下次清洗日"]
REQUIRED_FIELDS = ["清洗编号", "清洗车辆", "清洗方式", "清洗人员", "清洗日期"]
STATUS_ORDER = ["待清洗", "清洗中", "已清洗", "已验收"]
TERMINAL_STATUS = STATUS_ORDER[-1]
ACTION_RULES = {"安排清洗": "清洗中", "消毒登记": "已清洗", "验收完成": "已验收"}
# 每个动作允许从哪些状态发起：已验收归档的记录只能查看，不能再改动
ACTION_SOURCES = {
    "安排清洗": {"待清洗"},
    "消毒登记": {"待清洗", "清洗中"},
    "验收完成": {"已清洗"},
}
NEGATIVE_ACTIONS = []
FILTER_FIELDS = ["清洗编号", "清洗车辆", "清洗方式"]


def _period_of(row: dict[str, Any]) -> str:
    """清洗周期按清洗日期的年月划分：同一辆车同期只保留一条在办记录。"""
    return str(row.get("清洗日期") or "")[:7]


class Clean2Service:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        filters: dict[str, str] | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("清洗编号", ""))]
        for field, value in (filters or {}).items():
            if field in FILTER_FIELDS and value:
                rows = [row for row in rows if value in str(row.get(field, ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def _duplicate_error(self, values: dict[str, Any]) -> str:
        """查重：清洗编号全局唯一；同一辆车在同一清洗周期只允许一条在办记录。

        已验收归档的历史记录不参与在办查重，新周期登记不会覆盖历史周期。
        """
        code = str(values.get("清洗编号") or "").strip()
        vehicle = str(values.get("清洗车辆") or "").strip()
        period = str(values.get("清洗日期") or "").strip()[:7]
        for row in store.rows(MODULE):
            if code and str(row.get("清洗编号") or "") == code:
                return f"清洗编号 {code} 已登记过，请勿重复提交"
            if (
                row.get("status") != TERMINAL_STATUS
                and vehicle
                and period
                and str(row.get("清洗车辆") or "") == vehicle
                and _period_of(row) == period
            ):
                return (
                    f"该车辆在本清洗周期已有在办记录（{row.get('清洗编号')}），"
                    "同一辆车同期只保留一条，请勿重复提交"
                )
        return ""

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, f"缺少必填字段：{'、'.join(missing)}"
        duplicate = self._duplicate_error(values)
        if duplicate:
            return None, duplicate
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        for field in LEDGER_FIELDS:
            text = str(values.get(field) or "").strip()
            entry[field] = text or None
        entry["status"] = STATUS_ORDER[0]
        entry["清洗状态"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return entry, ""

    def run_action(
        self, entry_id: int, action: str, values: dict[str, Any] | None = None
    ) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"清洗记录 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于车厢清洗可执行范围"
        if entry.get("status") == TERMINAL_STATUS:
            return None, "该清洗记录已验收归档，只能查看，不能再改动"
        if entry.get("status") not in ACTION_SOURCES[action]:
            return None, f"当前状态「{entry.get('status')}」不能执行「{action}」"
        if action == "消毒登记":
            agent = str((values or {}).get("消毒药剂") or "").strip()
            if not agent:
                return None, "消毒登记需要填写消毒药剂"
            entry["消毒药剂"] = agent
        target = ACTION_RULES[action]
        entry["status"] = target
        # 业务列与系统状态同步，列表、详情、消毒弹窗看到的是同一结论
        entry["清洗状态"] = target
        entry["pending"] = target != TERMINAL_STATUS
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        return entry, f"清洗记录已{action}"
