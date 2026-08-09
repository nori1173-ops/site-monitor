<template>
  <v-app>
    <v-main class="d-flex align-center justify-center bg-background">
      <v-card class="pa-8 auth-card" width="420" elevation="0">
        <div class="text-center mb-6">
          <v-icon icon="mdi-pulse" color="primary" size="48" class="mb-2" />
          <h1 class="text-h5 font-weight-bold text-primary">Site Monitor</h1>
          <p class="text-body-2 text-medium-emphasis mt-1">
            {{ step === 'login' ? 'ログイン' : step === 'reset-email' ? 'パスワードリセット' : step === 'reset-code' ? '新しいパスワードの設定' : 'リセット完了' }}
          </p>
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

        <!-- ログイン -->
        <template v-if="step === 'login'">
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
              :loading="authStore.loading"
            >
              ログイン
            </v-btn>
          </v-form>

          <div class="text-center mt-3">
            <a
              href="#"
              class="text-body-2 text-primary font-weight-medium"
              @click.prevent="step = 'reset-email'"
            >
              パスワードを忘れた方
            </a>
          </div>

          <div class="text-center mt-2">
            <span class="text-body-2 text-medium-emphasis">アカウントをお持ちでないですか？</span>
            <router-link to="/signup" class="text-body-2 text-primary font-weight-medium ml-1">
              サインアップ
            </router-link>
          </div>
        </template>

        <!-- パスワードリセット: メールアドレス入力 -->
        <template v-if="step === 'reset-email'">
          <v-form @submit.prevent="handleResetRequest" ref="resetEmailFormRef">
            <v-text-field
              v-model="email"
              label="メールアドレス"
              type="email"
              prepend-inner-icon="mdi-email-outline"
              :rules="[(v: string) => !!v || 'メールアドレスを入力してください']"
              class="mb-4"
            />
            <v-btn
              type="submit"
              color="primary"
              block
              size="large"
              :loading="resetLoading"
            >
              リセットコードを送信
            </v-btn>
          </v-form>
          <div class="text-center mt-3">
            <a
              href="#"
              class="text-body-2 text-medium-emphasis"
              @click.prevent="step = 'login'; errorMessage = ''"
            >
              ログインに戻る
            </a>
          </div>
        </template>

        <!-- パスワードリセット: 確認コード + 新パスワード -->
        <template v-if="step === 'reset-code'">
          <v-alert type="info" variant="tonal" class="mb-4" density="compact">
            {{ email }} に確認コードを送信しました
          </v-alert>
          <v-form @submit.prevent="handleResetConfirm" ref="resetCodeFormRef">
            <v-text-field
              v-model="resetCode"
              label="確認コード"
              prepend-inner-icon="mdi-shield-key-outline"
              placeholder="6桁のコード"
              :rules="[(v: string) => !!v || '確認コードを入力してください']"
              class="mb-2"
            />
            <v-text-field
              v-model="newPassword"
              label="新しいパスワード"
              :type="showNewPassword ? 'text' : 'password'"
              prepend-inner-icon="mdi-lock-outline"
              :append-inner-icon="showNewPassword ? 'mdi-eye-off' : 'mdi-eye'"
              @click:append-inner="showNewPassword = !showNewPassword"
              :rules="[(v: string) => !!v || '新しいパスワードを入力してください', (v: string) => v.length >= 8 || '8文字以上で入力してください']"
              class="mb-4"
            />
            <v-btn
              type="submit"
              color="primary"
              block
              size="large"
              :loading="resetLoading"
            >
              パスワードを変更
            </v-btn>
          </v-form>
          <div class="text-center mt-3">
            <a
              href="#"
              class="text-body-2 text-medium-emphasis"
              @click.prevent="step = 'login'; errorMessage = ''"
            >
              ログインに戻る
            </a>
          </div>
        </template>

        <!-- リセット完了 -->
        <template v-if="step === 'reset-complete'">
          <v-alert type="success" variant="tonal" class="mb-4">
            パスワードが変更されました
          </v-alert>
          <v-btn
            color="primary"
            block
            size="large"
            @click="step = 'login'; errorMessage = ''"
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
import { resetPassword, confirmResetPassword } from 'aws-amplify/auth'

const router = useRouter()
const authStore = useAuthStore()

const step = ref<'login' | 'reset-email' | 'reset-code' | 'reset-complete'>('login')
const email = ref('')
const password = ref('')
const showPassword = ref(false)
const formRef = ref()
const resetEmailFormRef = ref()
const resetCodeFormRef = ref()
const errorMessage = ref('')
const resetLoading = ref(false)
const resetCode = ref('')
const newPassword = ref('')
const showNewPassword = ref(false)

async function handleLogin() {
  const { valid } = await formRef.value.validate()
  if (!valid) return

  try {
    errorMessage.value = ''
    authStore.error = null
    await authStore.login(email.value, password.value)
    router.push({ name: 'dashboard' })
  } catch (e: unknown) {
    errorMessage.value = e instanceof Error ? e.message : 'ログインに失敗しました'
  }
}

async function handleResetRequest() {
  const { valid } = await resetEmailFormRef.value.validate()
  if (!valid) return

  try {
    errorMessage.value = ''
    resetLoading.value = true
    await resetPassword({ username: email.value })
    step.value = 'reset-code'
  } catch (e: unknown) {
    errorMessage.value = e instanceof Error ? e.message : 'リセットコードの送信に失敗しました'
  } finally {
    resetLoading.value = false
  }
}

async function handleResetConfirm() {
  const { valid } = await resetCodeFormRef.value.validate()
  if (!valid) return

  try {
    errorMessage.value = ''
    resetLoading.value = true
    await confirmResetPassword({
      username: email.value,
      confirmationCode: resetCode.value,
      newPassword: newPassword.value,
    })
    step.value = 'reset-complete'
  } catch (e: unknown) {
    errorMessage.value = e instanceof Error ? e.message : 'パスワードの変更に失敗しました'
  } finally {
    resetLoading.value = false
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
