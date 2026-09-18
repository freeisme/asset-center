<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import {
  createCable,
  createPort,
  getDeviceType,
  importPortsFromTemplate,
  listCables,
  listDeviceTypes,
  listRackPorts,
  loadTopology,
  removeCable,
  removePort,
  updatePort,
  type Cable,
  type DeviceTypeDetail,
  type DeviceTypeSummary,
  type RackPort,
  type RackPortDevice,
  type RackPortsPayload,
  type TopologyNode,
} from "../api/datacenter";
import { hasPermission } from "../session";

const KIND_LABELS: Record<string, string> = {
  network: "电口",
  fiber: "光口",
  power: "电源",
  console: "Console",
  other: "其他",
};
const MEDIUM_OPTIONS = [
  { value: "cat5e", label: "超五类" },
  { value: "cat6", label: "六类" },
  { value: "fiber-om3", label: "多模光纤 OM3" },
  { value: "fiber-os2", label: "单模光纤 OS2" },
  { value: "dac", label: "DAC 高速线" },
  { value: "power", label: "电源线" },
  { value: "console", label: "Console 线" },
  { value: "other", label: "其他" },
];
const STATUS_LABELS: Record<string, string> = {
  in_use: "在用",
  idle: "闲置",
  repair: "维修",
  retired: "报废",
  shared: "公用",
};

const PANEL = { paddingLeft: 36, paddingTop: 30, rowHeight: 30 };

const loading = ref(false);
const nodes = ref<TopologyNode[]>([]);
const deviceTypes = ref<DeviceTypeSummary[]>([]);
const selectedNodeId = ref("");
const rackPorts = ref<RackPortsPayload | null>(null);
const deviceType = ref<DeviceTypeDetail | null>(null);
const cables = ref<Cable[]>([]);
const selectedPortId = ref("");
const pendingA = ref<RackPort | null>(null);
const cableDialog = ref(false);
const cableForm = ref<{ medium: string; lengthM: number; label: string }>({
  medium: "cat6",
  lengthM: 3,
  label: "",
});
const portDialog = ref(false);
const portEditing = ref<RackPort | null>(null);
const portForm = ref<Record<string, unknown>>({});
const templateDialog = ref(false);
const templateCatalogId = ref("");
const applyHeight = ref(false);

const canCreate = computed(() => hasPermission("rack_layout", "create"));
const canUpdate = computed(() => hasPermission("rack_layout", "update"));
const canDelete = computed(() => hasPermission("rack_layout", "delete"));
const device = computed<RackPortDevice | null>(
  () => rackPorts.value?.placements.find((item) => item.placementId === selectedNodeId.value) ?? null,
);
const selectedPort = computed<RackPort | null>(
  () => device.value?.ports.find((item) => item.id === selectedPortId.value) ?? null,
);
const panelPorts = computed(() => (device.value?.ports ?? []).filter((item) => item.face === "front"));
const panelRows = computed(() => {
  const rows = new Map<number, RackPort[]>();
  panelPorts.value.forEach((port) => {
    const list = rows.get(port.rowIndex) ?? [];
    list.push(port);
    rows.set(port.rowIndex, list);
  });
  return [...rows.entries()]
    .sort((a, b) => a[0] - b[0])
    .map(([row, ports]) => ({
      row,
      ports: ports.sort((a, b) => a.positionIndex - b.positionIndex),
    }));
});
const panelWidth = computed(() => {
  const widest = Math.max(12, ...panelRows.value.map((row) => row.ports.length));
  return PANEL.paddingLeft + widest * 20 + 24;
});
const panelHeight = computed(() => PANEL.paddingTop + Math.max(1, panelRows.value.length) * PANEL.rowHeight + 16);

function portX(port: RackPort): number {
  return PANEL.paddingLeft + (port.positionIndex - 1) * 20;
}

function portY(port: RackPort): number {
  return PANEL.paddingTop + (port.rowIndex - 1) * PANEL.rowHeight;
}

function portWidth(port: RackPort): number {
  return port.kind === "power" ? 24 : port.kind === "fiber" ? 18 : 16;
}

function portClass(port: RackPort): string {
  if (port.status === "down") return "port-down";
  if (port.status === "disabled") return "port-disabled";
  return port.cableId ? "port-used" : "port-idle";
}

