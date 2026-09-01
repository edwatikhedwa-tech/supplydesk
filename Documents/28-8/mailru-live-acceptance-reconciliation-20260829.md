# SupplyDesk - Mail.ru Live Acceptance - P0 Reconciliation

> **HISTORICAL — NOT CURRENT.** Это read-only evidence snapshot от 29 августа
> 2026 года. Текущее состояние и более поздние результаты находятся в
> [`../../ai/CURRENT_STATE.md`](../../ai/CURRENT_STATE.md) и
> [`../../ai/reports/`](../../ai/reports/).

Read-only evidence snapshot; no business-state writes, no SMTP DATA.

## Campaign
- campaign_id: `2`; request_id: `1059`; planned: `130`
- provider/status: `yandex` / `paused_for_health`; pause_reason: `provider_spam_or_policy_rejection`
- process effective MAIL_OUTGOING_DISABLED: `1` (verified from PID 27368); `.env` does not define it, so no restart was performed

## Campaign accounting
- Sent: `44`
- Failed: `2`
- Delivery unknown: `0`
- Queued: `84`
- Queued strictly untouched: `82`
- Queued non-untouched: `2`
- Suppressed: `0`
- Answered: `0`
- Total accounted: `44 + 2 + 82 + 2 + 0 + 0 + 0 = 130`

## All 84 queued targets
Columns: target_id | ordinal | supplier_id | normalized_email | message_id | job_id | message_status/job_status | attempts | mail_send_attempt | irreversible_reached | provider/account history | accepted evidence | delivery_unknown evidence | suppression | reply | Mail.ru first-send

