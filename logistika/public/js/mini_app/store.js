import { reactive } from "vue";
import { call } from "./api";
import { setLang } from "./i18n";

export const store = reactive({ me: null, unread: 0 });

export async function loadMe() {
	store.me = await call("me");
	setLang(store.me.lang);
	return store.me;
}
