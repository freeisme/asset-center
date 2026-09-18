<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { api } from "../api/client";
import LegacyFrame from "../components/LegacyFrame.vue";
import { loadMeta, session } from "../session";
import {
  applyThemeColor,
  currentThemeColor,
  DEFAULT_THEME_COLOR,
  resetThemeColor,
  THEME_COLOR_PRESETS,
} from "../theme";

const health = ref<{ ok: boolean; requiredTables: number; requiredTableCount: number } | null>(null);
const healthError = ref("");
const frontendVersion = __APP_VERSION__;
const frontendBuildTime = __APP_BUILD_TIME__;
const themeColor = ref(currentThemeColor());

const version = computed(() => session.meta?.version || frontendVersion);
const roleLabel = computed(() =>
  session.isSuperAdmin ? "超级管理员" : String(session.user?.role ?? "—"),
);

function formatTime(value: string | undefined): string {
  if (!value) return "—";
  return String(value).replace("T", " ").slice(0, 19);
}

function pickThemeColor(color: string): void {
  themeColor.value = applyThemeColor(color);
}

function restoreDefaultTheme(): void {
  themeColor.value = resetThemeColor();
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
        <strong>外观主题</strong>
        <span style="color: var(--el-text-color-secondary); font-size: 13px">
          当前主题色 {{ themeColor }}
        </span>
      </div>
    </template>
    <div style="display: flex; flex-wrap: wrap; gap: 10px; align-items: center">
      <button
        v-for="preset in THEME_COLOR_PRESETS"
        :key="preset.key"
        type="button"
        :title="preset.label"
        :style="{
          width: '34px',
          height: '34px',
          borderRadius: '8px',
          border:
            themeColor === preset.color
              ? '2px solid var(--el-text-color-primary)'
              : '1px solid var(--el-border-color)',
          background: preset.color,
          cursor: 'pointer',
          color: '#fff',
          lineHeight: '1',
        }"
        @click="pickThemeColor(preset.color)"
      >
        <span v-if="themeColor === preset.color">✓</span>
      </button>
      <el-color-picker
        :model-value="themeColor"
        :predefine="THEME_COLOR_PRESETS.map((item) => item.color)"
        @change="(value: string | null) => pickThemeColor(value || DEFAULT_THEME_COLOR)"
      />
      <el-button @click="restoreDefaultTheme">恢复默认</el-button>
    </div>
    <div style="margin-top: 14px; display: flex; gap: 8px; align-items: center; flex-wrap: wrap">
      <el-button type="primary">主要按钮</el-button>
      <el-button>次要按钮</el-button>
      <el-tag type="primary">标签</el-tag>
      <el-switch :model-value="true" />
      <span style="color: var(--el-text-color-secondary); font-size: 13px">
        主题色会应用到新界面与旧版页面（迁移期），并保存在本机浏览器。
      </span>
    </div>
  </el-card>

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
