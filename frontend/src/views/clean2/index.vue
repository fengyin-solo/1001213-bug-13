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

    <template v-if="!current">
      <form class="filter-bar" @submit.prevent="reload">
        <label v-for="field in filterFields" :key="field" class="filter-item">
          <span>{{ field }}</span>
          <input v-model="filters[field]" :placeholder="`按${field}检索`" />
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
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in rows" :key="String(row.id)">
            <td v-for="column in columns" :key="column">
              <span v-if="column === '清洗状态'" class="tag" :class="tagClass(row.status)">
                {{ row.status ?? '—' }}
              </span>
              <template v-else>{{ row[column] ?? '—' }}</template>
            </td>
            <td class="row-actions">
              <button class="link" type="button" @click="openDetail(row)">详情</button>
            </td>
          </tr>
          <tr v-if="!rows.length">
            <td :colspan="columns.length + 1" class="empty-state">暂无车厢清洗数据，可先登记清洗记录</td>
          </tr>
        </tbody>
      </table>
    </template>

    <div v-else class="detail-card">
      <header class="detail-head">
        <div>
          <h3>清洗记录 {{ current.清洗编号 }}</h3>
          <span class="tag" :class="tagClass(current.status)">{{ current.status }}</span>
        </div>
        <button class="btn ghost" type="button" @click="backToList">返回列表</button>
      </header>
      <div class="detail-grid">
        <div v-for="column in columns" :key="column" class="kv">
          <span>{{ column }}</span>
          <strong>{{ current[column] ?? '—' }}</strong>
        </div>
      </div>
      <div v-if="availableActions.length" class="detail-actions">
        <button
          v-for="action in availableActions"
          :key="action"
          class="btn"
          :class="{ primary: action === '消毒登记' }"
          type="button"
          :disabled="submitting"
          @click="runAction(action)"
        >
          {{ action }}
        </button>
      </div>
      <p v-else class="archived-note">该记录已验收归档，仅供查看，不能再改动。</p>
    </div>

    <div v-if="showCreate" class="modal-mask" @click.self="showCreate = false">
      <div class="modal-card">
        <h3>登记清洗记录</h3>
        <div class="form-grid">
          <label v-for="field in createFields" :key="field.key" class="form-item">
            <span>{{ field.key }}<i v-if="field.required" class="required">*</i></span>
            <input
              v-model="createForm[field.key]"
              :type="field.type"
              :placeholder="field.placeholder"
            />
          </label>
        </div>
        <p v-if="createError" class="error-text">{{ createError }}</p>
        <div class="modal-actions">
          <button class="btn ghost" type="button" @click="showCreate = false">取消</button>
          <button class="btn primary" type="button" :disabled="submitting" @click="submitCreate">
            {{ submitting ? '提交中…' : '提交登记' }}
          </button>
        </div>
      </div>
    </div>

    <div v-if="showDisinfect" class="modal-mask" @click.self="showDisinfect = false">
      <div class="modal-card">
        <h3>消毒登记</h3>
        <div class="detail-grid">
          <div class="kv">
            <span>清洗编号</span>
            <strong>{{ current?.清洗编号 ?? '—' }}</strong>
          </div>
          <div class="kv">
            <span>清洗车辆</span>
            <strong>{{ current?.清洗车辆 ?? '—' }}</strong>
          </div>
          <div class="kv">
            <span>当前状态</span>
            <strong>
              <span class="tag" :class="tagClass(current?.status)">{{ current?.status ?? '—' }}</span>
            </strong>
          </div>
        </div>
        <label class="form-item">
          <span>消毒药剂<i class="required">*</i></span>
          <input v-model="disinfectAgent" placeholder="如：含氯消毒剂" />
        </label>
        <p v-if="disinfectError" class="error-text">{{ disinfectError }}</p>
        <div class="modal-actions">
          <button class="btn ghost" type="button" @click="showDisinfect = false">取消</button>
          <button class="btn primary" type="button" :disabled="submitting" @click="submitDisinfect">
            {{ submitting ? '提交中…' : '确认消毒完成' }}
          </button>
        </div>
      </div>
    </div>

    <footer class="page-foot">
      <span>共 {{ total }} 条车厢清洗记录</span>
      <span v-if="noticeMessage" class="notice-text">{{ noticeMessage }}</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>

const ENDPOINT = '/api/clean2'
const columns = ["清洗编号", "清洗车辆", "清洗方式", "消毒药剂", "清洗人员", "清洗日期", "下次清洗日", "清洗状态"]
const statuses = ["待清洗", "清洗中", "已清洗", "已验收"]
const TERMINAL_STATUS = '已验收'
const filterFields = columns.slice(0, 3)
const createFields = [
  { key: '清洗编号', type: 'text', required: true, placeholder: '如 CLEA-0004' },
  { key: '清洗车辆', type: 'text', required: true, placeholder: '车牌或车辆编号' },
  { key: '清洗方式', type: 'text', required: true, placeholder: '如 高压冲洗' },
  { key: '清洗人员', type: 'text', required: true, placeholder: '负责人姓名' },
  { key: '清洗日期', type: 'date', required: true, placeholder: '' },
  { key: '下次清洗日', type: 'date', required: false, placeholder: '' },
  { key: '消毒药剂', type: 'text', required: false, placeholder: '也可在消毒登记时填写' },
]

