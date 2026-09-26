<template>
  <section class="page" data-module="clean2">
    <header class="page-head">
      <div>
        <h2>车厢清洗管理</h2>
        <p class="page-desc">维护清洗记录，围绕清洗编号、清洗车辆、清洗方式、消毒药剂做登记、筛选与状态流转。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记清洗记录</button>
        <button class="btn" type="button" @click="exportRows">导出车厢清洗清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label class="filter-item">
        <span>清洗编号</span>
        <input v-model="keyword" placeholder="按清洗编号检索" />
      </label>
      <label class="filter-item">
        <span>清洗状态</span>
        <select v-model="statusFilter">
          <option value="">全部状态</option>
          <option v-for="status in statuses" :key="status" :value="status">{{ status }}</option>
        </select>
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">{{ row[column] ?? '—' }}</td>
          <td class="row-actions">
            <button class="link" type="button" @click="openDetail(row)">详情</button>
            <button
              v-for="action in rowActions(row)"
              :key="action"
              class="link"
              type="button"
              @click="runAction(action, row)"
            >
              {{ action }}
            </button>
            <span v-if="isClosed(row)" class="closed-tag">已归档只读</span>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无车厢清洗数据，可先登记清洗记录</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条车厢清洗记录</span>
      <span v-if="noticeMessage" class="notice-text">{{ noticeMessage }}</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>

    <div v-if="createVisible" class="modal-mask" @click.self="createVisible = false">
      <div class="modal">
        <h3>登记清洗记录</h3>
        <div class="form-grid">
          <label v-for="field in ledgerFields" :key="field" class="form-item">
            <span>{{ field }}<em v-if="requiredFields.includes(field)" class="required-mark">*</em></span>
            <input
              v-model="createForm[field]"
              :type="dateFields.includes(field) ? 'date' : 'text'"
              :placeholder="`请输入${field}`"
            />
          </label>
        </div>
        <p class="modal-tip">同一辆车同期只保留一条在办记录，重复提交会合并到原记录，不会新建台账。</p>
        <p v-if="createError" class="error-text">{{ createError }}</p>
        <div class="modal-actions">
          <button class="btn ghost" type="button" @click="createVisible = false">取消</button>
          <button class="btn primary" type="button" :disabled="submitting" @click="submitCreate">提交登记</button>
        </div>
      </div>
    </div>

    <div v-if="detailVisible" class="modal-mask" @click.self="detailVisible = false">
      <div class="modal">
        <h3>清洗记录详情</h3>
        <template v-if="detail">
          <dl class="detail-grid">
            <template v-for="column in columns" :key="column">
              <dt>{{ column }}</dt>
              <dd>{{ detail[column] ?? '—' }}</dd>
            </template>
          </dl>
          <p v-if="isClosed(detail)" class="modal-tip">该记录已验收归档，只能查看不能再改动。</p>
          <div class="modal-actions">
            <button class="btn ghost" type="button" @click="detailVisible = false">关闭</button>
            <button
              v-for="action in rowActions(detail)"
              :key="action"
              class="btn primary"
              type="button"
              @click="runAction(action, detail)"
            >
              {{ action }}
            </button>
          </div>
        </template>
        <p v-else class="modal-tip">正在读取明细…</p>
        <p v-if="detailError" class="error-text">{{ detailError }}</p>
      </div>
    </div>

    <div v-if="disinfectVisible && disinfectTarget" class="modal-mask" @click.self="disinfectVisible = false">
      <div class="modal">
        <h3>消毒登记 · {{ disinfectTarget['清洗编号'] }}</h3>
        <dl class="detail-grid">
          <dt>清洗车辆</dt>
          <dd>{{ disinfectTarget['清洗车辆'] ?? '—' }}</dd>
          <dt>当前状态</dt>
          <dd>{{ disinfectTarget['清洗状态'] ?? '—' }}</dd>
        </dl>
        <div class="form-grid">
          <label class="form-item">
            <span>消毒药剂<em class="required-mark">*</em></span>
            <input v-model="disinfectForm['消毒药剂']" placeholder="请输入消毒药剂" />
          </label>
          <label class="form-item">
            <span>清洗人员</span>
            <input v-model="disinfectForm['清洗人员']" placeholder="请输入清洗人员" />
          </label>
          <label class="form-item">
            <span>清洗日期</span>
            <input v-model="disinfectForm['清洗日期']" type="date" />
          </label>
          <label class="form-item">
            <span>下次清洗日</span>
            <input v-model="disinfectForm['下次清洗日']" type="date" />
          </label>
        </div>
        <p class="modal-tip">提交后清洗状态更新为「已清洗」，消毒药剂一并落账保留。</p>
        <p v-if="disinfectError" class="error-text">{{ disinfectError }}</p>
        <div class="modal-actions">
          <button class="btn ghost" type="button" @click="disinfectVisible = false">取消</button>
          <button class="btn primary" type="button" :disabled="submitting" @click="submitDisinfect">确认消毒完成</button>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>