async function loadNodes(): Promise<void> {
  loading.value = true;
  try {
    const payload = await loadTopology({});
    nodes.value = payload.nodes;
    const current = nodes.value.find((item) => item.id === selectedNodeId.value) ?? nodes.value[0];
    if (current) await selectNode(current.id);
  } catch (error) {
    ElMessage.error(`设备加载失败：${(error as Error).message}`);
  } finally {
    loading.value = false;
  }
}

async function loadDeviceTypes(): Promise<void> {
  try {
    const payload = await listDeviceTypes();
    deviceTypes.value = payload.deviceTypes;
  } catch {
    deviceTypes.value = [];
  }
}

async function selectNode(nodeId: string): Promise<void> {
  selectedNodeId.value = nodeId;
  selectedPortId.value = "";
  pendingA.value = null;
  const node = nodes.value.find((item) => item.id === nodeId);
  if (!node) return;
  loading.value = true;
  try {
    const [ports, cablePayload] = await Promise.all([
      listRackPorts(node.rackId),
      listCables({ rackId: node.rackId }),
    ]);
    rackPorts.value = ports.rack;
    cables.value = cablePayload.cables;
    await matchDeviceType();
  } catch (error) {
    ElMessage.error(`端口加载失败：${(error as Error).message}`);
  } finally {
    loading.value = false;
  }
}

async function matchDeviceType(): Promise<void> {
  const current = device.value;
  if (!current?.brandModel) {
    deviceType.value = null;
    return;
  }
  const match = deviceTypes.value.find((item) =>
    current.brandModel.toLowerCase().includes(item.model.toLowerCase()),
  );
  deviceType.value = match ? (await getDeviceType(match.id)).deviceType : null;
}

function onPortClick(port: RackPort): void {
  selectedPortId.value = port.id;
  if (!canCreate.value) return;
  if (!pendingA.value) {
    pendingA.value = port;
    ElMessage.info(`已选择 ${port.name}，再点另一个端口即可连线。`);
    return;
  }
  if (pendingA.value.id === port.id) {
    pendingA.value = null;
    return;
  }
  cableForm.value = { medium: "cat6", lengthM: 3, label: "" };
  cableDialog.value = true;
}

async function submitCable(): Promise<void> {
  const a = pendingA.value;
  const b = selectedPort.value;
  if (!a || !b) return;
  try {
    await createCable({
      aPortId: a.id,
      bPortId: b.id,
      medium: cableForm.value.medium,
      lengthM: cableForm.value.lengthM,
      label: cableForm.value.label,
    });
    ElMessage.success("链路已建立。");
    cableDialog.value = false;
    pendingA.value = null;
    await selectNode(selectedNodeId.value);
  } catch (error) {
    ElMessage.error(`建立链路失败：${(error as Error).message}`);
  }
}

function openPortDialog(port: RackPort | null): void {
  portEditing.value = port;
  portForm.value = port
    ? { ...port }
    : { name: "", type: "", kind: "network", face: "front", rowIndex: 1, positionIndex: 1, status: "unknown", notes: "" };
  portDialog.value = true;
}

async function submitPort(): Promise<void> {
  const current = device.value;
  if (!current) return;
  try {
    if (portEditing.value) {
      await updatePort(portEditing.value.id, portForm.value);
      ElMessage.success("端口已更新。");
    } else {
      await createPort(current.placementId, portForm.value);
      ElMessage.success("端口已新增。");
    }
    portDialog.value = false;
    await selectNode(selectedNodeId.value);
  } catch (error) {
    ElMessage.error(`保存端口失败：${(error as Error).message}`);
  }
}

async function deletePort(port: RackPort): Promise<void> {
  try {
    const { value } = await ElMessageBox.prompt(
      `删除端口「${port.name}」会同时删除它的链路，请填写原因`,
      "删除端口",
      { confirmButtonText: "确认删除", cancelButtonText: "取消" },
    );
    await removePort(port.id, String(value ?? ""));
    ElMessage.success("端口已删除。");
    await selectNode(selectedNodeId.value);
  } catch (error) {
    if (error !== "cancel") ElMessage.error(`删除端口失败：${String(error)}`);
  }
}

