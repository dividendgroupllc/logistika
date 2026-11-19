// Telegram Mini App — mijoz kabineti (/tg sahifasi, logistika/www/tg.html).
import { createApp } from "vue";
import App from "./mini_app/App.vue";
import { router } from "./mini_app/router";

createApp(App).use(router).mount("#app");