| target | ordinal | supplier | normalized email | message | job | msg/job | attempts | attempt | irreversible | provider/account | accepted | unknown | suppression | reply | Mail.ru first-send |
|---:|---:|---:|---|---:|---:|---|---:|---|---|---|---:|---:|---|---|---|
| 28 | 27 | 3216 | sale@protopka.su | 57 | 49 | queued/queued | 1 | #1 transient_rejected/transient irreversible=1 stage=- code=- | YES | 1/yandex | 0 | 0 | NO | NO | NO |
| 33 | 32 | 3221 | info@mflame.ru | 62 | 54 | queued/queued | 1 | #1 transient_rejected/transient irreversible=1 stage=- code=- | YES | 1/yandex | 0 | 0 | NO | NO | NO |
| 50 | 49 | 3238 | info@tmf-shop.ru | 79 | 71 | queued/queued | 0 | NONE | NO | 1/yandex | 0 | 0 | NO | NO | YES |
| 51 | 50 | 3239 | info@pechi-market.ru | 80 | 72 | queued/queued | 0 | NONE | NO | 1/yandex | 0 | 0 | NO | NO | YES |
| 52 | 51 | 3240 | 1@pechnik.su | 81 | 73 | queued/queued | 0 | NONE | NO | 1/yandex | 0 | 0 | NO | NO | YES |
| 53 | 52 | 3241 | info@apk.ru | 82 | 74 | queued/queued | 0 | NONE | NO | 1/yandex | 0 | 0 | NO | NO | YES |
| 54 | 53 | 3242 | info@pro-komfort.com | 83 | 75 | queued/queued | 0 | NONE | NO | 1/yandex | 0 | 0 | NO | NO | YES |
| 55 | 54 | 3243 | 1@litkom.com | 84 | 76 | queued/queued | 0 | NONE | NO | 1/yandex | 0 | 0 | NO | NO | YES |
| 56 | 55 | 3244 | sales@pechimag.ru | 85 | 77 | queued/queued | 0 | NONE | NO | 1/yandex | 0 | 0 | NO | NO | YES |
| 57 | 56 | 3245 | info@childresidence.ru | 86 | 78 | queued/queued | 0 | NONE | NO | 1/yandex | 0 | 0 | NO | NO | YES |
| 58 | 57 | 3246 | info@rs-teplo.ru | 87 | 79 | queued/queued | 0 | NONE | NO | 1/yandex | 0 | 0 | NO | NO | YES |
| 59 | 58 | 3247 | sale@mrmag.ru | 88 | 80 | queued/queued | 0 | NONE | NO | 1/yandex | 0 | 0 | NO | NO | YES |
| 60 | 59 | 3248 | info@kamin-island.ru | 89 | 81 | queued/queued | 0 | NONE | NO | 1/yandex | 0 | 0 | NO | NO | YES |
| 61 | 60 | 3249 | stroy-kamin@mail.ru | 90 | 82 | queued/queued | 0 | NONE | NO | 1/yandex | 0 | 0 | NO | NO | YES |
| 62 | 61 | 3250 | ptk.10region@yandex.ru | 91 | 83 | queued/queued | 0 | NONE | NO | 1/yandex | 0 | 0 | NO | NO | YES |
| 63 | 62 | 3251 | info@delovpechke.ru | 92 | 84 | queued/queued | 0 | NONE | NO | 1/yandex | 0 | 0 | NO | NO | YES |
| 64 | 63 | 3252 | frs@t-m-f.ru | 93 | 85 | queued/queued | 0 | NONE | NO | 1/yandex | 0 | 0 | NO | NO | YES |
| 65 | 64 | 3253 | brozex@brozex.com | 94 | 86 | queued/queued | 0 | NONE | NO | 1/yandex | 0 | 0 | NO | NO | YES |
| 66 | 65 | 3254 | order@aquadom.info | 95 | 87 | queued/queued | 0 | NONE | NO | 1/yandex | 0 | 0 | NO | NO | YES |
| 67 | 66 | 3255 | info@kaminvdom.ru | 96 | 88 | queued/queued | 0 | NONE | NO | 1/yandex | 0 | 0 | NO | NO | YES |
| 68 | 67 | 3256 | info@�����������73.�� | 97 | 89 | queued/queued | 0 | NONE | NO | 1/yandex | 0 | 0 | NO | NO | YES |
| 69 | 68 | 3257 | support@prometall.ru | 98 | 90 | queued/queued | 0 | NONE | NO | 1/yandex | 0 | 0 | NO | NO | YES |
| 70 | 69 | 3258 | 89087178701@mail.ru | 99 | 91 | queued/queued | 0 | NONE | NO | 1/yandex | 0 | 0 | NO | NO | YES |
| 71 | 70 | 3259 | info@dver1.ru | 100 | 92 | queued/queued | 0 | NONE | NO | 1/yandex | 0 | 0 | NO | NO | YES |
| 72 | 71 | 3260 | sale@centropech.ru | 101 | 93 | queued/queued | 0 | NONE | NO | 1/yandex | 0 | 0 | NO | NO | YES |
| 73 | 72 | 3261 | info@lit-kom.ru | 102 | 94 | queued/queued | 0 | NONE | NO | 1/yandex | 0 | 0 | NO | NO | YES |
| 74 | 73 | 3262 | info@pechki.su | 103 | 95 | queued/queued | 0 | NONE | NO | 1/yandex | 0 | 0 | NO | NO | YES |
| 75 | 74 | 3263 | ural59@bk.ru | 104 | 96 | queued/queued | 0 | NONE | NO | 1/yandex | 0 | 0 | NO | NO | YES |
| 76 | 75 | 3264 | krasnodar@remix-kamin.ru | 105 | 97 | queued/queued | 0 | NONE | NO | 1/yandex | 0 | 0 | NO | NO | YES |
| 77 | 76 | 3265 | ekotermkrym@gmail.com | 106 | 98 | queued/queued | 0 | NONE | NO | 1/yandex | 0 | 0 | NO | NO | YES |
| 78 | 77 | 3266 | u002f1915039caf274cfb8dcc6b9ce9aaf948@sentry.iddqd.yandex.net | 107 | 99 | queued/queued | 0 | NONE | NO | 1/yandex | 0 | 0 | NO | NO | YES |
| 79 | 78 | 3267 | admin@1688.ru | 108 | 100 | queued/queued | 0 | NONE | NO | 1/yandex | 0 | 0 | NO | NO | YES |
| 80 | 79 | 3268 | zavod@feringer.ru | 109 | 101 | queued/queued | 0 | NONE | NO | 1/yandex | 0 | 0 | NO | NO | YES |
| 81 | 80 | 3269 | admin@mirpechek.ru | 110 | 102 | queued/queued | 0 | NONE | NO | 1/yandex | 0 | 0 | NO | NO | YES |
| 82 | 81 | 3270 | info@c-s-k.ru | 111 | 103 | queued/queued | 0 | NONE | NO | 1/yandex | 0 | 0 | NO | NO | YES |
| 83 | 82 | 3271 | romotop@inbox.ru | 112 | 104 | queued/queued | 0 | NONE | NO | 1/yandex | 0 | 0 | NO | NO | YES |
| 84 | 83 | 3272 | info@pechs.ru | 113 | 105 | queued/queued | 0 | NONE | NO | 1/yandex | 0 | 0 | NO | NO | YES |
| 85 | 84 | 3273 | zakaz@100-pechey.ru | 114 | 106 | queued/queued | 0 | NONE | NO | 1/yandex | 0 | 0 | NO | NO | YES |
| 86 | 85 | 3274 | utc@teplodar.ru | 115 | 107 | queued/queued | 0 | NONE | NO | 1/yandex | 0 | 0 | NO | NO | YES |
| 87 | 86 | 3275 | info@stout.ru | 116 | 108 | queued/queued | 0 | NONE | NO | 1/yandex | 0 | 0 | NO | NO | YES |
| 88 | 87 | 3276 | kamin@belfortkamin.ru | 117 | 109 | queued/queued | 0 | NONE | NO | 1/yandex | 0 | 0 | NO | NO | YES |
| 89 | 88 | 3277 | ir@kaspi.kz | 118 | 110 | queued/queued | 0 | NONE | NO | 1/yandex | 0 | 0 | NO | NO | YES |
| 90 | 89 | 3278 | pechi-d@mail.ru | 119 | 111 | queued/queued | 0 | NONE | NO | 1/yandex | 0 | 0 | NO | NO | YES |
| 91 | 90 | 3279 | info@pech-dlya-doma.ru | 120 | 112 | queued/queued | 0 | NONE | NO | 1/yandex | 0 | 0 | NO | NO | YES |
| 92 | 91 | 3280 | domkaminov@mail.ru | 121 | 113 | queued/queued | 0 | NONE | NO | 1/yandex | 0 | 0 | NO | NO | YES |
| 93 | 92 | 3281 | dostavka@pechilux.ru | 122 | 114 | queued/queued | 0 | NONE | NO | 1/yandex | 0 | 0 | NO | NO | YES |
| 94 | 93 | 3282 | mail@kamicenter.ru | 123 | 115 | queued/queued | 0 | NONE | NO | 1/yandex | 0 | 0 | NO | NO | YES |
| 95 | 94 | 3283 | info@kaminnext.ru | 124 | 116 | queued/queued | 0 | NONE | NO | 1/yandex | 0 | 0 | NO | NO | YES |
| 96 | 95 | 3284 | tmo@rupechi.ru | 125 | 117 | queued/queued | 0 | NONE | NO | 1/yandex | 0 | 0 | NO | NO | YES |
| 97 | 96 | 3285 | shop@dymohod-pech.ru | 126 | 118 | queued/queued | 0 | NONE | NO | 1/yandex | 0 | 0 | NO | NO | YES |
| 98 | 97 | 3286 | sale@pechi-group.ru | 127 | 119 | queued/queued | 0 | NONE | NO | 1/yandex | 0 | 0 | NO | NO | YES |
| 99 | 98 | 3287 | zakaz@pechki66.ru | 128 | 120 | queued/queued | 0 | NONE | NO | 1/yandex | 0 | 0 | NO | NO | YES |
| 100 | 99 | 3288 | 100kaminov@gmail.com | 129 | 121 | queued/queued | 0 | NONE | NO | 1/yandex | 0 | 0 | NO | NO | YES |
| 101 | 100 | 3289 | salon4@m-kamin.ru | 130 | 122 | queued/queued | 0 | NONE | NO | 1/yandex | 0 | 0 | NO | NO | YES |
| 102 | 101 | 3290 | zakaz@woodson.ru | 131 | 123 | queued/queued | 0 | NONE | NO | 1/yandex | 0 | 0 | NO | NO | YES |
| 103 | 102 | 3291 | shop@pechi96.ru | 132 | 124 | queued/queued | 0 | NONE | NO | 1/yandex | 0 | 0 | NO | NO | YES |
| 104 | 103 | 3292 | info@teplodvor.by | 133 | 125 | queued/queued | 0 | NONE | NO | 1/yandex | 0 | 0 | NO | NO | YES |
| 105 | 104 | 3293 | info@kaminchi.ru | 134 | 126 | queued/queued | 0 | NONE | NO | 1/yandex | 0 | 0 | NO | NO | YES |
| 106 | 105 | 3294 | info@satom.ru | 135 | 127 | queued/queued | 0 | NONE | NO | 1/yandex | 0 | 0 | NO | NO | YES |
| 107 | 106 | 3295 | sale@agsk.ru | 136 | 128 | queued/queued | 0 | NONE | NO | 1/yandex | 0 | 0 | NO | NO | YES |
| 108 | 107 | 3296 | bskoffice@yandex.ru | 137 | 129 | queued/queued | 0 | NONE | NO | 1/yandex | 0 | 0 | NO | NO | YES |
| 109 | 108 | 3297 | super@yutnoff.ru | 138 | 130 | queued/queued | 0 | NONE | NO | 1/yandex | 0 | 0 | NO | NO | YES |
| 110 | 109 | 3298 | sales@kamenka.ru | 139 | 131 | queued/queued | 0 | NONE | NO | 1/yandex | 0 | 0 | NO | NO | YES |
| 111 | 110 | 3299 | info@bestkaminy.ru | 140 | 132 | queued/queued | 0 | NONE | NO | 1/yandex | 0 | 0 | NO | NO | YES |
| 112 | 111 | 3300 | info@proxima-light.pro | 141 | 133 | queued/queued | 0 | NONE | NO | 1/yandex | 0 | 0 | NO | NO | YES |
| 113 | 112 | 3301 | art.izba.by@gmail.com | 142 | 134 | queued/queued | 0 | NONE | NO | 1/yandex | 0 | 0 | NO | NO | YES |
| 114 | 113 | 3302 | zakaz@magazin-pechi.ru | 143 | 135 | queued/queued | 0 | NONE | NO | 1/yandex | 0 | 0 | NO | NO | YES |
| 115 | 114 | 3303 | zakaz@amazonka.by | 144 | 136 | queued/queued | 0 | NONE | NO | 1/yandex | 0 | 0 | NO | NO | YES |
| 116 | 115 | 3304 | demyan-igor1@yandex.ru | 145 | 137 | queued/queued | 0 | NONE | NO | 1/yandex | 0 | 0 | NO | NO | YES |
| 117 | 116 | 3305 | market@100-kpd.ru | 146 | 138 | queued/queued | 0 | NONE | NO | 1/yandex | 0 | 0 | NO | NO | YES |
| 118 | 117 | 3306 | mail@master-sauna.ru | 147 | 139 | queued/queued | 0 | NONE | NO | 1/yandex | 0 | 0 | NO | NO | YES |
| 119 | 118 | 3307 | info@kamin-vdom.ru | 148 | 140 | queued/queued | 0 | NONE | NO | 1/yandex | 0 | 0 | NO | NO | YES |
| 120 | 119 | 3308 | info@kamin-expert.com | 149 | 141 | queued/queued | 0 | NONE | NO | 1/yandex | 0 | 0 | NO | NO | YES |
| 121 | 120 | 3309 | magazin@saunabas.ru | 150 | 142 | queued/queued | 0 | NONE | NO | 1/yandex | 0 | 0 | NO | NO | YES |
| 122 | 121 | 3310 | 12@psflamma.com | 151 | 143 | queued/queued | 0 | NONE | NO | 1/yandex | 0 | 0 | NO | NO | YES |
| 123 | 122 | 3311 | info@tvoy-usadba.ru | 152 | 144 | queued/queued | 0 | NONE | NO | 1/yandex | 0 | 0 | NO | NO | YES |
| 124 | 123 | 3312 | zakaz@kaminru.ru | 153 | 145 | queued/queued | 0 | NONE | NO | 1/yandex | 0 | 0 | NO | NO | YES |
| 125 | 124 | 3313 | teplopar@bk.ru | 154 | 146 | queued/queued | 0 | NONE | NO | 1/yandex | 0 | 0 | NO | NO | YES |
| 126 | 125 | 3314 | info@pechiptz.ru | 155 | 147 | queued/queued | 0 | NONE | NO | 1/yandex | 0 | 0 | NO | NO | YES |
| 127 | 126 | 3315 | sfera.termo@yandex.ru | 156 | 148 | queued/queued | 0 | NONE | NO | 1/yandex | 0 | 0 | NO | NO | YES |
| 128 | 127 | 3316 | zakaz@el-kamino.ru | 157 | 149 | queued/queued | 0 | NONE | NO | 1/yandex | 0 | 0 | NO | NO | YES |
| 129 | 128 | 3317 | info@kotlipechi.ru | 158 | 150 | queued/queued | 0 | NONE | NO | 1/yandex | 0 | 0 | NO | NO | YES |
| 130 | 129 | 3318 | info@bis-st.ru | 159 | 151 | queued/queued | 0 | NONE | NO | 1/yandex | 0 | 0 | NO | NO | YES |
| 131 | 130 | 3319 | info@agromash-tpk.ru | 160 | 152 | queued/queued | 0 | NONE | NO | 1/yandex | 0 | 0 | NO | NO | YES |

