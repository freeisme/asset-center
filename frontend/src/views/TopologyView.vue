<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import {
  listRacks,
  loadTopology,
  saveTopologyPositions,
  type Cable,
  type RackSummary,
  type TopologyNode,
  type TopologyPosition,
} from "../api/datacenter";
import { hasPermission } from "../session";

interface PlacedNode {
  node: TopologyNode;
  x: number;
  y: number;
  level: number;
}

const NODE_W = 168;
const NODE_H = 46;
const LEVEL_GAP = 230;
const ROW_GAP = 84;
const MARGIN = { left: 80, top: 56 };
const CATEGORY_LABELS: Record<string, string> = {
  server: "服务器",
  network: "网络",
  "patch-panel": "配线",
  power: "供电",
  storage: "存储",
  kvm: "KVM",
  cooling: "散热",
  other: "其他",
};

const loading = ref(false);
const racks = ref<RackSummary[]>([]);
const siteId = ref("");
const rackId = ref("");
const onlyLinked = ref(false);
const showLabels = ref(true);
const nodes = ref<TopologyNode[]>([]);
const links = ref<Cable[]>([]);
const savedPositions = ref<Record<string, TopologyPosition>>({});
const localPositions = ref<Record<string, { x: number; y: number }>>({});
const selectedId = ref("");
const dirty = ref(false);

const canUpdate = computed(() => hasPermission("rack_layout", "update"));
const sites = computed(() => {
  const map = new Map<string, string>();
  racks.value.forEach((item) => map.set(item.siteId, item.siteName));
  return [...map.entries()].map(([value, label]) => ({ value, label }));
});
const rackOptions = computed(() =>
  racks.value.filter((item) => !siteId.value || item.siteId === siteId.value),
);

const levels = computed(() => {
  const adjacency = new Map<string, Set<string>>();
  nodes.value.forEach((item) => adjacency.set(item.id, new Set()));
  links.value.forEach((link) => {
    adjacency.get(link.aPlacementId)?.add(link.bPlacementId);
    adjacency.get(link.bPlacementId)?.add(link.aPlacementId);
  });
  const degree = (id: string) => adjacency.get(id)?.size ?? 0;
  const root = [...nodes.value].sort((a, b) => degree(b.id) - degree(a.id))[0];
  const result = new Map<string, number>();
  if (!root) return result;
  result.set(root.id, 0);
  const queue: string[] = [root.id];
  while (queue.length) {
    const current = queue.shift() as string;
    const next = result.get(current) ?? 0;
    adjacency.get(current)?.forEach((neighbour) => {
      if (result.has(neighbour)) return;
      result.set(neighbour, next + 1);
      queue.push(neighbour);
    });
  }
  let fallback = Math.max(0, ...[...result.values()], 0);
  nodes.value.forEach((item) => {
    if (!result.has(item.id)) {
      fallback += 1;
      result.set(item.id, fallback);
    }
  });
  return result;
});

const placed = computed<PlacedNode[]>(() => {
  const byLevel = new Map<number, TopologyNode[]>();
  nodes.value.forEach((item) => {
    const level = levels.value.get(item.id) ?? 0;
    const list = byLevel.get(level) ?? [];
    list.push(item);
    byLevel.set(level, list);
  });
  const result: PlacedNode[] = [];
  [...byLevel.keys()]
    .sort((a, b) => a - b)
    .forEach((level) => {
      (byLevel.get(level) ?? [])
        .sort((a, b) => `${a.rackName}-${a.name}`.localeCompare(`${b.rackName}-${b.name}`))
        .forEach((node, index) => {
          const override = localPositions.value[node.id] ?? savedPositions.value[node.id];
          result.push({
            node,
            level,
            x: override?.x ?? MARGIN.left + level * LEVEL_GAP,
            y: override?.y ?? MARGIN.top + index * ROW_GAP,
          });
        });
    });
  return result;
});

const canvas = computed(() => {
  const maxX = Math.max(NODE_W + MARGIN.left, ...placed.value.map((item) => item.x + NODE_W));
  const maxY = Math.max(NODE_H + MARGIN.top, ...placed.value.map((item) => item.y + NODE_H));
  return { width: maxX + 40, height: maxY + 40 };
});

const selected = computed(() => nodes.value.find((item) => item.id === selectedId.value) ?? null);
const selectedLinks = computed(() =>
  links.value.filter(
    (link) => link.aPlacementId === selectedId.value || link.bPlacementId === selectedId.value,
  ),
);
const levelLabels = computed(() => {
  const seen = new Set<number>();
  placed.value.forEach((item) => seen.add(item.level));
  return [...seen]
    .sort((a, b) => a - b)
    .map((level, index) => ({
      level,
      label: index === 0 ? "边界 / 核心" : index === 1 ? "汇聚" : index === 2 ? "接入" : "末端",
    }));
});

