<script setup lang="ts">
import { computed, reactive, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import { firstVisiblePath, loadMeta, login, session } from "../session";

const route = useRoute();
const router = useRouter();
const form = reactive({ username: "", password: "" });
const submitting = ref(false);
const errorMessage = ref("");
const version = computed(() => session.meta?.version || __APP_VERSION__);

async function submit(): Promise<void> {
  if (!form.username.trim() || !form.password) {
    errorMessage.value = "请输入账号和密码。";
    return;
  }
  submitting.value = true;
  errorMessage.value = "";
  try {
    await login(form.username.trim(), form.password);
    await loadMeta();
    ElMessage.success("登录成功。");
    const redirect = typeof route.query.redirect === "string" ? route.query.redirect : "";
    await router.replace(redirect || firstVisiblePath());
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "登录失败。";
  } finally {
    submitting.value = false;
  }
}

void loadMeta();
</script>

<template>
  <div class="oa-login">
    <el-card class="oa-login-card">
      <template #header>
        <div style="display: flex; align-items: center; justify-content: space-between">
          <strong>办公资产管理系统</strong>
          <el-tag size="small" effect="plain" type="info">v{{ version }}</el-tag>
        </div>
      </template>
      <el-form label-position="top" @submit.prevent="submit">
        <el-form-item label="账号">
          <el-input v-model="form.username" autocomplete="username" placeholder="请输入账号" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input
            v-model="form.password"
            type="password"
            show-password
            autocomplete="current-password"
            placeholder="请输入密码"
            @keyup.enter="submit"
          />
        </el-form-item>
        <el-alert v-if="errorMessage" :title="errorMessage" type="error" :closable="false" show-icon />
        <el-button
          type="primary"
          style="width: 100%; margin-top: 12px"
          :loading="submitting"
          @click="submit"
        >
          登录
        </el-button>
      </el-form>
    </el-card>
  </div>
</template>
