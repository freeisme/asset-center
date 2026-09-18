import { api } from "./client";

export interface RackSummary {
  id: string;
  code: string;
  name: string;
  heightU: number;
  siteId: string;
  siteName: string;
  siteType?: string;
  usedUnits: number;
  deviceCount: number;
}

export interface Placement {
  id: string;
  rackId: string;
  sourceKind: "computer" | "custom";
  computerId?: string;
  inventoryModelId?: string;
  name: string;
  brandModel: string;
  category: string;
  positionU: number;
  uHeight: number;
  face: "front" | "rear" | "both";
  status?: string;
  assetCode?: string;
  serialNumber?: string;
  ownerLabel?: string;
  notes?: string;
}

export interface RackDetail extends RackSummary {
  placements: Placement[];
  freeUnits: number;
}

export interface AvailableComputer {
  computerId: string;
  name: string;
  brandModel: string;
  category: string;
  status: string;
  assetCode: string;
  serialNumber: string;
  ownerLabel: string;
}

export interface AvailableModel {
  inventoryModelId: string;
  name: string;
  brandModel: string;
  category: string;
  quantity: number;
  typeName: string;
  uHeight: number;
}

export interface RackPort {
  id: string;
  name: string;
  type: string;
  kind: "network" | "fiber" | "power" | "console" | "other";
  face: "front" | "rear";
  rowIndex: number;
  positionIndex: number;
  direction: string;
  speed: string;
  status: "up" | "down" | "disabled" | "unknown";
  notes: string;
  cableId?: string;
  cableLabel?: string;
  cableMedium?: string;
  cableStatus?: string;
  peerPlacementId?: string;
  peerPlacementName?: string;
  peerPortName?: string;
}

export interface RackPortDevice {
  placementId: string;
  name: string;
  brandModel: string;
  category: string;
  positionU: number;
  uHeight: number;
  face: string;
  catalogSlug: string;
  ports: RackPort[];
}

export interface RackPortsPayload {
  id: string;
  name: string;
  code: string;
  heightU: number;
  siteName: string;
  placements: RackPortDevice[];
  portCount: number;
}

export interface Cable {
  id: string;
  medium: string;
  lengthM: number | null;
  label: string;
  status: string;
  notes: string;
  aPortId: string;
  bPortId: string;
  aPortName: string;
  bPortName: string;
  aPlacementId: string;
  bPlacementId: string;
  aPlacementName: string;
  bPlacementName: string;
  aRackName: string;
  bRackName: string;
  aSiteName: string;
  bSiteName: string;
}

export interface DeviceTypeSummary {
  id: string;
  slug: string;
  manufacturer: string;
  model: string;
  partNumber: string;
  uHeight: number;
  category: string;
  frontImage: number;
  rearImage: number;
  imageFrontPath: string;
  imageRearPath: string;
  source: string;
  portCount: number;
}

export interface DeviceTypePort {
  name: string;
  type: string;
  kind: RackPort["kind"];
  face: "front" | "rear";
  rowIndex: number;
  positionIndex: number;
}

export interface DeviceTypeDetail extends DeviceTypeSummary {
  ports: DeviceTypePort[];
}

export interface TopologyNode {
  id: string;
  name: string;
  brandModel: string;
  category: string;
  status: string;
  positionU: number;
  uHeight: number;
  rackId: string;
  rackName: string;
  siteId: string;
  siteName: string;
  portCount: number;
  linkedPortCount: number;
}

export interface TopologyPosition {
  nodeId: string;
  x: number;
  y: number;
}

export interface TopologyPayload {
  nodes: TopologyNode[];
  links: Cable[];
  positions: TopologyPosition[];
}

export function listRacks(): Promise<{ racks: RackSummary[] }> {
  return api<{ racks: RackSummary[] }>("/api/rack-layout/racks");
}

export function getRack(rackId: string): Promise<{ rack: RackDetail }> {
  return api<{ rack: RackDetail }>(`/api/rack-layout/racks/${encodeURIComponent(rackId)}`);
}

export function availableDevices(keyword = ""): Promise<{
  computers: AvailableComputer[];
  inventoryModels: AvailableModel[];
}> {
  const query = keyword ? `?keyword=${encodeURIComponent(keyword)}` : "";
  return api(`/api/rack-layout/available${query}`);
}

