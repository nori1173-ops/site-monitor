<template>
  <v-app>
    <v-main class="d-flex align-center justify-center bg-background">
      <v-card class="pa-8 auth-card" width="420" elevation="0">
        <div class="text-center mb-6">
          <v-icon icon="mdi-pulse" color="primary" size="48" class="mb-2" />
          <h1 class="text-h5 font-weight-bold text-primary">Site Monitor</h1>
          <p class="text-body-2 text-medium-emphasis mt-1">アカウント登録</p>
        </div>

        <v-alert
          v-if="errorMessage"
          type="error"
          variant="tonal"
          class="mb-4"
          closable
          @click:close="errorMessage = ''"
        >
          {{ errorMessage }}
        </v-alert>

        <template v-if="step === 'register'">
          <v-form @submit.prevent="handleSignup" ref="formRef">
            <v-text-field
              v-model="email"
              label="メールアドレス"
              type="email"
              prepend-inner-icon="mdi-email-outline"
              :rules="emailRules"
              hint="@example.com ドメインのみ"
              persistent-hint
              class="mb-2"
            />
            <v-text-field
              v-model="password"
              label="パスワード"
              :type="showPassword ? 'text' : 'password'"
              prepend-inner-icon="mdi-lock-outline"
              :append-inner-icon="showPassword ? 'mdi-eye-off' : 'mdi-eye'"
              @click:append-inner="showPassword = !showPassword"
              :rules="passwordRules"
              class="mb-4"
            />
            <v-btn
              type="submit"
              color="primary"
              block
              size="large"
              :loading="authStore.loading"
            >
              サインアップ
            </v-btn>
          </v-form>
          <div class="text-center mt-4">
            <span class="text-body-2 text-medium-emphasis">アカウントをお持ちですか？</span>
            <router-link to="/login" class="text-body-2 text-primary font-weight-medium ml-1">
              ログイン
            </router-link>
          </div>
        </template>

        <template v-if="step === 'verify'">
          <v-alert type="info" variant="tonal" class="mb-4" density="compact">
            {{ email }} に確認コードを送信しました
          </v-alert>
          <v-form @submit.prevent="handleVerify">
            <v-text-field
              v-model="verificationCode"
              label="確認コード"
              prepend-inner-icon="mdi-shield-key-outline"
              placeholder="6桁のコード"
              class="mb-4"
            />
            <v-btn
              type="submit"
              color="primary"
              block
              size="large"
              :loading="authStore.loading"
            >
              確認
            </v-btn>
          </v-form>
        </template>

        <template v-if="step === 'complete'">
          <v-alert type="success" variant="tonal" class="mb-4">
            アカウント登録が完了しました
          </v-alert>
          <v-btn
            color="primary"
            block
            size="large"
            @click="router.push({ name: 'login' })"
          >
            ログインへ進む
          </v-btn>
        </template>
      </v-card>
    </v-main>
  </v-app>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const authStore = useAuthStore()
const step = ref<'register' | 'verify' | 'complete'>('register')
const email = ref('')
const password = ref('')
const showPassword = ref(false)
const verificationCode = ref('')
const errorMessage = ref('')
const formRef = ref()

const emailRules = [
  (v: string) => !!v || 'メールアドレスを入力してください',
  (v: string) => /.+@.+\..+/.test(v) || '有効なメールアドレスを入力してください',
  (v: string) => v.endsWith('@example.com') || '@example.com ドメインのみ登録可能です',
]

const passwordRules = [
  (v: string) => !!v || 'パスワードを入力してください',
  (v: string) => v.length >= 8 || '8文字以上で入力してください',
]

async function handleSignup() {
  const { valid } = await formRef.value.validate()
  if (!valid) return

  try {
    errorMessage.value = ''
    await authStore.register(email.value, password.value)
    step.value = 'verify'
  } catch (e: unknown) {
    errorMessage.value = e instanceof Error ? e.message : 'サインアップに失敗しました'
  }
}

async function handleVerify() {
  try {
    errorMessage.value = ''
    await authStore.confirmRegistration(email.value, verificationCode.value)
    step.value = 'complete'
  } catch (e: unknown) {
    errorMessage.value = e instanceof Error ? e.message : '確認コードの検証に失敗しました'
  }
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
