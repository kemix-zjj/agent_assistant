<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { ROLE_OPTIONS, useUserStore } from '@/stores/user'
import type { ViewRole } from '@/stores/user'
import { useApprovalStore } from '@/stores/approval'

const route = useRoute()
const userStore = useUserStore()
const approvalStore = useApprovalStore()

const activeMenu = computed(() => route.path)

const roleOptions = ROLE_OPTIONS

function handleRoleChange(value: ViewRole) {
  userStore.switchRole(value)
  approvalStore.refreshPendingCount()
}
</script>

<template>
  <div class="at-layout">
    <aside class="at-sidebar">
      <div class="at-logo">
        <span class="at-logo-mark">乐</span>
        <span class="at-logo-text">乐石数智助理</span>
      </div>

      <el-menu :default-active="activeMenu" router class="at-menu">
        <el-menu-item index="/new-task">
          <span>新建任务</span>
        </el-menu-item>
        <el-menu-item index="/assistants">
          <span>助理 &amp; 技能 &amp; 连接器</span>
        </el-menu-item>
      </el-menu>

      <div class="at-sidebar-foot">
        <el-select
          :model-value="userStore.role"
          size="small"
          class="at-role-select"
          @change="handleRoleChange"
        >
          <el-option
            v-for="item in roleOptions"
            :key="item.value"
            :label="item.label"
            :value="item.value"
          />
        </el-select>
        <div class="at-user">
          <el-avatar :size="28">{{ userStore.currentUser.avatar }}</el-avatar>
          <div class="at-user-info">
            <div class="at-user-name">{{ userStore.currentUser.name }}</div>
            <div class="at-user-org">厦门乐石科技有限公司</div>
          </div>
        </div>
      </div>
    </aside>

    <main class="at-main">
      <RouterView />
    </main>
  </div>
</template>

<style scoped>
.at-layout {
  display: flex;
  height: 100vh;
  overflow: hidden;
}

.at-sidebar {
  width: 240px;
  flex: 0 0 240px;
  display: flex;
  flex-direction: column;
  background: #fff;
  border-right: 1px solid var(--at-border);
}

.at-logo {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 16px;
  font-weight: 600;
}

.at-logo-mark {
  width: 24px;
  height: 24px;
  border-radius: 6px;
  background: var(--at-brand);
  color: #fff;
  font-size: 13px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.at-menu {
  flex: 1;
  border-right: none;
  overflow-y: auto;
}

.at-sidebar-foot {
  padding: 12px;
  border-top: 1px solid var(--at-border);
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.at-role-select {
  width: 100%;
}

.at-user {
  display: flex;
  align-items: center;
  gap: 8px;
}

.at-user-name {
  font-size: 13px;
  font-weight: 500;
}

.at-user-org {
  font-size: 12px;
  color: var(--at-text-weak);
}

.at-main {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}
</style>