async function deleteCable(cable: Cable): Promise<void> {
  try {
    const { value } = await ElMessageBox.prompt(
      `删除链路「${cable.aPlacementName}/${cable.aPortName} ↔ ${cable.bPlacementName}/${cable.bPortName}」的原因`,
      "删除链路",
      { confirmButtonText: "确认删除", cancelButtonText: "取消" },
    );
    await removeCable(cable.id, String(value ?? ""));
    ElMessage.success("链路已删除。");
    await selectNode(selectedNodeId.value);
  } catch (error) {
    if (error !== "cancel") ElMessage.error(`删除链路失败：${String(error)}`);
  }
}

async function submitTemplateImport(): Promise<void> {
  const current = device.value;
  if (!current || !templateCatalogId.value) {
    ElMessage.warning("请选择型号。");
    return;
  }
  try {
    const result = await importPortsFromTemplate(current.placementId, {
      catalogId: templateCatalogId.value,
      applyHeight: applyHeight.value,
    });
    ElMessage.success(`生成端口完成：新增 ${result.created} 个，跳过 ${result.skipped} 个。`);
    templateDialog.value = false;
    await selectNode(selectedNodeId.value);
  } catch (error) {
    ElMessage.error(`生成端口失败：${(error as Error).message}`);
  }
}

onMounted(async () => {
  await loadDeviceTypes();
  await loadNodes();
});
</script>

