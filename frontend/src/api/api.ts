import { tokenStore } from '../auth/tokenStore'
import { createApiClient } from './client'

/** The app-wide API client: sends the session token and drops it when the API says 401. */
export const api = createApiClient({
  getToken: () => tokenStore.get(),
  onUnauthorized: () => tokenStore.clear(),
})
