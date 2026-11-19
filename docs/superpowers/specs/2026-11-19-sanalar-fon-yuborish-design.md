# Sanalar ketma-ketligi, fonda Telegram yuborish, WI fura oynasi — dizayn

Sana: 2026-11-19. Foydalanuvchi tasdiqladi ("ha").

1. Sanalar: Order.zakaz_sanasi ≤ Order Detail.sana ≤ fura chiqish (reja/fakt) ≤ kelish; Truck
   Dispatch.hujjat_sanasi ≥ OD.sana; LD.sana ≥ Order sanasi; WI.sana ≥ fura fakt chiqqan
   (bo'lmasa OD.sana); KZ Truck Loading.sana ≥ yuk omborga kelgan (fura fakt_kelish) sana;
   Peregruz.sana ≥ fura fakt chiqqan sana; KZ Transit.sana ≥ KZ yuklash sanasi;
   fakt_yetib_borgan ≥ KZ Transit.sana.
2. Ichki Deklaratsiya: pekin list'i bor furalar tanlovda chiqmaydi.
3. Fura qatoridagi "Xitoy haydovchi" → "Yangi yaratish" — 3 maydonli oyna (ism, raqam, telefon).
4. "Zavoddan chiqdi" — furalarni belgilab (yoki "Hammasi") yuborish; nakladnoysizi tanlanmaydi.
5. Kunlik kuzatuv "Fura" — OD furalaridan Select; bitta bo'lsa avtomatik.
6. Telegram yuborish (Zavoddan chiqdi, kunlik/KZ Send, Bugungi joylashuv, LD hujjatlari) — fon
   vazifasi; darhol "navbatga qo'yildi", natija realtime bildirishnoma.
7. Logistika Settings: `wi_kutish_kunlari` (standart 3) — WI'da kelish sanasi bugundan ±N kun
   ichidagi yo'ldagi furalar (sanasiz — doim); `eski_malumot_rejimi` — yoqilsa barcha yo'ldagi
   furalar va "bugundan oldin" taqiqi o'chadi (ketma-ketlik tekshiruvi qoladi).
