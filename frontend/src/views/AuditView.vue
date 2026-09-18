<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import {
  AUDIT_ACTION_LABELS,
  AUDIT_CATEGORY_LABELS,
  AUDIT_CATEGORY_OPTIONS,
  AUDIT_ENTITY_TYPE_LABELS,
  AUDIT_ENTITY_TYPE_OPTIONS,
  auditActionLabel,
  auditCategoryLabel,
  auditChangeLabel,
  auditEntityTypeLabel,
  auditLogsToCsv,
  auditTagType,
  auditValueText,
  fetchAuditLogs,
  type AuditLog,
} from "../api/audit";

const loading = ref(false);
const logs = ref<AuditLog[]>([]);
const total = ref(0);
const page = ref(1);
const pageSize = ref(50);
const detail = ref<AuditLog | null>(null);
const detailVisible = ref(false);

const filters = reactive({
  dateRange: [] as string[],
  employee: "",
  keyword: "",
  category: "",
  actionType: "",
  entityType: "",
});

const actionOptions = computed(() => Object.keys(AUDIT_ACTION_LABELS));
const pagedLogs = computed(() => {
  const start = (page.value - 1) * pageSize.value;
  return logs.value.slice(start, start + pageSize.value);
});

async function load(): Promise<void> {
  loading.value = true;
  try {
    const payload = await fetchAuditLogs({
      startDate: filters.dateRange?.[0] || "",
      endDate: filters.dateRange?.[1] || "",
      employee: filters.employee,
      keyword: filters.keyword,
      category: filters.category,
      actionType: filters.actionType,
      entityType: filters.entityType,
      limit: 5000,
    });
    logs.value = payload.logs;
    total.value = payload.total;
    page.value = 1;
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "日志加载失败。");
  } finally {
    loading.value = false;
  }
}

function reset(): void {
  filters.dateRange = [];
  filters.employee = "";
  filters.keyword = "";
  filters.category = "";
  filters.actionType = "";
  filters.entityType = "";
  void load();
}

function openDetail(log: AuditLog): void {
  detail.value = log;
  detailVisible.value = true;
}

function exportCsv(): void {
  if (!logs.value.length) {
    ElMessage.warning("当前没有可导出的日志。");
    return;
  }
  const stamp = new Date()
    .toISOString()
    .slice(0, 16)
    .replace(/-/g, "")
    .replace("T", "-")
    .replace(":", "");
  const blob = new Blob([`\ufeff${auditLogsToCsv(logs.value)}`], {
    type: "text/csv;charset=utf-8;",
  });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `操作日志-${stamp}.csv`;
  link.click();
  URL.revokeObjectURL(url);
}

onMounted(load);
</script>

