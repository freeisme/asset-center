<script setup lang="ts">
import { computed } from "vue";
import { useRoute, useRouter } from "vue-router";
import LegacyFrame from "../components/LegacyFrame.vue";
import { PAGE_BY_PATH, PATH_BY_PAGE } from "../navigation";

const route = useRoute();
const router = useRouter();

const page = computed(() => PAGE_BY_PATH[route.path] ?? "dashboard");

function onPageChange(next: string): void {
  const path = PATH_BY_PAGE[next];
  if (path && path !== route.path) void router.replace(path);
}
</script>

<template>
  <LegacyFrame :page="page" @page-change="onPageChange" />
</template>
