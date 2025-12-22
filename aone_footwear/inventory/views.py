# inventory/views.py
from django.contrib import messages
from .models import PurchaseBill
import csv
import io
import json
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db import transaction
from django.db.models import F, Subquery, OuterRef, DecimalField, Value, ExpressionWrapper, Sum
from django.db.models import Q
from django.db.models.functions import Coalesce
from django.http import FileResponse, Http404
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseRedirect
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from reportlab.lib.pagesizes import A4

from reportlab.pdfgen import canvas

from .forms import LoginForm, PurchaseBillForm, BrandForm, CategoryForm, SectionForm, SizeForm
from .forms import SupplierForm, SalesBillForm
from .models import (Brand, Category, Section, Size, PurchaseItem, Supplier)


def is_admin(user):
    return user.is_authenticated and user.groups.filter(name="ADMIN").exists()

def is_staff_user(user):
    return user.is_authenticated and user.groups.filter(name="STAFF").exists()


# Ensure WEASYPRINT_AVAILABLE is always defined to avoid unresolved reference warnings.
WEASYPRINT_AVAILABLE = False
try:
    # Importing WeasyPrint may raise ImportError or other exceptions if dependencies are missing.
    from weasyprint import HTML  # type: ignore

    WEASYPRINT_AVAILABLE = True
except Exception:
    WEASYPRINT_AVAILABLE = False

from .models import Product, SalesBill, SalesItem, Stock, Customer


# Helper to convert floats/strings to Decimal with 2 dp
def to_decimal(value):
    try:
        # Accept strings, floats or Decimals
        return Decimal(str(value)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    except Exception:
        return Decimal('0.00')


@login_required
def invoice_print(request, pk):
    """
    Invoice print/view endpoint.
    - If ?download=1 present, server generates a PDF (WeasyPrint) and returns it as attachment.
    - Else it renders the invoice_print.html template (same as current).
    """
    sale = get_object_or_404(SalesBill.objects.select_related('customer').prefetch_related('items__product'), pk=pk)

    # If download requested, generate PDF server-side
    if request.GET.get('download') in ['1', 'true', 'yes']:
        if not WEASYPRINT_AVAILABLE:
            return HttpResponse("Server-side PDF generation is not available. Install WeasyPrint.", status=500)

        # Render template to HTML string
        html_string = render_to_string('inventory/invoice_print.html', {'sale': sale})
        # Use absolute base URL so resources (images/css) can be loaded by WeasyPrint
        base_url = request.build_absolute_uri('/')

        # Generate PDF bytes
        pdf_file = HTML(string=html_string, base_url=base_url).write_pdf()

        # Respond with attachment
        filename = f"invoice-{sale.bill_number or sale.pk}.pdf"
        response = HttpResponse(pdf_file, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response


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
@user_passes_test(lambda u: u.is_superuser)
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
@user_passes_test(lambda u: u.is_superuser)
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
                (float(i.get("price") or 0) * int(i.get("qty") or 0)) * float(i.get("gst_percent") or 0) / 100) for i in
                            items])

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
                                                             defaults={"mrp": item["mrp"],
                                                                       "gst_percent": item.get("gst_percent", 0)})

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
                                        billing_price=billing_price, discount_percent=disc_percent,
                                        discount_amount=disc_amount, gst_percent=gst_percent, gst_amount=gst_amount,
                                        line_total=line_total, msp=msp, )

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



@login_required
def post_login_redirect(request):
    if is_staff_user(request.user):
        return redirect("billing")
    return redirect("sales_dashboard")


# ---------- Billing / POS ----------

