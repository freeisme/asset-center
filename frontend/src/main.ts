import { createApp } from "vue";
import ElementPlus from "element-plus";
import zhCn from "element-plus/es/locale/lang/zh-cn";
import "element-plus/dist/index.css";
import "element-plus/theme-chalk/dark/css-vars.css";
import "./styles/app.css";
import App from "./App.vue";
import { router } from "./router";
import { applyThemeColor, currentThemeColor } from "./theme";

const theme = window.localStorage.getItem("oa-theme") === "dark" ? "dark" : "light";
document.documentElement.dataset.theme = theme;
applyThemeColor(currentThemeColor(), { persist: false });

createApp(App).use(router).use(ElementPlus, { locale: zhCn }).mount("#app");