function positionOf(nodeId: string): { x: number; y: number } {
  return placed.value.find((item) => item.node.id === nodeId) ?? { x: 0, y: 0 };
}

function linkPath(link: Cable): string {
  const from = positionOf(link.aPlacementId);
  const to = positionOf(link.bPlacementId);
  if (!from || !to) return "";
  const x1 = from.x;
  const y1 = from.y + NODE_H / 2;
  const x2 = to.x;
  const y2 = to.y + NODE_H / 2;
  const midX = (x1 + x2) / 2;
  return `M ${x1 + NODE_W} ${y1} L ${midX} ${y1} L ${midX} ${y2} L ${x2} ${y2}`;
}

function isHighlighted(link: Cable): boolean {
  return link.aPlacementId === selectedId.value || link.bPlacementId === selectedId.value;
}

async function loadData(): Promise<void> {
  loading.value = true;
  try {
    const payload = await loadTopology({
      siteId: siteId.value,
      rackId: rackId.value,
      onlyLinked: onlyLinked.value,
    });
    nodes.value = payload.nodes;
    links.value = payload.links;
    savedPositions.value = Object.fromEntries(
      payload.positions.map((item) => [item.nodeId, item]),
    );
    localPositions.value = {};
    dirty.value = false;
    if (selectedId.value && !nodes.value.some((item) => item.id === selectedId.value)) {
      selectedId.value = "";
    }
  } catch (error) {
    ElMessage.error(`拓扑加载失败：${(error as Error).message}`);
  } finally {
    loading.value = false;
  }
}

let drag: { id: string; offsetX: number; offsetY: number; moved: boolean } | null = null;

function onNodePointerDown(event: PointerEvent, item: PlacedNode): void {
  selectedId.value = item.node.id;
  if (!canUpdate.value) return;
  const rect = (event.currentTarget as SVGGElement).ownerSVGElement?.getBoundingClientRect();
  const scaleX = rect ? canvas.value.width / rect.width : 1;
  const scaleY = rect ? canvas.value.height / rect.height : 1;
  drag = {
    id: item.node.id,
    offsetX: item.x - (event.clientX - (rect?.left ?? 0)) * scaleX,
    offsetY: item.y - (event.clientY - (rect?.top ?? 0)) * scaleY,
    moved: false,
  };
  window.addEventListener("pointermove", onPointerMove);
  window.addEventListener("pointerup", onPointerUp, { once: true });
}

function onPointerMove(event: PointerEvent): void {
  if (!drag) return;
  const svg = document.querySelector<SVGSVGElement>(".topology-canvas");
  const rect = svg?.getBoundingClientRect();
  if (!rect) return;
  const scaleX = canvas.value.width / rect.width;
  const scaleY = canvas.value.height / rect.height;
  const x = Math.max(0, Math.round((event.clientX - rect.left) * scaleX + drag.offsetX));
  const y = Math.max(0, Math.round((event.clientY - rect.top) * scaleY + drag.offsetY));
  localPositions.value = { ...localPositions.value, [drag.id]: { x, y } };
  drag.moved = true;
  dirty.value = true;
}

function onPointerUp(): void {
  window.removeEventListener("pointermove", onPointerMove);
  drag = null;
}

async function savePositions(): Promise<void> {
  const payload: TopologyPosition[] = placed.value.map((item) => ({
    nodeId: item.node.id,
    x: item.x,
    y: item.y,
  }));
  if (!payload.length) return;
  try {
    const result = await saveTopologyPositions(payload);
    ElMessage.success(`已保存 ${result.saved} 个节点坐标。`);
    dirty.value = false;
    await loadData();
  } catch (error) {
    ElMessage.error(`保存布局失败：${(error as Error).message}`);
  }
}

function resetLayout(): void {
  localPositions.value = {};
  dirty.value = false;
  ElMessage.info("已按端口连接重新分层，未保存的拖动已清除。");
}

