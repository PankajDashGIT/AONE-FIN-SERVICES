 
from django.urls import path
from . import views

urlpatterns = [
    path('', views.sales_dashboard_view, name='sales_dashboard'),  # HOME = Dashboard
    path('billing/', views.billing_view, name='billing'),
    path('purchase/', views.purchase_view, name='purchase'),
    path('ledger/', views.ledger_view, name='ledger'),
    path('invoice/<int:bill_id>/', views.generate_invoice_pdf, name='invoice'),

    # AJAX
    path("supplier/add/", views.supplier_add, name="supplier_add"),
    path('api/categories/', views.api_categories, name='api_categories'),
    path('api/sections/', views.api_sections, name='api_sections'),
    path('api/sizes/', views.api_sizes, name='api_sizes'),
    path('api/product-info/', views.api_product_info, name='api_product_info'),

    # Master pages
    path('master/brand/add/', views.master_brand_add, name="brand_add"),
    path('master/category/add/', views.master_category_add, name="category_add"),
    path('master/section/add/', views.master_section_add, name="section_add"),
    path('master/size/add/', views.master_size_add, name="size_add"),
    path("master/", views.master_dashboard, name="master_dashboard"),

    # Sales Dashboard
    path('sales/dashboard/', views.sales_dashboard_view, name='sales_dashboard'),
    path('api/sales/dashboard-data/', views.sales_dashboard_data, name='sales_dashboard_data'),
    path('sales/export/', views.export_sales_excel, name='sales_export'),
]