export function placeDevice(rackId: string, payload: Record<string, unknown>): Promise<{ id: string }> {
  return api(`/api/rack-layout/racks/${encodeURIComponent(rackId)}/placements`, {
    method: "POST",
    body: payload,
  });
}

export function updatePlacement(placementId: string, payload: Record<string, unknown>): Promise<unknown> {
  return api(`/api/rack-layout/placements/${encodeURIComponent(placementId)}`, {
    method: "PUT",
    body: payload,
  });
}

export function removePlacement(placementId: string, reason: string): Promise<unknown> {
  return api(`/api/rack-layout/placements/${encodeURIComponent(placementId)}/remove`, {
    method: "POST",
    body: { reason },
  });
}

export function listRackPorts(rackId: string): Promise<{ rack: RackPortsPayload }> {
  return api<{ rack: RackPortsPayload }>(
    `/api/rack-layout/racks/${encodeURIComponent(rackId)}/ports`,
  );
}

export function importPortsFromTemplate(
  placementId: string,
  payload: { catalogId?: string; slug?: string; applyHeight?: boolean; uHeight?: number },
): Promise<{ created: number; skipped: number }> {
  return api(`/api/rack-layout/placements/${encodeURIComponent(placementId)}/ports/import`, {
    method: "POST",
    body: payload,
  });
}

export function createPort(placementId: string, payload: Record<string, unknown>): Promise<{ id: string }> {
  return api(`/api/rack-layout/placements/${encodeURIComponent(placementId)}/ports`, {
    method: "POST",
    body: payload,
  });
}

export function updatePort(portId: string, payload: Record<string, unknown>): Promise<unknown> {
  return api(`/api/rack-layout/ports/${encodeURIComponent(portId)}`, {
    method: "PUT",
    body: payload,
  });
}

export function removePort(portId: string, reason: string): Promise<unknown> {
  return api(`/api/rack-layout/ports/${encodeURIComponent(portId)}/remove`, {
    method: "POST",
    body: { reason },
  });
}

export function listCables(params: { rackId?: string; siteId?: string } = {}): Promise<{ cables: Cable[] }> {
  const query = new URLSearchParams();
  if (params.rackId) query.set("rackId", params.rackId);
  if (params.siteId) query.set("siteId", params.siteId);
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return api<{ cables: Cable[] }>(`/api/rack-layout/cables${suffix}`);
}

export function createCable(payload: Record<string, unknown>): Promise<{ id: string }> {
  return api("/api/rack-layout/cables", { method: "POST", body: payload });
}

export function updateCable(cableId: string, payload: Record<string, unknown>): Promise<unknown> {
  return api(`/api/rack-layout/cables/${encodeURIComponent(cableId)}`, {
    method: "PUT",
    body: payload,
  });
}

export function removeCable(cableId: string, reason: string): Promise<unknown> {
  return api(`/api/rack-layout/cables/${encodeURIComponent(cableId)}/remove`, {
    method: "POST",
    body: { reason },
  });
}

export function listDeviceTypes(keyword = ""): Promise<{ deviceTypes: DeviceTypeSummary[] }> {
  const query = keyword ? `?keyword=${encodeURIComponent(keyword)}` : "";
  return api<{ deviceTypes: DeviceTypeSummary[] }>(`/api/device-types${query}`);
}

export function getDeviceType(catalogId: string): Promise<{ deviceType: DeviceTypeDetail }> {
  return api<{ deviceType: DeviceTypeDetail }>(`/api/device-types/${encodeURIComponent(catalogId)}`);
}

export function importDeviceType(payload: {
  source: "inline" | "netbox";
  yamlText?: string;
  slug?: string;
}): Promise<{ catalogId: string; slug: string; portCount: number }> {
  return api("/api/device-types/import", { method: "POST", body: payload });
}

export function loadTopology(params: {
  siteId?: string;
  rackId?: string;
  onlyLinked?: boolean;
}): Promise<TopologyPayload> {
  const query = new URLSearchParams();
  if (params.siteId) query.set("siteId", params.siteId);
  if (params.rackId) query.set("rackId", params.rackId);
  if (params.onlyLinked) query.set("onlyLinked", "1");
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return api<TopologyPayload>(`/api/rack-layout/topology${suffix}`);
}

export function saveTopologyPositions(
  nodes: TopologyPosition[],
): Promise<{ saved: number }> {
  return api("/api/rack-layout/topology/positions", { method: "POST", body: { nodes } });
}