function buildExportSvg(): string {
  const nodesMarkup = placed.value
    .map(
      (item) => `<g transform="translate(${item.x},${item.y})">
        <rect width="${NODE_W}" height="${NODE_H}" fill="#ffffff" stroke="#8a8a8a"></rect>
        <text x="10" y="20" font-size="12" fill="#111111">${escapeXml(item.node.name)}</text>
        <text x="10" y="35" font-size="10" fill="#666666">${escapeXml(
          `${item.node.brandModel} · ${CATEGORY_LABELS[item.node.category] ?? item.node.category}`,
        )}</text>
      </g>`,
    )
    .join("");
  const linksMarkup = links.value
    .map((link) => {
      const path = linkPath(link);
      if (!path) return "";
      const label = showLabels.value
        ? `<text x="${(positionOf(link.aPlacementId).x + positionOf(link.bPlacementId).x) / 2}" y="${
            (positionOf(link.aPlacementId).y + positionOf(link.bPlacementId).y) / 2
          }" font-size="9" fill="#666666">${escapeXml(link.label || link.medium)}</text>`
        : "";
      return `<path d="${path}" fill="none" stroke="#8a8a8a" stroke-width="1.5"></path>${label}`;
    })
    .join("");
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${canvas.value.width} ${canvas.value.height}" width="${canvas.value.width}" height="${canvas.value.height}">
    <rect width="100%" height="100%" fill="#ffffff"></rect>${linksMarkup}${nodesMarkup}</svg>`;
}

function escapeXml(value: string): string {
  return value.replace(/[<>&"]/g, (char) =>
    char === "<" ? "&lt;" : char === ">" ? "&gt;" : char === "&" ? "&amp;" : "&quot;",
  );
}

function downloadBlob(blob: Blob, fileName: string): void {
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = fileName;
  link.click();
  URL.revokeObjectURL(link.href);
}

function exportSvg(): void {
  if (!placed.value.length) {
    ElMessage.warning("当前筛选条件下没有节点。");
    return;
  }
  downloadBlob(new Blob([buildExportSvg()], { type: "image/svg+xml" }), "网络拓扑.svg");
}

function exportPng(): void {
  if (!placed.value.length) return;
  const svg = buildExportSvg();
  const image = new Image();
  image.onload = () => {
    const canvasEl = document.createElement("canvas");
    canvasEl.width = canvas.value.width * 2;
    canvasEl.height = canvas.value.height * 2;
    const context = canvasEl.getContext("2d");
    if (!context) return;
    context.scale(2, 2);
    context.drawImage(image, 0, 0);
    canvasEl.toBlob((blob) => {
      if (blob) downloadBlob(blob, "网络拓扑.png");
    }, "image/png");
  };
  image.src = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
}

function printTopology(): void {
  const win = window.open("", "_blank");
  if (!win) {
    ElMessage.warning("浏览器拦截了打印窗口，请允许弹出窗口后重试。");
    return;
  }
  win.document.write(
    `<html><head><meta charset="utf-8" /><title>网络拓扑</title>
      <style>body{margin:16px;font-family:"Microsoft YaHei",Arial,sans-serif}
      h1{font-size:16px;margin:0 0 8px}p{color:#666;font-size:12px;margin:0 0 12px}</style></head>
      <body><h1>网络拓扑</h1><p>节点 ${placed.value.length} 个，链路 ${links.value.length} 条</p>${buildExportSvg()}</body></html>`,
  );
  win.document.close();
  win.focus();
  win.print();
}

onMounted(async () => {
  try {
    const payload = await listRacks();
    racks.value = payload.racks;
  } catch {
    racks.value = [];
  }
  await loadData();
});
</script>

<template>
  <el-card shadow="never" v-loading="loading">
    <template #header>
      <div class="topo-toolbar">
        <el-select v-model="siteId" placeholder="全部机房" clearable style="width: 180px" @change="loadData">
          <el-option v-for="item in sites" :key="item.value" :value="item.value" :label="item.label" />
        </el-select>
        <el-select v-model="rackId" placeholder="全部机柜" clearable style="width: 220px" @change="loadData">
          <el-option
            v-for="item in rackOptions"
            :key="item.id"
            :value="item.id"
            :label="`${item.siteName} / ${item.name}`"
          />
        </el-select>
        <el-switch v-model="onlyLinked" active-text="只看有链路的设备" @change="loadData" />
        <el-switch v-model="showLabels" active-text="链路标签" />
        <div class="spacer" />
        <el-button size="small" @click="resetLayout">重新布局</el-button>
        <el-button v-if="canUpdate" size="small" type="primary" :disabled="!dirty" @click="savePositions">
          保存布局
        </el-button>
        <el-button size="small" @click="exportSvg">导出 SVG</el-button>
        <el-button size="small" @click="exportPng">导出 PNG</el-button>
        <el-button size="small" @click="printTopology">打印</el-button>
      </div>
    </template>

    <div v-if="!nodes.length" class="empty-hint">
      当前筛选条件下没有设备。请先在“机柜视图”上架设备，并在“设备面板”里建立链路。
    </div>
    <div v-else class="topo-grid">
      <section>
        <svg
          class="topology-canvas"
          :viewBox="`0 0 ${canvas.width} ${canvas.height}`"
          :style="{ minHeight: `${Math.min(680, canvas.height)}px` }"
          role="img"
          aria-label="由端口连接自动生成的网络拓扑图"
        >
          <text
            v-for="item in levelLabels"
            :key="`tier-${item.level}`"
            :x="MARGIN.left + item.level * LEVEL_GAP - 60"
            y="30"
            class="tier-label"
          >
            {{ item.label }}
          </text>
          <g v-for="link in links" :key="`link-${link.id}`">
            <path :d="linkPath(link)" class="link" :class="{ highlight: isHighlighted(link) }" />
            <text
              v-if="showLabels"
              :x="(positionOf(link.aPlacementId).x + positionOf(link.bPlacementId).x) / 2"
              :y="(positionOf(link.aPlacementId).y + positionOf(link.bPlacementId).y) / 2"
              class="link-label"
            >
              {{ link.label || link.medium }}
            </text>
          </g>
          <g
            v-for="item in placed"
            :key="item.node.id"
            class="node"
            :class="{ selected: item.node.id === selectedId }"
            :transform="`translate(${item.x},${item.y})`"
            @pointerdown="onNodePointerDown($event, item)"
          >
            <rect :width="NODE_W" :height="NODE_H" rx="3" />
            <text x="10" y="20">{{ item.node.name }}</text>
            <text x="10" y="35" class="sub">
              {{ CATEGORY_LABELS[item.node.category] ?? item.node.category }} ·
              {{ item.node.linkedPortCount }}/{{ item.node.portCount }} 端口
            </text>
          </g>
        </svg>
      </section>

      <aside>
        <el-card shadow="never">
          <template #header><strong>节点详情</strong></template>
          <el-descriptions v-if="selected" :column="1" size="small" border>
            <el-descriptions-item label="设备">{{ selected.name }}</el-descriptions-item>
            <el-descriptions-item label="型号">{{ selected.brandModel || "—" }}</el-descriptions-item>
            <el-descriptions-item label="位置">
              {{ selected.siteName }} / {{ selected.rackName }} / 第 {{ selected.positionU }}U
            </el-descriptions-item>
            <el-descriptions-item label="端口">
              已连 {{ selected.linkedPortCount }} / 共 {{ selected.portCount }}
            </el-descriptions-item>
            <el-descriptions-item label="层级">第 {{ (levels.get(selected.id) ?? 0) + 1 }} 层</el-descriptions-item>
          </el-descriptions>
          <div v-else class="empty-hint">点击拓扑里的节点查看详情；拖动节点可微调布局。</div>

          <el-table v-if="selectedLinks.length" :data="selectedLinks" size="small" style="margin-top: 12px">
            <el-table-column label="链路" min-width="150">
              <template #default="{ row }">
                {{ row.label || `${row.aPortName} ↔ ${row.bPortName}` }}
              </template>
            </el-table-column>
            <el-table-column label="对端" min-width="150">
              <template #default="{ row }">
                {{ row.aPlacementId === selected?.id ? row.bPlacementName : row.aPlacementName }}
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </aside>
    </div>
  </el-card>
</template>

<style scoped>
.topo-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
}
.spacer {
  flex: 1;
}
.topo-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 320px);
  gap: 16px;
  align-items: start;
}
.topology-canvas {
  width: 100%;
  height: auto;
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color);
  border-radius: 4px;
  touch-action: none;
}
.tier-label {
  fill: var(--el-text-color-secondary);
  font-size: 11px;
}
.link {
  fill: none;
  stroke: var(--el-border-color-darker);
  stroke-width: 1.5;
}
.link.highlight {
  stroke: var(--el-color-primary);
  stroke-width: 2.5;
}
.link-label {
  fill: var(--el-text-color-secondary);
  font-size: 10px;
}
.node {
  cursor: grab;
}
.node rect {
  fill: var(--el-bg-color);
  stroke: var(--el-border-color-darker);
}
.node.selected rect {
  stroke: var(--el-color-primary);
  stroke-width: 2;
}
.node text {
  fill: var(--el-text-color-primary);
  font-size: 12px;
}
.node text.sub {
  fill: var(--el-text-color-secondary);
  font-size: 10px;
}
.empty-hint {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}
@media (max-width: 1100px) {
  .topo-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
