from django.contrib import admin
from django.urls import path
from django.contrib.auth import views as auth_views
from .views import *

# adjust app name if different

urlpatterns = [

    # ------------------------------------------------
    # PUBLIC LANDING PAGE (with login modal)
    # ------------------------------------------------
    path("", landing_view, name="landing"),

    # ------------------------------------------------
    # AUTHENTICATION
    # ------------------------------------------------
    path("login/", auth_views.LoginView.as_view(
            template_name="inventory/login.html",
            redirect_authenticated_user=True
        ),
        name="login"
    ),
    path("ledger/details/<int:stock_id>/", ledger_details),
    path("logout/", auth_views.LogoutView.as_view(next_page="login"), name="logout"),

    # ------------------------------------------------
    # MAIN BUSINESS PAGES
    # ------------------------------------------------
    path("sales/dashboard/", sales_dashboard_view, name="sales_dashboard"),
    path("billing/", billing_view, name="billing"),
    path("purchase/", purchase_view, name="purchase"),
    path("ledger/", ledger_view, name="ledger"),

    # ------------------------------------------------
    # INVOICE
    # ------------------------------------------------
    path('billing/submit/', billing_view, name='billing-submit'),
    path("invoice/<int:bill_id>/pdf/", generate_invoice_pdf, name="invoice-pdf"),

    # ------------------------------------------------
    # MASTER DATA PAGES
    # ------------------------------------------------
    path("master/", master_dashboard, name="master_dashboard"),
    path("master/brand/add/", master_brand_add, name="master_brand_add"),
    path("master/category/add/", master_category_add, name="master_category_add"),
    path("master/section/add/", master_section_add, name="master_section_add"),
    path("master/size/add/", master_size_add, name="master_size_add"),
    path("purchase/check-bill/", check_purchase_bill, name="check_purchase_bill"),
    path("purchase/party-wise/",party_wise_purchase_view,name="party_wise_purchase"),

    path("ledger/export/",export_stock_ledger_csv,name="export_stock_ledger_excel"),
    # ------------------------------------------------
    # API ENDPOINTS
    # ------------------------------------------------
    path("api/categories/", api_categories, name="api_categories"),
    path("api/sections/", api_sections, name="api_sections"),
    path("api/sizes/", api_sizes, name="api_sizes"),
    path("api/product-info/", api_product_info, name="api_product_info"),
    path('supplier/add/', supplier_add, name='supplier_add'),

    # SALES API (AJAX)
    path("api/sales/dashboard-data/", sales_dashboard_data, name="sales_dashboard_data"),

    # EXPORTS
    path("sales/export/", export_sales_excel, name="sales_export"),
    path("post-login/", post_login_redirect, name="post_login"),
    # ------------------------------------------------
    # COMPANY STATIC INFO PAGES
    # ------------------------------------------------
    path("privacy/", privacy_view, name="privacy"),
    path("terms/", terms_view, name="terms"),
    path("contact/", contact_view, name="contact"),

    # ------------------------------------------------
    # STAFF MANAGEMENT
    # ------------------------------------------------
    path("system/staff/", staff_management_view, name="staff_management"),
    path("system/staff/add/", staff_add_edit_view, name="staff_add"),
    path("system/staff/edit/<int:user_id>/", staff_add_edit_view, name="staff_edit"),
    path("system/staff/toggle/<int:user_id>/", staff_toggle_active, name="staff_toggle"),

    # ------------------------------------------------
    # EXPENSE MANAGEMENT
    # ------------------------------------------------
    path("system/expenses/", expense_management_view, name="expense_management"),
    path("api/expenses/chart/", expense_chart_data, name="expense_chart_data"),
]
