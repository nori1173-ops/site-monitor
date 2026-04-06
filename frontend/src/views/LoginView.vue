<template>
  <v-app>
    <v-main class="d-flex align-center justify-center bg-background">
      <v-card class="pa-8 auth-card" width="420" elevation="0">
        <div class="text-center mb-6">
          <v-icon icon="mdi-pulse" color="primary" size="48" class="mb-2" />
          <h1 class="text-h5 font-weight-bold text-primary">Web Alive Monitoring</h1>
          <p class="text-body-2 text-medium-emphasis mt-1">ログイン</p>
        </div>

        <v-form @submit.prevent="handleLogin" ref="formRef">
          <v-text-field
            v-model="email"
            label="メールアドレス"
            type="email"
            prepend-inner-icon="mdi-email-outline"
            :rules="[(v: string) => !!v || 'メールアドレスを入力してください']"
            class="mb-2"
          />
          <v-text-field
            v-model="password"
            label="パスワード"
            :type="showPassword ? 'text' : 'password'"
            prepend-inner-icon="mdi-lock-outline"
            :append-inner-icon="showPassword ? 'mdi-eye-off' : 'mdi-eye'"
            @click:append-inner="showPassword = !showPassword"
            :rules="[(v: string) => !!v || 'パスワードを入力してください']"
            class="mb-4"
          />
          <v-btn
            type="submit"
            color="primary"
            block
            size="large"
            :loading="loading"
          >
            ログイン
          </v-btn>
        </v-form>

        <div class="text-center mt-4">
          <span class="text-body-2 text-medium-emphasis">アカウントをお持ちでないですか？</span>
          <router-link to="/signup" class="text-body-2 text-primary font-weight-medium ml-1">
            サインアップ
          </router-link>
        </div>
      </v-card>
    </v-main>
  </v-app>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const auth = useAuthStore()
const email = ref('miyaji@osasi.co.jp')
const password = ref('')
const showPassword = ref(false)
const loading = ref(false)
const formRef = ref()

async function handleLogin() {
  const { valid } = await formRef.value.validate()
  if (!valid) return
  loading.value = true
  setTimeout(() => {
    auth.login(email.value)
    loading.value = false
    router.push({ name: 'dashboard' })
  }, 300)
}
</script>

<style scoped>
.auth-card {
  border: 1px solid #E2E8F0;
  border-radius: 16px;
}
.bg-background {
  background-color: #F1F5F9;
  min-height: 100vh;
}
</style>
