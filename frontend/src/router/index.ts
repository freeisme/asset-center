import type { Component } from "vue";
import { createRouter, createWebHistory, type RouteRecordRaw } from "vue-router";
import LegacyPage from "../views/LegacyPage.vue";
import LoginView from "../views/LoginView.vue";
import SettingsView from "../views/SettingsView.vue";
import RackLayoutView from "../views/RackLayoutView.vue";
import DevicePanelView from "../views/DevicePanelView.vue";
import TopologyView from "../views/TopologyView.vue";
import { NAV_ITEMS, PATH_BY_PAGE } from "../navigation";
import { canViewPage, firstVisiblePath, refreshSession, session } from "../session";

/** 已迁移到 Vue 的页面；其余页面继续由旧前端在 iframe 中渲染。 */
const MIGRATED_VIEWS: Record<string, Component> = {
  settings: SettingsView,
  rackLayout: RackLayoutView,
  devicePanel: DevicePanelView,
  topology: TopologyView,
};

const vueRoutes: RouteRecordRaw[] = NAV_ITEMS.filter((item) => MIGRATED_VIEWS[item.page]).map((item) => ({
  path: item.path,
  name: item.page,
  component: MIGRATED_VIEWS[item.page],
  meta: { title: item.title, page: item.page },
}));

const legacyRoutes: RouteRecordRaw[] = NAV_ITEMS.filter((item) => !MIGRATED_VIEWS[item.page]).map((item) => ({
  path: item.path,
  name: item.page,
  component: LegacyPage,
  meta: { title: item.title, page: item.page, legacy: true },
}));

const routes: RouteRecordRaw[] = [
  { path: "/login", name: "login", component: LoginView, meta: { title: "登录", public: true } },
  { path: "/", redirect: PATH_BY_PAGE.dashboard },
  ...vueRoutes,
  ...legacyRoutes,
  { path: "/:pathMatch(.*)*", redirect: PATH_BY_PAGE.dashboard },
];

export const router = createRouter({
  history: createWebHistory(),
  routes,
});

router.beforeEach(async (to) => {
  if (!session.ready) await refreshSession();
  const isPublic = Boolean(to.meta.public);
  if (isPublic) {
    return session.user ? { path: firstVisiblePath() } : true;
  }
  if (!session.user) {
    return { path: "/login", query: to.fullPath === "/" ? {} : { redirect: to.fullPath } };
  }
  const page = typeof to.meta.page === "string" ? to.meta.page : "";
  if (page && !canViewPage(page)) {
    return { path: firstVisiblePath() };
  }
  return true;
});