@login_required
@user_passes_test(lambda u: is_admin(u) or is_staff_user(u))
@transaction.atomic
def billing_view(request):
    """
    GET: Render billing page.
    POST: Validate items (read-only), then write SalesBill, SalesItems and update Stock within the same transaction.
    Uses decorator @transaction.atomic so the entire view is transactional.
    Validation failures return JSON (or render) before any writes occur.
    """
    # --- GET: render billing page ---
    if request.method == 'GET':
        brands = Brand.objects.all().order_by('name')
        bill_form = SalesBillForm()
        data = {'stock_qty': 0}
        return render(request, 'inventory/billing.html', {
            'brands': brands,
            'bill_form': bill_form,
            'data': data
        })

    # --- Only POST beyond this point ---
    if request.method != 'POST':
        return HttpResponseBadRequest("Unsupported HTTP method.")

    # Parse items_json
    items_json = request.POST.get('items_json') or request.POST.get('items') or None
    if not items_json:
        return JsonResponse({'success': False, 'error': 'No items supplied.'}, status=400)

    try:
        items = json.loads(items_json)
    except Exception:
        return JsonResponse({'success': False, 'error': 'Invalid items_json.'}, status=400)

    if not isinstance(items, list) or len(items) == 0:
        return JsonResponse({'success': False, 'error': 'At least one item required.'}, status=400)

    # Optionally resolve/create customer (lightweight)
    customer = None
    customer_name = request.POST.get('customer_name') or request.POST.get('customer')
    customer_mobile = request.POST.get('customer_mobile')
    if customer_name:
        try:
            if customer_mobile:
                customer = Customer.objects.filter(name=customer_name, phone=customer_mobile).first()
            if not customer:
                # create a minimal customer record if not found
                customer = Customer.objects.create(name=customer_name, phone=customer_mobile or '')
        except Exception:
            customer = None

    payment_mode = request.POST.get('payment_type') or request.POST.get('payment_mode') or 'CASH'

    # --- PRE-VALIDATION (reads only) ---
    validated_items = []
    for idx, it in enumerate(items):
        try:
            product_id = int(it.get('product_id') or it.get('product') or it.get('id'))
            qty = int(it.get('qty', 0))
            price_unit = to_decimal(it.get('price', 0))
            gst_percent_input = it.get('gst_percent') if it.get('gst_percent') is not None else it.get('gst')
        except Exception:
            return JsonResponse({'success': False, 'error': f'Invalid data for item #{idx+1}.'}, status=400)

        if qty <= 0:
            return JsonResponse({'success': False, 'error': f'Quantity must be positive for item #{idx+1}.'}, status=400)

        # Fetch product (read-only)
        try:
            product = Product.objects.select_related('stock').get(pk=product_id)
        except Product.DoesNotExist:
            return JsonResponse({'success': False, 'error': f'Product id {product_id} not found (item #{idx+1}).'}, status=400)

        # Use DB MRP to validate discount limits
        mrp_db = to_decimal(product.mrp)
        gst_percent = to_decimal(gst_percent_input if gst_percent_input is not None else product.gst_percent)

        # Pre-check stock availability (best effort)
        try:
            stock = product.stock
            if stock.quantity < qty:
                return JsonResponse({'success': False, 'error': f'Not enough stock for product {product}. Available {stock.quantity}.'}, status=400)
        except Stock.DoesNotExist:
            return JsonResponse({'success': False, 'error': f'No stock record for product {product}.'}, status=400)

        # Validate manual discount: (mrp - price_unit) <= 15% MRP
        discount_per_unit = (mrp_db - price_unit)
        max_allowed = (mrp_db * Decimal('0.15')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        if discount_per_unit > max_allowed:
            return JsonResponse({'success': False,
                                 'error': f'Manual discount on product {product} exceeds 15% of MRP (max ₹{max_allowed}).'}, status=400)

        validated_items.append({
            'product': product,
            'qty': qty,
            'mrp': mrp_db,
            'price_unit': price_unit,
            'gst_percent': gst_percent
        })

    # --- ALL VALIDATED: perform writes (still inside @transaction.atomic) ---
    bill_number = timezone.now().strftime('B%Y%m%d%H%M%S')
    try:
        # Create sales bill
        sales_bill = SalesBill.objects.create(
            bill_number=bill_number,
            bill_date=timezone.now(),
            customer=customer,
            payment_mode=payment_mode,
            total_qty=0,
            total_amount=Decimal('0.00'),
            total_discount=Decimal('0.00'),
            total_gst=Decimal('0.00'),
            cgst=Decimal('0.00'),
            sgst=Decimal('0.00'),
            created_by=request.user,
        )

        total_qty = 0
        total_amount = Decimal('0.00')
        total_gst = Decimal('0.00')
        total_discount = Decimal('0.00')

        # For each validated item, lock its stock row and update
        for item in validated_items:
            product = item['product']
            qty = item['qty']
            mrp = item['mrp']
            price_unit = item['price_unit']
            gst_percent = item['gst_percent']

            # Lock stock row and re-check availability
            stock = Stock.objects.select_for_update().get(product=product)
            if stock.quantity < qty:
                # Raising an exception will rollback the atomic transaction
                raise ValueError(f'Not enough stock for product {product}. Available {stock.quantity}.')

            discount_per_unit = (mrp - price_unit)
            line_discount_amount = (discount_per_unit * qty).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

            line_gst_amount = (price_unit * qty * gst_percent / Decimal('100.00')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            line_total = (price_unit * qty + line_gst_amount).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

            SalesItem.objects.create(
                sales_bill=sales_bill,
                product=product,
                quantity=qty,
                mrp=mrp,
                selling_price=price_unit,
                discount_percent=((discount_per_unit / mrp) * Decimal('100.00')).quantize(Decimal('0.01')) if mrp > 0 else Decimal('0.00'),
                discount_amount=line_discount_amount,
                gst_percent=gst_percent,
                gst_amount=line_gst_amount,
                line_total=line_total,
            )

            # Decrement stock and save
            stock.quantity -= qty
            stock.save()

            total_qty += qty
            total_amount += line_total
            total_gst += line_gst_amount
            total_discount += line_discount_amount

        # Finalize totals and save the sales bill
        sales_bill.total_qty = total_qty
        sales_bill.total_amount = total_amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        sales_bill.total_gst = total_gst.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        sales_bill.total_discount = total_discount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        sales_bill.cgst = (sales_bill.total_gst / Decimal('2.00')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        sales_bill.sgst = (sales_bill.total_gst / Decimal('2.00')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        sales_bill.save()

    except ValueError as ve:
        # A validation or stock re-check failed; rollback happens automatically because we're inside atomic()
        return JsonResponse({'success': False, 'error': str(ve)}, status=400)
    except Exception:
        # Unexpected failure: rollback automatically
        return JsonResponse({'success': False, 'error': 'Server error while creating bill.'}, status=500)

    # Build invoice URL and respond (AJAX vs normal)
    invoice_url = reverse('invoice-pdf', args=[sales_bill.pk])
    invoice_url_with_download = invoice_url
    is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.META.get('HTTP_ACCEPT') == 'application/json'
    if is_ajax:
        return JsonResponse({'success': True, 'invoice_url': invoice_url_with_download})
    else:
        return HttpResponseRedirect(invoice_url_with_download)


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
    bill = get_object_or_404(SalesBill, id=bill_id)
    items = SalesItem.objects.filter(sales_bill=bill)

    buffer = io.BytesIO()
    pagesize = A4
    page_width, page_height = A4

    pdf = canvas.Canvas(buffer, pagesize=pagesize)

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
    pdf.drawString(30, y, f"Invoice No: {bill.bill_number}")
    y -= 12
    pdf.drawString(30, y, f"Date: {bill.bill_date.strftime('%d-%m-%Y %H:%M')}")
    y -= 20

    pdf.line(20, y, page_width - 20, y)
    y -= 10

    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(25, y, "Item")
    pdf.drawString(page_width - 160, y, "Qty")
    pdf.drawString(page_width - 120, y, "Rate")
    pdf.drawString(page_width - 70, y, "Amount")
    y -= 12

    pdf.line(20, y, page_width - 20, y)
    y -= 10

    pdf.setFont("Helvetica", 9)

    total_amount = 0
    tax_total = 0

    for item in items:
        name = f"{item.product.brand.name} {item.product.section.name} {item.product.size.value}"
        line_total = float(item.quantity) * float(item.selling_price)
        total_amount += line_total

        gst_rate = float(item.gst_percent or 0)
        gst_amount = (line_total * gst_rate) / 100
        tax_total += gst_amount

        pdf.drawString(25, y, name[:25])
        pdf.drawString(page_width - 160, y, str(item.quantity))
        pdf.drawString(page_width - 120, y, f"{item.selling_price:.2f}")
        pdf.drawString(page_width - 70, y, f"{line_total:.2f}")
        y -= 12

        if y < 50:
            pdf.showPage()
            y = page_height - 40
            pdf.setFont("Helvetica", 9)

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

    pdf.showPage()
    pdf.save()

    buffer.seek(0)
    return FileResponse(buffer, as_attachment=True, filename=f"Invoice_{bill.bill_number}.pdf")



# ---------- Stock Ledger ----------

@login_required
@user_passes_test(lambda u: u.is_superuser)
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
@user_passes_test(lambda u: u.is_superuser)
def master_brand_add(request):
    if request.method == "POST":
        name = request.POST.get("name", "").strip()

        if Brand.objects.filter(name__iexact=name).exists():
            messages.warning(request, f"Brand '{name}' already exists!")
        else:
            Brand.objects.create(name=name)
            messages.success(request, f"Brand '{name}' added successfully!")

    return redirect("master_dashboard")


@login_required
@user_passes_test(lambda u: u.is_superuser)
@login_required
@user_passes_test(lambda u: u.is_superuser)
def master_category_add(request):
    if request.method == "POST":
        brand_id = request.POST.get("brand")
        name = request.POST.get("name", "").strip()

        if Category.objects.filter(
            brand_id=brand_id,
            name__iexact=name
        ).exists():
            messages.warning(request, f"Category '{name}' already exists!")
        else:
            Category.objects.create(
                brand_id=brand_id,
                name=name
            )
            messages.success(request, f"Category '{name}' added successfully!")

    return redirect("master_dashboard")



@login_required
@user_passes_test(lambda u: u.is_superuser)
def master_section_add(request):
    if request.method == "POST":
        category_id = request.POST.get("category")
        name = request.POST.get("name", "").strip()

        if Section.objects.filter(
            category_id=category_id,
            name__iexact=name
        ).exists():
            messages.warning(request, f"Section '{name}' already exists!")
        else:
            Section.objects.create(
                category_id=category_id,
                name=name
            )
            messages.success(request, f"Section '{name}' added successfully!")

    return redirect("master_dashboard")



@login_required
@user_passes_test(lambda u: u.is_superuser)
def master_size_add(request):
    if request.method == "POST":
        section_id = request.POST.get("section")
        sizes = request.POST.getlist("sizes")

        section = Section.objects.get(id=section_id)

        added = []
        skipped = []

        for size_val in sizes:
            obj, created = Size.objects.get_or_create(
                section=section,
                value=size_val
            )
            if created:
                added.append(size_val)
            else:
                skipped.append(size_val)

        if added:
            messages.success(request, f"Sizes added: {', '.join(added)}")

        if skipped:
            messages.warning(request, f"Sizes already exist: {', '.join(skipped)}")

    return redirect("master_dashboard")



@login_required
@user_passes_test(lambda u: u.is_superuser)
def master_dashboard(request):
    return render(request, "inventory/master/dashboard.html", {"brands": Brand.objects.all(), })


@login_required
@user_passes_test(lambda u: u.is_superuser)
def master_size_add(request):
    if request.method == "POST":
        section = Section.objects.get(id=request.POST.get("section"))

        selected_sizes = request.POST.getlist("sizes")  # list: ["6","7","10","Free"]

        for size_val in selected_sizes:
            Size.objects.get_or_create(section=section, value=size_val)

        messages.success(request, "Sizes saved successfully!")
        return redirect("master_dashboard")

    return redirect("master_dashboard")


@login_required
@user_passes_test(lambda u: u.is_superuser)
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
    bills_qs = SalesBill.objects.filter(bill_date__date__gte=start_date, bill_date__date__lte=end_date)

    # --- KPIs ---

    # Today's sales (all bills for today)
    todays_bills = SalesBill.objects.filter(bill_date__date=today)
    today_sales = todays_bills.aggregate(total=Sum("total_amount"))["total"] or 0

    # Last 7 days sales (rolling)
    seven_days_ago = today - timedelta(days=6)
    last_7_qs = SalesBill.objects.filter(bill_date__date__gte=seven_days_ago, bill_date__date__lte=today)
    last_7_sales = last_7_qs.aggregate(total=Sum("total_amount"))["total"] or 0

    # Total sales (filtered range)
    total_sales = bills_qs.aggregate(total=Sum("total_amount"))["total"] or 0

    # Total qty sold (filtered range — from items)
    items_qs = SalesItem.objects.filter(sales_bill__bill_date__date__gte=start_date,
        sales_bill__bill_date__date__lte=end_date, )
    total_qty = items_qs.aggregate(total=Sum("quantity"))["total"] or 0

    # --- Payment mode summary (filtered) ---
    payments_raw = bills_qs.values("payment_mode").annotate(amount=Sum("total_amount"))

    payments = []
    for p in payments_raw:
        payments.append({"mode": p["payment_mode"], "amount": float(p["amount"] or 0), })

    # --- Best selling article (by qty, filtered range) ---
    best_selling = None
    if items_qs.exists():
        top_item = (items_qs.values("product").annotate(qty_sum=Sum("quantity"), amount_sum=Sum("line_total")).order_by(
            "-qty_sum").first())
        if top_item:
            product = Product.objects.select_related("brand", "category", "section", "size").get(id=top_item["product"])
            best_selling = {
                "name": f"{product.brand.name} / {product.category.name} / {product.section.name} / {product.size.value}",
                "qty": int(top_item["qty_sum"] or 0), "amount": float(top_item["amount_sum"] or 0), }

    # --- Table data (Sales items with bill info) ---
    table_qs = (
        SalesItem.objects.select_related("sales_bill", "product__brand", "product__category", "product__section",
            "product__size", ).filter(sales_bill__bill_date__date__gte=start_date,
            sales_bill__bill_date__date__lte=end_date, ).order_by("-sales_bill__bill_date", "-id"))

    if search:
        table_qs = table_qs.filter(
            Q(sales_bill__bill_number__icontains=search) | Q(product__brand__name__icontains=search) | Q(
                product__category__name__icontains=search) | Q(product__section__name__icontains=search) | Q(
                product__size__value__icontains=search))

    total_rows = table_qs.count()
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size

    rows = []
    for item in table_qs[start_idx:end_idx]:
        bill = item.sales_bill
        product = item.product
        line_amount = float(item.line_total or (item.quantity * item.selling_price))

        rows.append({"bill_no": bill.bill_number, "date": bill.bill_date.strftime("%d-%m-%Y"),
            "article": product.article_no or f"{product.brand.name}/{product.section.name}/{product.size.value}",
            "category": product.category.name, "size": product.size.value, "qty": item.quantity, "amount": line_amount,
            "payment": bill.get_payment_mode_display(), })

    total_pages = (total_rows + page_size - 1) // page_size if page_size else 1

    data = {"kpis": {"today_sales": float(today_sales), "last_7_sales": float(last_7_sales),
        "total_sales": float(total_sales), "total_qty": int(total_qty or 0), }, "payments": payments,
        "best_selling": best_selling,
        "table": {"rows": rows, "page": page, "page_size": page_size, "total_rows": total_rows,
            "total_pages": total_pages, },
        "meta": {"start_date": start_date.strftime("%d-%m-%Y"), "end_date": end_date.strftime("%d-%m-%Y"), }}

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
        SalesItem.objects
        .select_related(
            "sales_bill",
            "product__brand",
            "product__category",
            "product__section",
            "product__size"
        )
        .filter(
            sales_bill__bill_date__date__gte=start_date,
            sales_bill__bill_date__date__lte=end_date,
        )
        .order_by("-sales_bill__bill_date", "-id")
    )

    if search:
        qs = qs.filter(
            Q(sales_bill__bill_number__icontains=search) |
            Q(product__brand__name__icontains=search) |
            Q(product__category__name__icontains=search) |
            Q(product__section__name__icontains=search) |
            Q(product__size__value__icontains=search)
        )

    # CSV response
    response = HttpResponse(content_type="text/csv")
    filename = f"sales_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.csv"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'

    writer = csv.writer(response)

    # ===========================
    #   UPDATED COLUMN HEADERS
    # ===========================
    writer.writerow([
        "Date",
        "Bill No",
        "Article",
        "Category",
        "Size",
        "Qty",
        "MRP",
        "Discount",
        "Total GST",
        "Total",
        "Payment Mode",
        "Customer Mobile Number"
    ])
    for item in qs:
        bill = item.sales_bill
        product = item.product

        line_amount = float(item.line_total or (item.quantity * item.selling_price))
        discount = float(item.discount_amount or 0)

        # Compute total GST
        total_gst = float(item.gst_amount)

        writer.writerow([
            bill.bill_date.strftime("%d-%m-%Y"),
            bill.bill_number,
            product.article_no or f"{product.brand.name}/{product.section.name}/{product.size.value}",
            product.category.name,
            product.size.value,
            item.quantity,
            f"{item.mrp:.2f}",
            f"{discount:.2f}",
            f"{total_gst:.2f}",      # NEW COLUMN
            f"{line_amount:.2f}",
            bill.payment_mode,
            bill.customer.phone if bill.customer else ""
        ])

    return response



def landing_view(request):
    return render(request, "inventory/landing.html")


def privacy_view(request):
    return render(request, "inventory/privacy.html")


def terms_view(request):
    return render(request, "inventory/terms.html")

@login_required()
def contact_view(request):
    return render(request, "inventory/contact_us.html")


@login_required
def check_purchase_bill(request):
    supplier_id = request.GET.get("supplier_id")
    bill_number = request.GET.get("bill_number", "").strip()

    if not supplier_id or not bill_number:
        return JsonResponse({"exists": False})

    exists = PurchaseBill.objects.filter(
        supplier_id=supplier_id,
        bill_number__iexact=bill_number
    ).exists()

    return JsonResponse({"exists": exists})

@login_required
@user_passes_test(lambda u: u.is_superuser)
def party_wise_purchase_view(request):
    suppliers = Supplier.objects.all().order_by("name")

    supplier_id = request.GET.get("supplier")
    start_date = request.GET.get("start_date")
    end_date = request.GET.get("end_date")

    items = PurchaseItem.objects.select_related(
        "purchase",
        "product__brand",
        "product__category",
        "product__section",
        "product__size",
        "purchase__supplier"
    )

    if supplier_id:
        items = items.filter(purchase__supplier_id=supplier_id)

    if start_date:
        items = items.filter(purchase__bill_date__date__gte=start_date)

    if end_date:
        items = items.filter(purchase__bill_date__date__lte=end_date)

    items = items.order_by("-purchase__bill_date")

    context = {
        "suppliers": suppliers,
        "items": items,
        "selected_supplier": supplier_id,
        "start_date": start_date,
        "end_date": end_date,
    }

    return render(
        request,
        "inventory/reports/party_wise_purchase.html",
        context
    )