<template>
  <el-card shadow="never" v-loading="loading">
    <template #header>
      <div class="panel-toolbar">
        <el-select v-model="selectedNodeId" style="width: 340px" filterable @change="selectNode">
          <el-option
            v-for="item in nodes"
            :key="item.id"
            :value="item.id"
            :label="`${item.siteName} / ${item.rackName} / ${item.name}`"
          />
        </el-select>
        <el-tag v-if="deviceType" type="success" effect="plain">
          型号库：{{ deviceType.manufacturer }} {{ deviceType.model }}
        </el-tag>
        <el-tag v-else type="info" effect="plain">未匹配型号库（端口为手工维护）</el-tag>
        <div class="spacer" />
        <el-button v-if="canCreate && device" size="small" @click="templateDialog = true">按型号生成端口</el-button>
        <el-button v-if="canCreate && device" size="small" @click="openPortDialog(null)">新增端口</el-button>
      </div>
    </template>

    <div v-if="!device" class="empty-hint">还没有上架设备，请先在“机柜视图”里上架并生成端口。</div>
    <div v-else class="panel-grid">
      <section>
        <div class="panel-meta">
          <strong>{{ device.name }}</strong>
          <span>{{ device.brandModel }} ｜ 第 {{ device.positionU }}U ｜ {{ device.ports.length }} 个端口</span>
        </div>
        <svg
          class="device-panel"
          :viewBox="`0 0 ${panelWidth} ${panelHeight}`"
          :style="{ minHeight: `${panelHeight}px` }"
          role="img"
          :aria-label="`${device.name} 前面板端口图`"
        >
          <rect
            x="2"
            y="2"
            :width="panelWidth - 4"
            :height="panelHeight - 4"
            rx="4"
            class="panel-frame"
          />
          <image
            v-if="deviceType?.imageFrontPath"
            :href="deviceType.imageFrontPath"
            x="6"
            :y="6"
            :width="panelWidth - 12"
            :height="panelHeight - 12"
            preserveAspectRatio="none"
            class="panel-image"
          />
          <text x="12" :y="panelHeight - 8" class="panel-caption">
            {{ deviceType ? `${deviceType.manufacturer} ${deviceType.model}` : device.brandModel }}
          </text>
          <g v-for="row in panelRows" :key="row.row">
            <g v-for="port in row.ports" :key="port.id">
              <rect
                :x="portX(port)"
                :y="portY(port)"
                :width="portWidth(port)"
                height="18"
                rx="2"
                class="port"
                :class="[portClass(port), { selected: port.id === selectedPortId, pending: port.id === pendingA?.id }]"
                @click="onPortClick(port)"
              />
              <text :x="portX(port) + portWidth(port) / 2" :y="portY(port) + 30" class="port-label">
                {{ port.name.replace(/[^0-9]/g, "").slice(-2) }}
              </text>
            </g>
          </g>
        </svg>
        <div class="legend">
          <span><i class="swatch used" /> 已连接</span>
          <span><i class="swatch idle" /> 空闲</span>
          <span><i class="swatch down" /> 断开</span>
          <span>点两个端口即可连线；点单个端口查看链路</span>
        </div>
      </section>

      <aside>
        <el-card shadow="never" class="side-card">
          <template #header>
            <div class="side-head"><strong>端口列表</strong><span>{{ device.ports.length }} 个</span></div>
          </template>
          <el-table :data="device.ports" size="small" height="280" @row-click="(row: RackPort) => (selectedPortId = row.id)">
            <el-table-column prop="name" label="端口" width="90" />
            <el-table-column label="类型" width="90">
              <template #default="{ row }">{{ KIND_LABELS[row.kind] ?? row.kind }}</template>
            </el-table-column>
            <el-table-column label="对端">
              <template #default="{ row }">
                {{ row.peerPlacementName ? `${row.peerPlacementName}/${row.peerPortName}` : "—" }}
              </template>
            </el-table-column>
            <el-table-column label="操作" width="120">
              <template #default="{ row }">
                <el-button v-if="canUpdate" link size="small" @click.stop="openPortDialog(row)">编辑</el-button>
                <el-button v-if="canDelete" link type="danger" size="small" @click.stop="deletePort(row)">
                  删除
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>

        <el-card shadow="never" class="side-card">
          <template #header><strong>链路详情</strong></template>
          <el-descriptions v-if="selectedPort" :column="1" size="small" border>
            <el-descriptions-item label="本端">{{ device.name }} / {{ selectedPort.name }}</el-descriptions-item>
            <el-descriptions-item label="对端">
              {{ selectedPort.peerPlacementName ? `${selectedPort.peerPlacementName} / ${selectedPort.peerPortName}` : "—" }}
            </el-descriptions-item>
            <el-descriptions-item label="介质">{{ selectedPort.cableMedium || "—" }}</el-descriptions-item>
            <el-descriptions-item label="链路标签">{{ selectedPort.cableLabel || "—" }}</el-descriptions-item>
          </el-descriptions>
          <div v-else class="empty-hint">点击面板或列表里的端口查看链路。</div>
        </el-card>

        <el-card shadow="never" class="side-card">
          <template #header><strong>本机柜链路</strong></template>
          <el-table :data="cables" size="small" height="220">
            <el-table-column label="A 端" min-width="140">
              <template #default="{ row }">{{ row.aPlacementName }} / {{ row.aPortName }}</template>
            </el-table-column>
            <el-table-column label="B 端" min-width="140">
              <template #default="{ row }">{{ row.bPlacementName }} / {{ row.bPortName }}</template>
            </el-table-column>
            <el-table-column prop="medium" label="介质" width="90" />
            <el-table-column v-if="canDelete" label="操作" width="80">
              <template #default="{ row }">
                <el-button link type="danger" size="small" @click.stop="deleteCable(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </aside>
    </div>

    <el-dialog v-model="cableDialog" title="建立链路" width="420px">
      <el-form label-position="top" size="small">
        <el-form-item label="A 端">
          <el-input :model-value="pendingA ? `${pendingA.name}` : ''" disabled />
        </el-form-item>
        <el-form-item label="B 端">
          <el-input :model-value="selectedPort ? `${selectedPort.name}` : ''" disabled />
        </el-form-item>
        <el-form-item label="介质">
          <el-select v-model="cableForm.medium" style="width: 100%">
            <el-option v-for="item in MEDIUM_OPTIONS" :key="item.value" :value="item.value" :label="item.label" />
          </el-select>
        </el-form-item>
        <el-form-item label="长度（米）">
          <el-input-number v-model="cableForm.lengthM" :min="0.5" :max="10000" :step="0.5" />
        </el-form-item>
        <el-form-item label="标签">
          <el-input v-model="cableForm.label" placeholder="例如：SW-A01-GE24 → SRV-A01-NIC1" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="cableDialog = false">取消</el-button>
        <el-button type="primary" @click="submitCable">建立链路</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="portDialog" :title="portEditing ? '编辑端口' : '新增端口'" width="420px">
      <el-form label-position="top" size="small">
        <el-form-item label="端口名称">
          <el-input v-model="portForm.name" placeholder="例如 GE24" />
        </el-form-item>
        <el-form-item label="端口类型">
          <el-select v-model="portForm.kind" style="width: 100%">
            <el-option v-for="(label, value) in KIND_LABELS" :key="value" :value="value" :label="label" />
          </el-select>
        </el-form-item>
        <el-form-item label="类型标识">
          <el-input v-model="portForm.type" placeholder="例如 1000base-t / 10gbase-x-sfpp" />
        </el-form-item>
        <el-form-item label="面板 / 行 / 位">
          <el-select v-model="portForm.face" style="width: 110px">
            <el-option value="front" label="前面板" />
            <el-option value="rear" label="后面板" />
          </el-select>
          <el-input-number v-model="portForm.rowIndex" :min="1" :max="20" style="margin: 0 8px" />
          <el-input-number v-model="portForm.positionIndex" :min="1" :max="48" />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="portForm.status" style="width: 100%">
            <el-option value="unknown" label="未知" />
            <el-option value="up" label="正常" />
            <el-option value="down" label="断开" />
            <el-option value="disabled" label="停用" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="portDialog = false">取消</el-button>
        <el-button type="primary" @click="submitPort">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="templateDialog" title="按型号生成端口" width="460px">
      <el-form label-position="top" size="small">
        <el-form-item label="型号">
          <el-select v-model="templateCatalogId" filterable style="width: 100%">
            <el-option
              v-for="item in deviceTypes"
              :key="item.id"
              :value="item.id"
              :label="`${item.manufacturer} ${item.model}（${item.portCount} 个端口）`"
            />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-checkbox v-model="applyHeight">同时按型号高度调整设备占用（{{ deviceType?.uHeight ?? "—" }}U）</el-checkbox>
        </el-form-item>
      </el-form>
      <div class="empty-hint">
        型号库由 <code>tools/import_device_types.py</code> 从 NetBox devicetype-library 导入（含面板图）。
      </div>
      <template #footer>
        <el-button @click="templateDialog = false">取消</el-button>
        <el-button type="primary" @click="submitTemplateImport">生成端口</el-button>
      </template>
    </el-dialog>
  </el-card>
</template>

<style scoped>
.panel-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
}
.spacer {
  flex: 1;
}
.panel-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 380px);
  gap: 16px;
  align-items: start;
}
.panel-meta {
  display: flex;
  align-items: baseline;
  gap: 12px;
  margin-bottom: 8px;
}
.panel-meta span {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}
.device-panel {
  width: 100%;
  height: auto;
  background: var(--el-fill-color-lighter);
  border: 1px solid var(--el-border-color);
  border-radius: 4px;
}
.panel-frame {
  fill: var(--el-bg-color);
  stroke: var(--el-border-color);
}
.panel-image {
  opacity: 0.55;
}
.panel-caption {
  fill: var(--el-text-color-secondary);
  font-size: 10px;
}
.port {
  fill: var(--el-fill-color-darker);
  stroke: var(--el-border-color-darker);
  cursor: pointer;
}
.port-used {
  fill: var(--el-text-color-primary);
}
.port-down {
  fill: var(--el-color-danger);
}
.port-disabled {
  fill: var(--el-fill-color);
}
.port.selected {
  stroke: var(--el-color-primary);
  stroke-width: 2;
}
.port.pending {
  stroke: var(--el-color-warning);
  stroke-width: 2;
}
.port-label {
  fill: var(--el-text-color-secondary);
  font-size: 9px;
  text-anchor: middle;
}
.legend {
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
  margin-top: 8px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
}
.swatch {
  display: inline-block;
  width: 10px;
  height: 10px;
  margin-right: 4px;
  border: 1px solid var(--el-border-color-darker);
}
.swatch.used {
  background: var(--el-text-color-primary);
}
.swatch.idle {
  background: var(--el-fill-color-darker);
}
.swatch.down {
  background: var(--el-color-danger);
}
.side-card {
  margin-bottom: 12px;
}
.side-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.empty-hint {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}
@media (max-width: 1100px) {
  .panel-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
