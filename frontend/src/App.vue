<script setup lang="ts">
import { computed } from "vue";
import { useRoute } from "vue-router";
import AppShell from "./layouts/AppShell.vue";

const route = useRoute();
const isPublicRoute = computed(() => Boolean(route.meta.public));
</script>

<template>
  <router-view v-if="isPublicRoute" />
  <AppShell v-else>
    <router-view />
  </AppShell>
</template>
