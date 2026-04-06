<template>
  <v-app>
    <v-app-bar color="primary" density="comfortable" elevation="2">
      <v-app-bar-title class="font-weight-bold">
        <v-icon icon="mdi-pulse" class="mr-2" />
        Web Alive Monitoring
      </v-app-bar-title>
      <template v-slot:append>
        <span class="text-body-2 mr-3 d-none d-sm-inline">{{ auth.email }}</span>
        <v-btn icon="mdi-logout" variant="text" @click="handleLogout" />
      </template>
    </v-app-bar>
    <v-main>
      <slot />
    </v-main>
  </v-app>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const router = useRouter()

function handleLogout() {
  auth.logout()
  router.push({ name: 'login' })
}
</script>
