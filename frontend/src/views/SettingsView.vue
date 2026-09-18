<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { api } from "../api/client";
import LegacyFrame from "../components/LegacyFrame.vue";
import { loadMeta, session } from "../session";

const health = ref<{ ok: boolean; requiredTables: number; requiredTableCount: number } | null>(null);
const healthError = ref("");
const frontendVersion = __APP_VERSION__;
const frontendBuildTime = __APP_BUILD_TIME__;

const version = computed(() => session.meta?.version || frontendVersion);
const roleLabel = computed(() =>
  session.isSuperAdmin ? "超级管理员" : String(session.user?.role ?? "—"),
);

function formatTime(value: string | undefined): string {
  if (!value) return "—";
  return String(value).replace("T", " ").slice(0, 19);
}

onMounted(async () => {
  await loadMeta();
  try {
    health.value = await api<{ ok: boolean; requiredTables: number; requiredTableCount: number }>(
      "/api/health",
    );
  } catch (error) {
    healthError.value = error instanceof Error ? error.message : "健康检查失败。";
  }
});
</script>

<template>
  <el-card shadow="never">
    <template #header>
      <div style="display: flex; align-items: center; justify-content: space-between">
        <strong>系统信息</strong>
        <el-tag type="success" effect="dark">当前系统版本 v{{ version }}</el-tag>
      </div>
    </template>
    <el-descriptions :column="2" border>
      <el-descriptions-item label="当前系统版本">
        <strong>v{{ version }}</strong>
      </el-descriptions-item>
      <el-descriptions-item label="前端构建版本">v{{ frontendVersion }}</el-descriptions-item>
      <el-descriptions-item label="前端构建时间">{{ formatTime(frontendBuildTime) }}</el-descriptions-item>
      <el-descriptions-item label="服务端时间">
        {{ formatTime(session.meta?.serverTime) }} {{ session.meta?.timeZone || "" }}
      </el-descriptions-item>
      <el-descriptions-item label="登录账号">
        {{ session.user?.displayName || session.user?.username || "—" }}（{{ roleLabel }}）
      </el-descriptions-item>
      <el-descriptions-item label="数据库">
        <template v-if="health">
          {{ health.ok ? "连接正常" : "异常" }} ·
          {{ health.requiredTables }}/{{ health.requiredTableCount }} 张必需表
        </template>
        <template v-else-if="healthError">{{ healthError }}</template>
        <template v-else>检测中…</template>
      </el-descriptions-item>
    </el-descriptions>
  </el-card>

  <el-card shadow="never" style="margin-top: 16px">
    <template #header>
      <div style="display: flex; align-items: center; gap: 8px">
        <strong>完整设置</strong>
        <el-tag size="small" type="warning" effect="plain">迁移中：以下沿用旧版界面</el-tag>
      </div>
    </template>
    <div style="height: calc(100vh - 320px); min-height: 420px">
      <LegacyFrame page="settings" />
    </div>
  </el-card>
</template>
