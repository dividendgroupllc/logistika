import { createRouter, createWebHashHistory } from "vue-router";
import Orders from "./pages/Orders.vue";
import Order from "./pages/Order.vue";
import Cargo from "./pages/Cargo.vue";
import Documents from "./pages/Documents.vue";
import Chats from "./pages/Chats.vue";
import Chat from "./pages/Chat.vue";
import Profile from "./pages/Profile.vue";

// Bot tugmalari shu manzillarni ochadi (telegram/keyboards.open_button).
export const TABS = ["/", "/hujjatlar", "/chatlar", "/profil"];

export const router = createRouter({
	history: createWebHashHistory(),
	routes: [
		{ path: "/", component: Orders },
		{ path: "/buyurtma/:name", component: Order, props: true },
		{ path: "/buyurtma/:name/chat", component: Chat, props: true },
		{ path: "/yuk/:name", component: Cargo, props: true },
		{ path: "/hujjatlar", component: Documents },
		{ path: "/chatlar", component: Chats },
		{ path: "/profil", component: Profile },
		{ path: "/:any(.*)", redirect: "/" },
	],
	scrollBehavior: () => ({ top: 0 }),
});
