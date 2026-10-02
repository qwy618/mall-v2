<template>
  <div class="sys">
    <el-tabs v-model="active" class="sys__tabs">
      <el-tab-pane label="用户管理" name="user" />
      <el-tab-pane label="角色管理" name="role" />
    </el-tabs>
    <!-- 仅挂载当前激活的页，避免两个列表同时拉取 -->
    <UserIndex v-if="active === 'user'" />
    <RoleIndex v-else />
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import UserIndex from './user/index.vue'
import RoleIndex from './role/index.vue'

const active = ref<'user' | 'role'>('user')
</script>

<style scoped>
.sys__tabs {
  margin-bottom: 4px;
}
</style>