const rows = ref<Row[]>([])
const total = ref(0)
const stats = ref(statuses.map((status) => ({ label: `${status}车辆`, value: 0 })))
const errorMessage = ref('')
const noticeMessage = ref('')
const filters = ref<Record<string, string>>({})
const statusFilter = ref('')

const current = ref<Row | null>(null)
const showCreate = ref(false)
const showDisinfect = ref(false)
const submitting = ref(false)
const createForm = ref<Record<string, string>>({})
const createError = ref('')
const disinfectAgent = ref('')
const disinfectError = ref('')

const availableActions = computed(() => {
  const status = current.value?.status
  if (status === '待清洗') return ['安排清洗', '消毒登记']
  if (status === '清洗中') return ['消毒登记']
  if (status === '已清洗') return ['验收完成']
  return []
})

function tagClass(status: Row['status'] | undefined) {
  if (status === '待清洗') return 'pending'
  if (status === TERMINAL_STATUS) return 'done'
  return 'active'
}

function resetFilters() {
  filters.value = {}
  statusFilter.value = ''
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  createForm.value = {}
  createError.value = ''
  showCreate.value = true
}

async function readResult(response: Response): Promise<{ ok: boolean; message: string }> {
  const payload = (await response.json().catch(() => ({}))) as Record<string, unknown>
  const message =
    (typeof payload.message === 'string' && payload.message) ||
    (typeof payload.detail === 'string' && payload.detail) ||
    '车厢清洗操作未生效，请稍后重试'
  return { ok: response.ok && payload.ok !== false, message }
}

async function submitCreate() {
  if (submitting.value) return
  createError.value = ''
  submitting.value = true
  try {
    const response = await request(ENDPOINT, {
      method: 'POST',
      body: JSON.stringify({ values: createForm.value }),
    })
    const result = await readResult(response)
    if (!result.ok) {
      createError.value = result.message
      return
    }
    showCreate.value = false
    noticeMessage.value = result.message
    await Promise.all([reload(), loadStats()])
  } catch (error) {
    createError.value = error instanceof Error ? error.message : '清洗记录登记失败'
  } finally {
    submitting.value = false
  }
}

async function openDetail(row: Row) {
  errorMessage.value = ''
  noticeMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}`)
    if (!response.ok) {
      throw new Error('清洗记录明细读取失败')
    }
    current.value = (await response.json()) as Row
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '清洗记录明细读取失败'
  }
}

function backToList() {
  current.value = null
  void reload()
}

async function refreshDetail() {
  if (!current.value) return
  const response = await request(`${ENDPOINT}/${current.value.id}`)
  if (response.ok) {
    current.value = (await response.json()) as Row
  }
}

async function postAction(values: Record<string, string>): Promise<string | null> {
  if (!current.value || submitting.value) return null
  submitting.value = true
  try {
    const response = await request(`${ENDPOINT}/${current.value.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values }),
    })
    const result = await readResult(response)
    if (!result.ok) {
      return result.message
    }
    noticeMessage.value = result.message
    await Promise.all([refreshDetail(), reload(), loadStats()])
    return null
  } catch (error) {
    return error instanceof Error ? error.message : '车厢清洗操作失败'
  } finally {
    submitting.value = false
  }
}

async function runAction(action: string) {
  errorMessage.value = ''
  noticeMessage.value = ''
  if (action === '消毒登记') {
    disinfectAgent.value = String(current.value?.消毒药剂 ?? '')
    disinfectError.value = ''
    showDisinfect.value = true
    return
  }
  const failure = await postAction({ action })
  if (failure) {
    errorMessage.value = failure
  }
}

async function submitDisinfect() {
  disinfectError.value = ''
  const failure = await postAction({ action: '消毒登记', 消毒药剂: disinfectAgent.value.trim() })
  if (failure) {
    disinfectError.value = failure
    return
  }
  showDisinfect.value = false
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams()
  for (const field of filterFields) {
    const value = (filters.value[field] ?? '').trim()
    if (value) query.set(field, value)
  }
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
}

async function loadStats() {
  try {
    const response = await request(`${ENDPOINT}?size=200`)
    if (!response.ok) return
    const payload = await response.json()
    const items: Row[] = payload.items ?? []
    stats.value = statuses.map((status) => ({
      label: `${status}车辆`,
      value: items.filter((item) => item.status === status).length,
    }))
  } catch {
    // 统计卡片失败不阻塞页面
  }
}

onMounted(() => {
  void reload()
  void loadStats()
})
</script>