<template>
  <el-card shadow="never">
    <el-form label-position="top" @submit.prevent="load">
      <el-row :gutter="12">
        <el-col :xs="24" :sm="12" :md="6">
          <el-form-item label="日期范围">
            <el-date-picker
              v-model="filters.dateRange"
              type="daterange"
              value-format="YYYY-MM-DD"
              start-placeholder="开始日期"
              end-placeholder="结束日期"
              style="width: 100%"
            />
          </el-form-item>
        </el-col>
        <el-col :xs="24" :sm="12" :md="4">
          <el-form-item label="人员">
            <el-input v-model="filters.employee" placeholder="人员编号或姓名" clearable />
          </el-form-item>
        </el-col>
        <el-col :xs="24" :sm="12" :md="4">
          <el-form-item label="关键词">
            <el-input
              v-model="filters.keyword"
              placeholder="人员、设备或操作内容"
              clearable
              @keyup.enter="load"
            />
          </el-form-item>
        </el-col>
        <el-col :xs="24" :sm="12" :md="3">
          <el-form-item label="操作类别">
            <el-select v-model="filters.category" placeholder="全部类别" clearable style="width: 100%">
              <el-option
                v-for="option in AUDIT_CATEGORY_OPTIONS"
                :key="option"
                :label="AUDIT_CATEGORY_LABELS[option]"
                :value="option"
              />
            </el-select>
          </el-form-item>
        </el-col>
        <el-col :xs="24" :sm="12" :md="4">
          <el-form-item label="具体变动">
            <el-select
              v-model="filters.actionType"
              placeholder="全部变动"
              clearable
              filterable
              style="width: 100%"
            >
              <el-option
                v-for="option in actionOptions"
                :key="option"
                :label="auditActionLabel(option)"
                :value="option"
              />
            </el-select>
          </el-form-item>
        </el-col>
        <el-col :xs="24" :sm="12" :md="3">
          <el-form-item label="对象范围">
            <el-select
              v-model="filters.entityType"
              placeholder="全部对象"
              clearable
              style="width: 100%"
            >
              <el-option
                v-for="option in AUDIT_ENTITY_TYPE_OPTIONS"
                :key="option"
                :label="AUDIT_ENTITY_TYPE_LABELS[option]"
                :value="option"
              />
            </el-select>
          </el-form-item>
        </el-col>
      </el-row>
      <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap">
        <el-button type="primary" :loading="loading" @click="load">应用筛选</el-button>
        <el-button @click="reset">重置</el-button>
        <el-button @click="load">刷新日志</el-button>
        <el-button :disabled="!logs.length" @click="exportCsv">导出当前结果</el-button>
        <span style="color: var(--el-text-color-secondary); font-size: 13px">
          显示 {{ logs.length }} / 共 {{ total }} 条
        </span>
      </div>
    </el-form>
  </el-card>

  <el-card shadow="never" style="margin-top: 12px">
    <el-table
      v-loading="loading"
      :data="pagedLogs"
      size="small"
      border
      stripe
      height="calc(100vh - 420px)"
      empty-text="暂无符合条件的操作日志"
    >
      <el-table-column prop="createdAt" label="时间" width="160" />
      <el-table-column label="操作类别" width="130">
        <template #default="{ row }">
          <el-tag size="small" effect="plain">{{ auditCategoryLabel(row) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="具体变动" width="150">
        <template #default="{ row }">
          <el-tag size="small" :type="auditTagType(row.actionType)">{{ auditChangeLabel(row) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="变更对象" min-width="200">
        <template #default="{ row }">
          <div>{{ row.entityName || row.deviceName || "—" }}</div>
          <div style="color: var(--el-text-color-secondary); font-size: 12px">
            {{ auditEntityTypeLabel(row.entityType) }}
          </div>
        </template>
      </el-table-column>
      <el-table-column label="关联人员" width="150">
        <template #default="{ row }">
          <div v-if="row.employeeName">
            {{ row.employeeName }}
            <div style="color: var(--el-text-color-secondary); font-size: 12px">
              {{ row.employeeId }}
            </div>
          </div>
          <span v-else style="color: var(--el-text-color-secondary)">—</span>
        </template>
      </el-table-column>
      <el-table-column label="变更前" min-width="180" show-overflow-tooltip>
        <template #default="{ row }">{{ auditValueText(row.oldValue) }}</template>
      </el-table-column>
      <el-table-column label="变更后" min-width="180" show-overflow-tooltip>
        <template #default="{ row }">{{ auditValueText(row.newValue) }}</template>
      </el-table-column>
      <el-table-column prop="summary" label="变更说明" min-width="200" show-overflow-tooltip />
      <el-table-column label="操作人" width="120">
        <template #default="{ row }">
          <div>{{ row.actor || "web" }}</div>
          <div style="color: var(--el-text-color-secondary); font-size: 12px">{{ row.source }}</div>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="80" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openDetail(row)">详情</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination
      v-model:current-page="page"
      v-model:page-size="pageSize"
      :page-sizes="[20, 50, 100, 200]"
      :total="logs.length"
      layout="total, sizes, prev, pager, next"
      style="margin-top: 12px; justify-content: flex-end"
    />
  </el-card>

  <el-drawer v-model="detailVisible" title="日志详情" size="520px">
    <el-descriptions v-if="detail" :column="1" border>
      <el-descriptions-item label="时间">{{ detail.createdAt }}</el-descriptions-item>
      <el-descriptions-item label="操作类别">{{ auditCategoryLabel(detail) }}</el-descriptions-item>
      <el-descriptions-item label="具体变动">{{ auditChangeLabel(detail) }}</el-descriptions-item>
      <el-descriptions-item label="操作类型">{{ detail.actionType }}</el-descriptions-item>
      <el-descriptions-item label="对象">
        {{ detail.entityName || detail.deviceName || "—" }}（{{ auditEntityTypeLabel(detail.entityType) }}）
      </el-descriptions-item>
      <el-descriptions-item label="关联人员">
        {{ detail.employeeName || "—" }} {{ detail.employeeId }}
      </el-descriptions-item>
      <el-descriptions-item label="变更前">{{ auditValueText(detail.oldValue) }}</el-descriptions-item>
      <el-descriptions-item label="变更后">{{ auditValueText(detail.newValue) }}</el-descriptions-item>
      <el-descriptions-item label="变更说明">{{ detail.summary || "—" }}</el-descriptions-item>
      <el-descriptions-item label="操作人">
        {{ detail.actor || "web" }} / {{ detail.source || "—" }}
      </el-descriptions-item>
    </el-descriptions>
  </el-drawer>
</template>
