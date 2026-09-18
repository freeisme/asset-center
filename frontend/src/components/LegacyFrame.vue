<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from "vue";
import {
  legacyAuthenticated,
  pushLegacyPage,
  registerLegacyFrame,
} from "../legacyBridge";
import { applyThemeColor, currentThemeColor } from "../theme";

const props = defineProps<{ page: string }>();
const emit = defineEmits<{ (event: "page-change", page: string): void }>();

// 旧前端的侧边栏与顶栏由新外壳接管，这里只保留页面主体。
const FRAME_CHROME_CSS = `
  aside.sidebar { display: none !important; }
  .main-content { flex: 1 1 auto !important; min-width: 0 !important; margin-left: 0 !important; }
  body { overflow: auto !important; }
`;

const frame = ref<HTMLIFrameElement | null>(null);
let observer: MutationObserver | undefined;
let loaded = false;
let pushed = false;

interface LegacyApi {
  getPage?: () => string;
  setPage?: (page: string) => void;
  setTheme?: (theme: string) => void;
  isAuthenticated?: () => boolean;
}

function legacyApi(): LegacyApi | undefined {
  const win = frame.value?.contentWindow as unknown as { oaLegacy?: LegacyApi } | null;
  return win?.oaLegacy;
}

function frameDocument(): Document | null {
  try {
    return frame.value?.contentDocument ?? null;
  } catch {
    return null;
  }
}

function syncPage(): void {
  if (!loaded) return;
  if (pushLegacyPage(props.page)) pushed = true;
}

/** 旧前端要先完成会话校验才有权限表，权限没到位时切换页面会被它重置回首页。 */
function waitForLegacyAuth(attempt = 0): void {
  if (!loaded) return;
  if (legacyAuthenticated()) {
    syncPage();
    return;
  }
  if (attempt > 25) return;
  window.setTimeout(() => waitForLegacyAuth(attempt + 1), 200);
}

function onFrameLoad(): void {
  const doc = frameDocument();
  const win = frame.value?.contentWindow ?? null;
  if (!doc || !win) return;
  const style = doc.createElement("style");
  style.textContent = FRAME_CHROME_CSS;
  doc.head?.appendChild(style);
  registerLegacyFrame(win);
  applyThemeColor(currentThemeColor(), { persist: false });
  loaded = true;
  pushed = false;
  waitForLegacyAuth();

  const target = doc.querySelector("#appContent");
  if (!target) return;
  observer?.disconnect();
  observer = new MutationObserver(() => {
    if (!pushed) return;
    const current = legacyApi()?.getPage?.();
    if (current && current !== props.page) emit("page-change", current);
  });
  observer.observe(target, { childList: true });
}

watch(() => props.page, syncPage);

onMounted(() => {
  if (frame.value?.contentDocument?.readyState === "complete") onFrameLoad();
});

onBeforeUnmount(() => {
  observer?.disconnect();
  registerLegacyFrame(null);
});
</script>

<template>
  <iframe ref="frame" class="legacy-frame" src="/legacy/" title="旧版页面" @load="onFrameLoad" />
</template>