## Queued non-untouched
### #27 - `sale@protopka.su`
- target: `28`; job: `49`; message: `57`
- attempt history: id=29 attempt=1 outcome=transient_rejected classification=transient irreversible_reached=1
- irreversible reached: `YES`
- current state: target/job/message = `eligible/queued/queued`
- why not untouched: `attempts=1`, existing `mail_send_attempt`, and an irreversible gate is recorded; therefore it is not strictly untouched.
- safe for Mail.ru first-send: `NO`
### #32 - `info@mflame.ru`
- target: `33`; job: `54`; message: `62`
- attempt history: id=35 attempt=1 outcome=transient_rejected classification=transient irreversible_reached=1
- irreversible reached: `YES`
- current state: target/job/message = `eligible/queued/queued`
- why not untouched: `attempts=1`, existing `mail_send_attempt`, and an irreversible gate is recorded; therefore it is not strictly untouched.
- safe for Mail.ru first-send: `NO`

## Account and incoming state
- account `1`: provider=`yandex`, email=`edwatik@yandex.ru`, status=`connected`
- real connected Mail.ru account: `NONE`
- mail_account_profiles rows: `0`
- Yandex incoming: configured/available in existing account path; Mail.ru incoming: not run because no connected Mail.ru account
- outgoing during this reconciliation: `OFF`; SMTP DATA calls: `0`

## Safety
- SQLite integrity_check: `ok`
- duplicate jobs/messages created by this run: `NO`
- live campaign/message/job state writes: `NO`
- live account/credential writes: `NO`
- active/stale reservations: checked separately before any live run; no live run was started

## Gate
- `MAIL.RU ACCOUNT REQUIRED`: no owner-scoped connected Mail.ru account with `auth_mode=app_password` exists.
- `TEST_RECIPIENT REQUIRED`: no explicitly owner-designated test recipient was provided in the task.
- Therefore connection test, IMAP sync, self-test, supplier #1, and controlled +5 were not started.
