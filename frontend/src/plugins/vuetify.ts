import 'vuetify/styles'
import '@mdi/font/css/materialdesignicons.css'
import { createVuetify } from 'vuetify'
import * as components from 'vuetify/components'
import * as directives from 'vuetify/directives'
import { ja } from 'vuetify/locale'

export default createVuetify({
  components,
  directives,
  locale: {
    locale: 'ja',
    messages: { ja },
  },
  theme: {
    defaultTheme: 'light',
    themes: {
      light: {
        colors: {
          primary: '#1E40AF',
          'primary-darken-1': '#1E3A8A',
          secondary: '#3B82F6',
          accent: '#D97706',
          background: '#F1F5F9',
          surface: '#FFFFFF',
          'surface-variant': '#F8FAFC',
          error: '#DC2626',
          warning: '#F59E0B',
          success: '#16A34A',
          info: '#0EA5E9',
          'on-primary': '#FFFFFF',
          'on-secondary': '#FFFFFF',
          'on-surface': '#1E293B',
          'on-background': '#1E293B',
        },
      },
    },
  },
  defaults: {
    VCard: {
      elevation: 0,
      rounded: 'lg',
    },
    VBtn: {
      rounded: 'lg',
    },
    VTextField: {
      variant: 'outlined',
      density: 'comfortable',
    },
  },
})
