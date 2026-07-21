import { mount } from 'svelte'
import { get } from 'svelte/store'
import './app.css'
import App from './App.svelte'
import { loadBaseCurrencies } from './api'
import { locale, loadLocale, tx } from './i18n'

// Preload the active locale so a persisted non-default language renders on the
// first paint instead of flashing English. `en` is bundled and resolves
// instantly; any other locale is awaited here. A failed chunk fetch still
// mounts the app (translations fall back to English).
try {
  await loadLocale(get(locale))
} catch {
  // ignore: mount anyway and degrade to English
}

const target = document.getElementById('app')!
let app = null
try {
  const baseCurrencies = await loadBaseCurrencies()
  app = mount(App, { target, props: { baseCurrencies } })
} catch {
  target.setAttribute('role', 'alert')
  target.textContent = tx('errors.requestFailed')
}

export default app
