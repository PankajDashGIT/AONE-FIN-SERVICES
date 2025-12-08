from django.contrib import admin
from django.urls import path
from django.contrib.auth import views as auth_views
from inventory import views   # adjust app name if different

urlpatterns = [

    # ------------------------------------------------
    # PUBLIC LANDING PAGE (with login modal)
    # ------------------------------------------------
    path("", views.landing_view, name="landing"),

    # ------------------------------------------------
    # AUTHENTICATION
    # ------------------------------------------------
    path("login/", auth_views.LoginView.as_view(
            template_name="inventory/login.html",
            redirect_authenticated_user=True
        ),
        name="login"
    ),

    path("logout/", auth_views.LogoutView.as_view(next_page="login"), name="logout"),

    # ------------------------------------------------
    # MAIN BUSINESS PAGES
    # ------------------------------------------------
    path("sales/dashboard/", views.sales_dashboard_view, name="sales_dashboard"),
    path("billing/", views.billing_view, name="billing"),
    path("purchase/", views.purchase_view, name="purchase"),
    path("ledger/", views.ledger_view, name="ledger"),

    # ------------------------------------------------
    # INVOICE
    # ------------------------------------------------
    path("invoice/<int:bill_id>/", views.generate_invoice_pdf, name="invoice"),

    # ------------------------------------------------
    # MASTER DATA PAGES
    # ------------------------------------------------
    path("master/", views.master_dashboard, name="master_dashboard"),
    path("master/brand/add/", views.master_brand_add, name="brand_add"),
    path("master/category/add/", views.master_category_add, name="category_add"),
    path("master/section/add/", views.master_section_add, name="section_add"),
    path("master/size/add/", views.master_size_add, name="size_add"),

    # ------------------------------------------------
    # API ENDPOINTS
    # ------------------------------------------------
    path("api/categories/", views.api_categories, name="api_categories"),
    path("api/sections/", views.api_sections, name="api_sections"),
    path("api/sizes/", views.api_sizes, name="api_sizes"),
    path("api/product-info/", views.api_product_info, name="api_product_info"),
    path('supplier/add/', views.supplier_add, name='supplier_add'),

    # SALES API (AJAX)
    path("api/sales/dashboard-data/", views.sales_dashboard_data, name="sales_dashboard_data"),

    # EXPORTS
    path("sales/export/", views.export_sales_excel, name="sales_export"),

    # ------------------------------------------------
    # COMPANY STATIC INFO PAGES
    # ------------------------------------------------
    path("privacy/", views.privacy_view, name="privacy"),
    path("terms/", views.terms_view, name="terms"),
    path("contact/", views.contact_view, name="contact"),

    # ------------------------------------------------
    # ADMIN
    # ------------------------------------------------
    path("admin/", admin.site.urls),
]
