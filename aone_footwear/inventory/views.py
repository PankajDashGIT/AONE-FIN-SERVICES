# inventory/views.py
from django.http import HttpResponse
from django.utils import timezone
from datetime import datetime, timedelta, date
from django.db.models import Sum, F, Q
import csv
import json
from django.contrib import (messages)
from django.contrib.auth import login, logout
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.db import transaction
from .forms import LoginForm, PurchaseBillForm, SalesBillForm, CustomerForm, BrandForm, CategoryForm, SectionForm, SizeForm
from .models import (Brand, Category, Section, Size, Product, Stock, PurchaseItem, SalesBill, SalesItem, Supplier)
from .forms import SupplierForm
import io
from django.http import FileResponse, Http404
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from django.contrib.auth.decorators import login_required
from django.db.models import F, Subquery, OuterRef, DecimalField, Value, ExpressionWrapper, Sum
from django.db.models.functions import Coalesce


# ---------- Auth ----------

def user_login(request):
    if request.user.is_authenticated:
        return redirect('billing')

    form = LoginForm(request, data=request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.get_user()
        login(request, user)
        return redirect('sales_dashboard')
    return render(request, 'inventory/login.html', {'form': form})


def user_logout(request):
    logout(request)
    return redirect('login')


@login_required
def supplier_add(request):
    if request.method == "POST":
        form = SupplierForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Supplier added successfully!")
            return redirect('supplier_add')
    else:
        form = SupplierForm()

    return render(request, "inventory/supplier_add.html", {"form": form})


# ---------- Stock Purchase ----------
# updates only to purchase_view context to include categories/sections/sizes



# ... rest of file unchanged above purchase_view ...

# ---------- Stock Purchase ----------
@login_required
@transaction.atomic
def purchase_view(request):
    form = PurchaseBillForm(request.POST or None)

    if request.method == "POST":

        # Validate Bill Form
        if not form.is_valid():
            return JsonResponse({"error": "Invalid bill form", "details": form.errors}, status=400)

        # Items JSON
        items_json = request.POST.get("items_json")
        if not items_json:
            return JsonResponse({"error": "No items received"}, status=400)

        import json
        items = json.loads(items_json)
        if len(items) == 0:
            return JsonResponse({"error": "No items in purchase"}, status=400)

        # Save the bill
        bill = form.save(commit=False)
        bill.created_by = request.user

        # Compute totals
        total_qty = sum([int(i["qty"]) for i in items])
        total_discount = sum([float(i.get("discount_rs") or 0) for i in items])
        total_gst = sum(
            [((float(i.get("price") or 0) * int(i.get("qty") or 0)) * float(i.get("gst_percent") or 0) / 100) for i in
                items])
        total_amount = sum([(float(i.get("price") or 0) * int(i.get("qty") or 0)) + (
                    (float(i.get("price") or 0) * int(i.get("qty") or 0)) * float(i.get("gst_percent") or 0) / 100) for
            i in items])

        bill.total_qty = total_qty
        bill.total_discount = total_discount
        bill.total_gst = total_gst
        bill.total_amount = total_amount

        # Payment split
        if bill.payment_mode == "CASH":
            bill.cash_paid = total_amount
            bill.credit_amount = 0
        else:
            bill.cash_paid = 0
            bill.credit_amount = total_amount

        bill.save()

        # Save items & update stock
        for item in items:
            # Fetch or create product
            product, created = Product.objects.get_or_create(brand_id=item["brand_id"], category_id=item["category_id"],
                section_id=item["section_id"], size_id=item["size_id"],
                defaults={"mrp": item["mrp"], "gst_percent": item.get("gst_percent", 0)})

            # Always update MRP & GST
            product.mrp = item["mrp"]
            product.gst_percent = item.get("gst_percent", 0)
            product.save()

            qty = int(item["qty"])
            billing_price = float(item["price"])
            disc_percent = float(item.get("discount_percent") or 0)
            disc_amount = float(item.get("discount_rs") or 0)
            gst_percent = float(item.get("gst_percent") or 0)
            mrp = float(item.get("mrp") or 0)
            msp = float(item.get("msp") or 0)

            gst_amount = ((billing_price * qty) * gst_percent) / 100
            line_total = (billing_price * qty) + gst_amount

            PurchaseItem.objects.create(purchase=bill, product=product, quantity=qty, mrp=mrp,
                billing_price=billing_price, discount_percent=disc_percent, discount_amount=disc_amount,
                gst_percent=gst_percent, gst_amount=gst_amount, line_total=line_total, msp=msp, )

            # Stock update
            stock, _ = Stock.objects.get_or_create(product=product)
            stock.quantity += qty
            stock.save()

        messages.success(request, "Purchase saved successfully!")
        return redirect("ledger")

    # GET view
    context = {"form": form, "brands": Brand.objects.all(), "suppliers": Supplier.objects.all(),
        # Populate the independent dropdowns with all choices (no cascading)
        "categories": Category.objects.all(), "sections": Section.objects.all(), "sizes": Size.objects.all(), }
    return render(request, "inventory/purchase.html", context)


# ---------- Billing / POS ----------

@login_required
@transaction.atomic
def billing_view(request):
    bill_form = SalesBillForm(request.POST or None)
    customer_form = CustomerForm(request.POST or None, prefix='cust')

    if request.method == 'POST':

        # 1) Validate sales bill form
        if not bill_form.is_valid():
            return JsonResponse({"error": "Invalid bill form"}, status=400)

        # 2) Parse items JSON from hidden field
        items_json = request.POST.get("items_json")
        if not items_json:
            return JsonResponse({"error": "No bill items received"}, status=400)

        import json
        items = json.loads(items_json)

        if len(items) == 0:
            return JsonResponse({"error": "Bill cannot be empty"}, status=400)

        # 3) Create SalesBill
        sales_bill = bill_form.save(commit=False)
        sales_bill.created_by = request.user

        # Customer (if credit)
        if bill_form.cleaned_data['payment_mode'] == 'CREDIT':
            if customer_form.is_valid():
                customer = customer_form.save()
                sales_bill.customer = customer
            else:
                return JsonResponse({"error": "Invalid customer form"}, status=400)

        sales_bill.save()

        # 4) Process each item
        for item in items:

            product_id = item.get("product_id")
            qty = int(item.get("qty", 0))
            mrp = float(item.get("mrp", 0))
            final_price = float(item.get("final_price", 0))
            gst_percent = float(item.get("gst_percent", 0))

            # Get product
            try:
                product = Product.objects.get(id=product_id)
            except Product.DoesNotExist:
                transaction.set_rollback(True)
                return JsonResponse({"error": f"Product not found: {product_id}"}, status=400)

            # Get stock object
            try:
                stock = Stock.objects.get(product=product)
            except Stock.DoesNotExist:
                transaction.set_rollback(True)
                return JsonResponse({"error": f"No stock available for product {product}"}, status=400)

            # -----------------------------------------
            # BACKEND STOCK VALIDATION (prevents oversell)
            # -----------------------------------------
            if qty > stock.quantity:
                transaction.set_rollback(True)
                return JsonResponse({"error": f"Not enough stock for {product}. "
                                              f"Available: {stock.quantity}, Requested: {qty}"}, status=400)

            # -----------------------------------------
            # AUTO STOCK REDUCE
            # -----------------------------------------
            stock.quantity -= qty
            stock.save()

            # Create SalesItem
            SalesItem.objects.create(sales_bill=sales_bill, product=product, quantity=qty, mrp=mrp,
                selling_price=final_price, gst_percent=gst_percent, )

        # After all items processed, return invoice PDF
        return generate_invoice_pdf(request, sales_bill.id)

    # GET request → display billing page
    context = {'bill_form': bill_form, 'customer_form': customer_form, 'brands': Brand.objects.all(), }
    return render(request, 'inventory/billing.html', context)


def api_product_info(request):
    size_id = request.GET.get('size_id')

    try:
        product = Product.objects.get(size_id=size_id)
        stock = Stock.objects.get(product=product)
    except Product.DoesNotExist:
        return JsonResponse({'error': 'Product not found'}, status=404)
    except Stock.DoesNotExist:
        return JsonResponse({'error': 'Stock not found'}, status=404)

    data = {'mrp': product.mrp, 'stock_qty': stock.quantity, }
    return JsonResponse(data)


# ---------- Invoice PDF ----------

@login_required
def generate_invoice_pdf(request, bill_id):
    """
    Generate a PDF invoice for the given bill_id.
    Works for both internal calls and direct URL access.
    """

    try:
        bill = SalesBill.objects.get(id=bill_id)
    except SalesBill.DoesNotExist:
        raise Http404("Invoice not found")

    items = SalesItem.objects.filter(sales_bill=bill)

    # PDF buffer
    buffer = io.BytesIO()

    # --- CHOOSE INVOICE FORMAT ---
    # Format A = A4 (default)
    # Format B = Thermal 80mm
    invoice_format = request.GET.get("format", "A").upper()

    if invoice_format == "B":
        # Thermal width = 80mm, height auto (use long height)
        page_width = 80 * mm
        page_height = 500 * mm  # long height scroll
        pagesize = (page_width, page_height)
    else:
        # A4 Portrait default
        pagesize = A4
        page_width, page_height = A4

    pdf = canvas.Canvas(buffer, pagesize=pagesize)

    # ------------ HEADER --------------
    y = page_height - 30

    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(30, y, "AONE FOOTWEAR")
    y -= 15

    pdf.setFont("Helvetica", 10)
    pdf.drawString(30, y, "Main Market, Bhubaneswar, Odisha")
    y -= 12
    pdf.drawString(30, y, "Phone: +91-9876543210")
    y -= 20

    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(30, y, f"Invoice No: {bill.id}")
    y -= 12
    pdf.drawString(30, y, f"Date: {bill.created_at.strftime('%d-%m-%Y %H:%M')}")
    y -= 20

    pdf.line(20, y, page_width - 20, y)
    y -= 10

    # -------- TABLE HEADER ------------
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(25, y, "Item")
    pdf.drawString(page_width - 160, y, "Qty")
    pdf.drawString(page_width - 120, y, "Rate")
    pdf.drawString(page_width - 70, y, "Amount")
    y -= 12

    pdf.line(20, y, page_width - 20, y)
    y -= 10

    # -------- TABLE ROWS ------------
    pdf.setFont("Helvetica", 9)

    total_amount = 0
    tax_total = 0

    for item in items:
        product_name = f"{item.product.brand.name} {item.product.section.name} {item.product.size.value}"
        line_total = float(item.quantity) * float(item.selling_price)
        total_amount += line_total

        # GST calculation
        gst_rate = float(item.gst_percent or 0)
        gst_amount = (line_total * gst_rate) / 100
        tax_total += gst_amount

        # Print row
        pdf.drawString(25, y, product_name[:25])
        pdf.drawString(page_width - 160, y, str(item.quantity))
        pdf.drawString(page_width - 120, y, f"{item.selling_price:.2f}")
        pdf.drawString(page_width - 70, y, f"{line_total:.2f}")
        y -= 12

        if y < 50:
            pdf.showPage()
            y = page_height - 40
            pdf.setFont("Helvetica", 9)

    # -------- TOTALS ------------
    y -= 15
    pdf.line(20, y, page_width - 20, y)
    y -= 12

    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(page_width - 150, y, "Sub Total:")
    pdf.drawString(page_width - 70, y, f"{total_amount:.2f}")
    y -= 12

    pdf.drawString(page_width - 150, y, "GST:")
    pdf.drawString(page_width - 70, y, f"{tax_total:.2f}")
    y -= 12

    grand_total = total_amount + tax_total
    pdf.drawString(page_width - 150, y, "Grand Total:")
    pdf.drawString(page_width - 70, y, f"{grand_total:.2f}")
    y -= 25

    pdf.setFont("Helvetica", 9)
    pdf.drawString(30, y, "Thank you for shopping with AONE FOOTWEAR!")
    y -= 12
    pdf.drawString(30, y, "GST Inclusive Wherever Applicable")

    pdf.showPage()
    pdf.save()

    buffer.seek(0)

    filename = f"Invoice_{bill.id}.pdf"
    return FileResponse(buffer, as_attachment=True, filename=filename)


# ---------- Stock Ledger ----------

@login_required
def ledger_view(request):
    qs = Stock.objects.select_related('product', 'product__brand', 'product__category', 'product__section',
        'product__size').all()

    # Filters from GET
    brand_id = request.GET.get('brand')
    category_id = request.GET.get('category')
    section_id = request.GET.get('section')
    size_id = request.GET.get('size')
    supplier_id = request.GET.get('supplier')

    if brand_id:
        qs = qs.filter(product__brand_id=brand_id)
    if category_id:
        qs = qs.filter(product__category_id=category_id)
    if section_id:
        qs = qs.filter(product__section_id=section_id)
    if size_id:
        qs = qs.filter(product__size_id=size_id)

    # If supplier filter provided, keep stocks for products that have purchases from that supplier
    if supplier_id:
        qs = qs.filter(product__purchaseitem__purchase__supplier_id=supplier_id).distinct()

    # Create an expression for valuation = quantity * product.mrp with explicit output_field
    valuation_expr = ExpressionWrapper(F('quantity') * F('product__mrp'),
        output_field=DecimalField(max_digits=14, decimal_places=2))

    # Annotate per-row valuation (uses Decimal output_field to avoid mixed types)
    qs = qs.annotate(
        valuation=Coalesce(valuation_expr, Value(0), output_field=DecimalField(max_digits=14, decimal_places=2)))

    # Subquery: get the latest PurchaseItem for this product and fetch purchase.supplier.name and purchase.bill_number
    latest_pi = PurchaseItem.objects.filter(product=OuterRef('product')).order_by('-purchase__bill_date',
                                                                                  '-purchase__id')

    qs = qs.annotate(supplier_name=Subquery(latest_pi.values('purchase__supplier__name')[:1]),
        bill_number=Subquery(latest_pi.values('purchase__bill_number')[:1]))

    # Compute totals from the filtered queryset using the same valuation expression
    totals = qs.aggregate(total_qty=Coalesce(Sum('quantity'), Value(0)),
        total_valuation=Coalesce(Sum(valuation_expr), Value(0),
                                 output_field=DecimalField(max_digits=18, decimal_places=2)))

    # Pass dropdown lists if you want server-side filled dependent selects
    brands = Brand.objects.all()
    suppliers = Supplier.objects.all()  # party/supplier list for filter
    categories = Category.objects.filter(brand_id=brand_id) if brand_id else Category.objects.none()
    sections = Section.objects.filter(category_id=category_id) if category_id else Section.objects.none()
    sizes = Size.objects.filter(section_id=section_id) if section_id else Size.objects.none()

    context = {'stocks': qs, 'brands': brands, 'suppliers': suppliers, 'categories': categories, 'sections': sections,
        'sizes': sizes, 'totals': totals, }
    return render(request, 'inventory/ledger.html', context)


# ---------- AJAX APIs ----------

@login_required
def api_categories(request):
    brand_id = request.GET.get('brand_id')
    categories = Category.objects.filter(brand_id=brand_id).values('id', 'name')
    return JsonResponse(list(categories), safe=False)


@login_required
def api_sections(request):
    category_id = request.GET.get('category_id')
    sections = Section.objects.filter(category_id=category_id).values('id', 'name')
    return JsonResponse(list(sections), safe=False)


@login_required
def api_sizes(request):
    section_id = request.GET.get('section_id')
    sizes = Size.objects.filter(section_id=section_id).values('id', 'value')
    return JsonResponse(list(sizes), safe=False)


@login_required
def api_product_info(request):
    brand_id = request.GET.get('brand_id')
    category_id = request.GET.get('category_id')
    section_id = request.GET.get('section_id')
    size_id = request.GET.get('size_id')

    products = Product.objects.filter(brand_id=brand_id, category_id=category_id, section_id=section_id,
        size_id=size_id)

    # multi-MRP list + stock
    data = []
    for p in products:
        qty = getattr(p.stock, 'quantity', 0)
        data.append({'product_id': p.id, 'mrp': float(p.mrp), 'default_discount': float(p.default_discount_percent),
            'gst_percent': float(p.gst_percent), 'stock_qty': qty, })

    return JsonResponse(data, safe=False)


@login_required
def master_brand_add(request):
    form = BrandForm(request.POST or None)
    if request.method == "POST":
        if form.is_valid():
            form.save()
            messages.success(request, "Brand added successfully!")
            return redirect("brand_add")
    return render(request, "inventory/master/brand_add.html", {"form": form})


@login_required
def master_category_add(request):
    form = CategoryForm(request.POST or None)
    if request.method == "POST":
        if form.is_valid():
            form.save()
            messages.success(request, "Category added successfully!")
            return redirect("category_add")
    return render(request, "inventory/master/category_add.html", {"form": form})


@login_required
def master_section_add(request):
    form = SectionForm(request.POST or None)
    if request.method == "POST":
        if form.is_valid():
            form.save()
            messages.success(request, "Section added successfully!")
            return redirect("section_add")
    return render(request, "inventory/master/section_add.html", {"form": form})


@login_required
def master_size_add(request):
    form = SizeForm(request.POST or None)
    if request.method == "POST":
        if form.is_valid():
            form.save()
            messages.success(request, "Size added successfully!")
            return redirect("size_add")
    return render(request, "inventory/master/size_add.html", {"form": form})

@login_required
def master_dashboard(request):
    return render(request, "inventory/master/dashboard.html", {
        "brands": Brand.objects.all(),
    })

@login_required
def master_size_add(request):
    if request.method == "POST":
        section = Section.objects.get(id=request.POST.get("section"))

        selected_sizes = request.POST.getlist("sizes")  # list: ["6","7","10","Free"]

        for size_val in selected_sizes:
            Size.objects.get_or_create(
                section=section,
                value=size_val
            )

        messages.success(request, "Sizes saved successfully!")
        return redirect("master_dashboard")

    return redirect("master_dashboard")


@login_required
def sales_dashboard_view(request):
    """Render the Sales Dashboard shell — data loaded via AJAX."""
    return render(request, "inventory/sales_dashboard.html", {})


@login_required
def sales_dashboard_data(request):
    """
    AJAX endpoint that returns JSON for:
    - KPIs
    - payment summary
    - best selling article
    - sales table (paginated)
    """
    # --- Parse filters ---
    start_str = request.GET.get("start_date")
    end_str = request.GET.get("end_date")
    search = request.GET.get("search", "").strip()
    page = int(request.GET.get("page", 1))
    page_size = int(request.GET.get("page_size", 10))

    today = timezone.localdate()

    # Default range: today
    if start_str:
        start_date = datetime.strptime(start_str, "%d-%m-%Y").date()
    else:
        start_date = today

    if end_str:
        end_date = datetime.strptime(end_str, "%d-%m-%Y").date()
    else:
        end_date = today

    # Base bill queryset for filtered range
    bills_qs = SalesBill.objects.filter(
        bill_date__date__gte=start_date,
        bill_date__date__lte=end_date
    )

    # --- KPIs ---

    # Today's sales (all bills for today)
    todays_bills = SalesBill.objects.filter(bill_date__date=today)
    today_sales = todays_bills.aggregate(total=Sum("total_amount"))["total"] or 0

    # Last 7 days sales (rolling)
    seven_days_ago = today - timedelta(days=6)
    last_7_qs = SalesBill.objects.filter(
        bill_date__date__gte=seven_days_ago,
        bill_date__date__lte=today
    )
    last_7_sales = last_7_qs.aggregate(total=Sum("total_amount"))["total"] or 0

    # Total sales (filtered range)
    total_sales = bills_qs.aggregate(total=Sum("total_amount"))["total"] or 0

    # Total qty sold (filtered range — from items)
    items_qs = SalesItem.objects.filter(
        sales_bill__bill_date__date__gte=start_date,
        sales_bill__bill_date__date__lte=end_date,
    )
    total_qty = items_qs.aggregate(total=Sum("quantity"))["total"] or 0

    # --- Payment mode summary (filtered) ---
    payments_raw = bills_qs.values("payment_mode").annotate(
        amount=Sum("total_amount")
    )

    payments = []
    for p in payments_raw:
        payments.append({
            "mode": p["payment_mode"],
            "amount": float(p["amount"] or 0),
        })

    # --- Best selling article (by qty, filtered range) ---
    best_selling = None
    if items_qs.exists():
        top_item = (
            items_qs
            .values("product")
            .annotate(qty_sum=Sum("quantity"), amount_sum=Sum("line_total"))
            .order_by("-qty_sum")
            .first()
        )
        if top_item:
            product = Product.objects.select_related(
                "brand", "category", "section", "size"
            ).get(id=top_item["product"])
            best_selling = {
                "name": f"{product.brand.name} / {product.category.name} / {product.section.name} / {product.size.value}",
                "qty": int(top_item["qty_sum"] or 0),
                "amount": float(top_item["amount_sum"] or 0),
            }

    # --- Table data (Sales items with bill info) ---
    table_qs = (
        SalesItem.objects.select_related(
            "sales_bill",
            "product__brand",
            "product__category",
            "product__section",
            "product__size",
        )
        .filter(
            sales_bill__bill_date__date__gte=start_date,
            sales_bill__bill_date__date__lte=end_date,
        )
        .order_by("-sales_bill__bill_date", "-id")
    )

    if search:
        table_qs = table_qs.filter(
            Q(sales_bill__bill_number__icontains=search)
            | Q(product__brand__name__icontains=search)
            | Q(product__category__name__icontains=search)
            | Q(product__section__name__icontains=search)
            | Q(product__size__value__icontains=search)
        )

    total_rows = table_qs.count()
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size

    rows = []
    for item in table_qs[start_idx:end_idx]:
        bill = item.sales_bill
        product = item.product
        line_amount = float(item.line_total or (item.quantity * item.selling_price))

        rows.append({
            "bill_no": bill.bill_number,
            "date": bill.bill_date.strftime("%d-%m-%Y"),
            "article": product.article_no or f"{product.brand.name}/{product.section.name}/{product.size.value}",
            "category": product.category.name,
            "size": product.size.value,
            "qty": item.quantity,
            "amount": line_amount,
            "payment": bill.get_payment_mode_display(),
        })

    total_pages = (total_rows + page_size - 1) // page_size if page_size else 1

    data = {
        "kpis": {
            "today_sales": float(today_sales),
            "last_7_sales": float(last_7_sales),
            "total_sales": float(total_sales),
            "total_qty": int(total_qty or 0),
        },
        "payments": payments,
        "best_selling": best_selling,
        "table": {
            "rows": rows,
            "page": page,
            "page_size": page_size,
            "total_rows": total_rows,
            "total_pages": total_pages,
        },
        "meta": {
            "start_date": start_date.strftime("%d-%m-%Y"),
            "end_date": end_date.strftime("%d-%m-%Y"),
        }
    }

    return JsonResponse(data)


@login_required
def export_sales_excel(request):
    """
    Export filtered sales (same filters as dashboard) to CSV (Excel-friendly).
    URL: /sales/export/
    """
    start_str = request.GET.get("start_date")
    end_str = request.GET.get("end_date")
    search = request.GET.get("search", "").strip()

    today = timezone.localdate()

    if start_str:
        start_date = datetime.strptime(start_str, "%d-%m-%Y").date()
    else:
        start_date = today

    if end_str:
        end_date = datetime.strptime(end_str, "%d-%m-%Y").date()
    else:
        end_date = today

    qs = (
        SalesItem.objects.select_related(
            "sales_bill",
            "product__brand",
            "product__category",
            "product__section",
            "product__size",
        )
        .filter(
            sales_bill__bill_date__date__gte=start_date,
            sales_bill__bill_date__date__lte=end_date,
        )
        .order_by("-sales_bill__bill_date", "-id")
    )

    if search:
        qs = qs.filter(
            Q(sales_bill__bill_number__icontains=search)
            | Q(product__brand__name__icontains=search)
            | Q(product__category__name__icontains=search)
            | Q(product__section__name__icontains=search)
            | Q(product__size__value__icontains=search)
        )

    # CSV response
    response = HttpResponse(content_type="text/csv")
    filename = f"sales_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.csv"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'

    writer = csv.writer(response)
    writer.writerow(["Bill No", "Date", "Article", "Category", "Size", "Qty", "Amount", "Payment"])

    for item in qs:
        bill = item.sales_bill
        product = item.product
        line_amount = float(item.line_total or (item.quantity * item.selling_price))

        writer.writerow([
            bill.bill_number,
            bill.bill_date.strftime("%d-%m-%Y"),
            product.article_no or f"{product.brand.name}/{product.section.name}/{product.size.value}",
            product.category.name,
            product.size.value,
            item.quantity,
            f"{line_amount:.2f}",
            bill.get_payment_mode_display(),
        ])

    return response

def landing_view(request):
    return render(request, "inventory/landing.html")

def privacy_view(request):
    return render(request, "inventory/privacy.html")

def terms_view(request):
    return render(request, "inventory/terms.html")

def contact_view(request):
    return render(request, "inventory/contact.html")