const ENDPOINT = '/api/clean2'
const columns = ["清洗编号", "清洗车辆", "清洗方式", "消毒药剂", "清洗人员", "清洗日期", "下次清洗日", "清洗状态"]
const ledgerFields = columns.slice(0, 7)
const requiredFields = ["清洗编号", "清洗车辆", "清洗方式"]
const dateFields = ["清洗日期", "下次清洗日"]
const statuses = ["待清洗", "清洗中", "已清洗", "已验收"]
const closedStatus = "已验收"
const nextActions: Record<string, string> = { "待清洗": "安排清洗", "清洗中": "消毒登记", "已清洗": "验收完成" }

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const noticeMessage = ref('')
const keyword = ref('')
const statusFilter = ref('')
const submitting = ref(false)
const stats = ref([
  { label: '待清洗车辆', value: 0 },
  { label: '清洗中车辆', value: 0 },
  { label: '已验收车辆', value: 0 },
])

const createVisible = ref(false)
const createForm = ref<Record<string, string>>({})
const createError = ref('')

const detailVisible = ref(false)
const detail = ref<Row | null>(null)
const detailError = ref('')

const disinfectVisible = ref(false)
const disinfectTarget = ref<Row | null>(null)
const disinfectForm = ref<Record<string, string>>({})
const disinfectError = ref('')

function statusOf(row: Row): string {
  return String(row.status ?? row['清洗状态'] ?? '')
}

function isClosed(row: Row): boolean {
  return statusOf(row) === closedStatus
}

function rowActions(row: Row): string[] {
  const action = nextActions[statusOf(row)]
  return action ? [action] : []
}

function textOf(row: Row, field: string): string {
  const value = row[field]
  return value === null || value === undefined ? '' : String(value)
}

function resetFilters() {
  keyword.value = ''
  statusFilter.value = ''
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  createForm.value = Object.fromEntries(ledgerFields.map((field) => [field, '']))
  createError.value = ''
  createVisible.value = true
}

async function submitCreate() {
  for (const field of requiredFields) {
    if (!createForm.value[field]?.trim()) {
      createError.value = `请先填写${field}`
      return
    }
  }
  submitting.value = true
  try {
    const response = await request(ENDPOINT, {
      method: 'POST',
      body: JSON.stringify({ values: createForm.value }),
    })
    const payload = await response.json()
    if (!response.ok || !payload.ok) {
      createError.value = payload.message ?? payload.detail ?? '清洗记录登记失败，请稍后重试'
      return
    }
    createVisible.value = false
    noticeMessage.value = payload.message ?? '清洗记录已登记'
    await reload()
  } catch (error) {
    createError.value = error instanceof Error ? error.message : '清洗记录登记失败'
  } finally {
    submitting.value = false
  }
}

async function openDetail(row: Row) {
  detailVisible.value = true
  detail.value = null
  detailError.value = ''
  await refreshDetail(Number(row.id))
}

async function refreshDetail(id: number) {
  try {
    const response = await request(`${ENDPOINT}/${id}`)
    const payload = await response.json()
    if (!response.ok) {
      throw new Error(payload.detail ?? '清洗记录明细读取失败')
    }
    detail.value = payload
  } catch (error) {
    detailError.value = error instanceof Error ? error.message : '清洗记录明细读取失败'
  }
}

