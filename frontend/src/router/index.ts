import { createRouter, createWebHistory, type RouteRecordRaw } from "vue-router";
import LegacyPage from "../views/LegacyPage.vue";
import LoginView from "../views/LoginView.vue";
import SettingsView from "../views/SettingsView.vue";
import { NAV_ITEMS, PATH_BY_PAGE } from "../navigation";
import { canViewPage, firstVisiblePath, refreshSession, session } from "../session";

const legacyRoutes: RouteRecordRaw[] = NAV_ITEMS.filter((item) => item.page !== "settings").map((item) => ({
  path: item.path,
  name: item.page,
  component: LegacyPage,
  meta: { title: item.title, page: item.page, legacy: true },
}));

const routes: RouteRecordRaw[] = [
  { path: "/login", name: "login", component: LoginView, meta: { title: "登录", public: true } },
  { path: "/", redirect: PATH_BY_PAGE.dashboard },
  { path: PATH_BY_PAGE.settings, name: "settings", component: SettingsView, meta: { title: "设置", page: "settings" } },
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
