<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import { NAV_GROUPS, NAV_ITEMS, PATH_BY_PAGE } from "../navigation";
import { canViewPage, loadMeta, logout, session } from "../session";
import {
  applyLegacyTheme,
  clickLegacyAction,
  hasLegacyFrame,
  legacyNotificationCount,
  legacyTheme,
} from "../legacyBridge";

const route = useRoute();
const router = useRouter();
const theme = ref(document.documentElement.dataset.theme === "dark" ? "dark" : "light");
const notificationCount = ref("");
let pollTimer: number | undefined;

const visibleItems = computed(() => NAV_ITEMS.filter((item) => canViewPage(item.page)));
const currentTitle = computed(() => String(route.meta.title ?? "办公资产中台"));
const version = computed(() => session.meta?.version || __APP_VERSION__);

function setTheme(next: string): void {
  theme.value = next;
  document.documentElement.dataset.theme = next;
  document.documentElement.classList.toggle("dark", next === "dark");
  window.localStorage.setItem("oa-theme", next);
  applyLegacyTheme(next);
}

function toggleTheme(): void {
  if (hasLegacyFrame() && clickLegacyAction("toggle-theme")) {
    const next = legacyTheme() || (theme.value === "dark" ? "light" : "dark");
    setTheme(next);
    return;
  }
  setTheme(theme.value === "dark" ? "light" : "dark");
}

function reloadData(): void {
  if (hasLegacyFrame() && clickLegacyAction("reset-data")) return;
  void loadMeta();
  ElMessage.success("已重新加载数据。");
}

function openNotifications(): void {
  if (!clickLegacyAction("open-notifications")) {
    ElMessage.info("消息提醒仅在旧版页面内可用。");
  }
}

async function signOut(): Promise<void> {
  await logout();
  await router.replace("/login");
}

onMounted(async () => {
  document.documentElement.classList.toggle("dark", theme.value === "dark");
  if (!session.meta) await loadMeta();
  pollTimer = window.setInterval(() => {
    notificationCount.value = legacyNotificationCount();
  }, 3000);
});

onBeforeUnmount(() => {
  if (pollTimer) window.clearInterval(pollTimer);
});
</script>

<template>
  <div class="oa-shell">
    <aside class="oa-rail">
      <div class="oa-brand">
        <span class="oa-brand-mark">OA</span>
        <span class="oa-brand-text">
          <strong>办公资产</strong>
          <small>管理中台</small>
        </span>
      </div>

      <el-menu class="oa-nav" :default-active="route.path" router>
        <template v-for="group in NAV_GROUPS" :key="group">
          <template v-if="visibleItems.some((item) => item.group === group)">
            <div class="oa-nav-group">{{ group }}</div>
            <el-menu-item
              v-for="item in visibleItems.filter((entry) => entry.group === group)"
              :key="item.page"
              :index="item.path"
            >
              {{ item.title }}
            </el-menu-item>
          </template>
        </template>
      </el-menu>

      <div class="oa-rail-footer">
        当前版本 v{{ version }}
        <br />
        {{ session.user?.displayName || session.user?.username || "" }}
      </div>
    </aside>

    <main class="oa-main">
      <header class="oa-topbar">
        <div class="oa-topbar-title">
          <h1>{{ currentTitle }}</h1>
          <el-tag size="small" effect="plain" type="info">v{{ version }}</el-tag>
        </div>
        <div class="oa-topbar-actions">
          <el-badge :value="notificationCount" :hidden="!notificationCount">
            <el-button text @click="openNotifications">消息</el-button>
          </el-badge>
          <el-button text @click="toggleTheme">{{ theme === "dark" ? "日间" : "夜间" }}</el-button>
          <el-button text @click="reloadData">重新加载</el-button>
          <el-button text @click="router.push(PATH_BY_PAGE.settings)">设置</el-button>
          <el-button text type="danger" @click="signOut">退出</el-button>
        </div>
      </header>

      <section class="oa-content" :class="{ 'is-scroll': !route.meta.legacy }">
        <slot />
      </section>
    </main>
  </div>
</template>