function openDisinfect(row: Row) {
  disinfectTarget.value = row
  disinfectForm.value = {
    "消毒药剂": textOf(row, '消毒药剂'),
    "清洗人员": textOf(row, '清洗人员'),
    "清洗日期": textOf(row, '清洗日期'),
    "下次清洗日": textOf(row, '下次清洗日'),
  }
  disinfectError.value = ''
  disinfectVisible.value = true
}

async function submitDisinfect() {
  if (!disinfectTarget.value) return
  if (!disinfectForm.value['消毒药剂']?.trim()) {
    disinfectError.value = '请先填写消毒药剂，再完成消毒登记'
    return
  }
  const failure = await postAction(disinfectTarget.value, { action: '消毒登记', ...disinfectForm.value })
  if (failure) {
    disinfectError.value = failure
    return
  }
  disinfectVisible.value = false
}

async function runAction(action: string, row: Row) {
  if (action === '消毒登记') {
    openDisinfect(row)
    return
  }
  errorMessage.value = ''
  noticeMessage.value = ''
  const failure = await postAction(row, { action })
  if (failure) {
    errorMessage.value = failure
  }
}

/** 提交状态动作；返回 null 表示成功，否则为可读的失败原因。 */
async function postAction(row: Row, values: Record<string, string>): Promise<string | null> {
  submitting.value = true
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values }),
    })
    const payload = await response.json()
    if (!response.ok || !payload.ok) {
      return payload.message ?? payload.detail ?? '车厢清洗动作未生效，请稍后重试'
    }
    noticeMessage.value = payload.message ?? '操作成功'
    await reload()
    if (detailVisible.value && detail.value && String(detail.value.id) === String(row.id)) {
      await refreshDetail(Number(row.id))
    }
    return null
  } catch (error) {
    return error instanceof Error ? error.message : '车厢清洗操作失败'
  } finally {
    submitting.value = false
  }
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams()
  if (keyword.value.trim()) query.set('keyword', keyword.value.trim())
  if (statusFilter.value) query.set('status', statusFilter.value)
  try {
    const response = await request(`${ENDPOINT}?${query.toString()}`)
    if (!response.ok) {
      throw new Error('清洗记录列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '车厢清洗列表读取失败'
  }
  await refreshStats()
}

async function refreshStats() {
  try {
    const response = await request(`${ENDPOINT}?page=1&size=200`)
    if (!response.ok) return
    const payload = await response.json()
    const counts: Record<string, number> = {}
    for (const item of (payload.items ?? []) as Row[]) {
      const key = statusOf(item)
      counts[key] = (counts[key] ?? 0) + 1
    }
    stats.value = [
      { label: '待清洗车辆', value: counts['待清洗'] ?? 0 },
      { label: '清洗中车辆', value: counts['清洗中'] ?? 0 },
      { label: '已验收车辆', value: counts['已验收'] ?? 0 },
    ]
  } catch {
    // 统计卡片读取失败不阻断列表
  }
}

onMounted(reload)
</script>

<style scoped>
.modal-mask {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 20;
}
.modal {
  background: #fff;
  border-radius: 10px;
  padding: 16px 18px;
  width: 420px;
  max-width: 92vw;
  max-height: 86vh;
  overflow-y: auto;
}
.modal h3 {
  margin: 0 0 12px;
  font-size: 15px;
}
.form-grid {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 12px;
}
.form-item span {
  display: block;
  font-size: 12px;
  color: var(--muted);
  margin-bottom: 4px;
}
.form-item input {
  width: 100%;
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 6px 8px;
}
.required-mark {
  color: #b42318;
  font-style: normal;
  margin-left: 2px;
}
.modal-tip {
  font-size: 12px;
  color: var(--muted);
  margin: 10px 0 0;
}
.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 14px;
}
.detail-grid {
  display: grid;
  grid-template-columns: 96px 1fr;
  row-gap: 8px;
  margin: 0;
  font-size: 13px;
}
.detail-grid dt {
  color: var(--muted);
}
.detail-grid dd {
  margin: 0;
}
.filter-item select {
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 6px 8px;
  background: #fff;
}
.closed-tag {
  color: var(--muted);
  font-size: 12px;
}
.notice-text {
  color: #067647;
}
</style>
