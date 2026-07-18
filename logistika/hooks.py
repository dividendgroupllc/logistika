app_name = "logistika"
app_title = "Erp for logistics "
app_publisher = "sardorbek qamchibekov "
app_description = "Erpnext for logistics"
app_email = "sardorbekqamchibekov76@gmail.com"
app_license = "mit"

# Fixtures
fixtures = [
	{
		"dt": "Custom Field",
		"filters": [["name", "in", ["Contact-telegram_chat_id", "Account-account_name_zh"]]],
	},
	{
		"dt": "Property Setter",
		"filters": [["doc_type", "=", "Account"], ["property", "=", "translated_doctype"]],
	},
]

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "logistika",
# 		"logo": "/assets/logistika/logo.png",
# 		"title": "Erp for logistics ",
# 		"route": "/logistika",
# 		"has_permission": "logistika.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
app_include_css = "/assets/logistika/css/internal_logistics.css"
# `?v=N` — bu fayl to'g'ridan-to'g'ri (esbuild bundle'siz) statik xizmat qilinadi,
# nginx uni "Cache-Control: max-age=31536000" (1 yil!) bilan yuboradi — fayl
# o'zgarganda ham brauzer/oraliq keshlar buni sezmasligi mumkin edi (aynan shu holat
# 2026-07-18'da sodir bo'ldi). Shuning uchun har safar bu faylga MUHIM o'zgarish
# kiritilganda shu raqamni oshirish kerak — URL o'zgarishi barcha keshlarni majburan
# chetlab o'tadi.
app_include_js = "/assets/logistika/js/order_chat_widget.js?v=3"

# include js, css files in header of web template
# web_include_css = "/assets/logistika/css/logistika.css"
# web_include_js = "/assets/logistika/js/logistika.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "logistika/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "logistika/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "logistika.utils.jinja_methods",
# 	"filters": "logistika.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "logistika.install.before_install"
# after_install = "logistika.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "logistika.uninstall.before_uninstall"
# after_uninstall = "logistika.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "logistika.utils.before_app_install"
# after_app_install = "logistika.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "logistika.utils.before_app_uninstall"
# after_app_uninstall = "logistika.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "logistika.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
	"Account": {
		# Yangi hisob qo'shilganda yoki nomi o'zgartirilganda, Chart of Accounts'ning
		# xitoycha tarjimasi (Kimi orqali) avtomatik yaratiladi/yangilanadi — qo'lda
		# translate_chart_of_accounts/sync_coa_translations qayta ishga tushirish shart
		# emas. Bu fon vazifasi (background job) sifatida ishlaydi, hisobni saqlashni
		# sekinlashtirmaydi.
		"after_insert": "logistika.erp_for_logistics.coa_translation.queue_translation_for_new_account",
		"on_update": "logistika.erp_for_logistics.coa_translation.queue_translation_for_renamed_account",
		# ERPNext hisob nomini o'zgartirishda odatiy save() emas, balki
		# update_account_number() (frappe.rename_doc) yo'lini ishlatadi — shu yo'l
		# on_update'ni chaqirmaydi, faqat after_rename'ni.
		"after_rename": "logistika.erp_for_logistics.coa_translation.queue_translation_after_rename",
	}
}

# Scheduled Tasks
# ---------------

scheduler_events = {
	"cron": {
		# Xitoy vaqti bilan soat 11:00 (UTC+8) = 03:00 UTC = O'zbekiston vaqti bilan 08:00
		# Internal Logistics (Xitoy furalari) uchun GPS/Traccar avtomatikasi olib
		# tashlandi — manzil endi qo'lda kiritiladi. Traccar endi faqat KZ Transit uchun.
		"0 3 * * *": [
			"logistika.erp_for_logistics.kz_gps_tracking.daily_gps_update_kz",
		],
	},
}

# Testing
# -------

# before_tests = "logistika.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "logistika.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "logistika.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["logistika.utils.before_request"]
# after_request = ["logistika.utils.after_request"]

# Job Events
# ----------
# before_job = ["logistika.utils.before_job"]
# after_job = ["logistika.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"logistika.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []

