// inventory/static/inventory/js/billing.js

let billItems = [];
let purchaseItems = [];
let data = null;

// global array that holds items already added to the bill
// billItems should be filled when you click "Add to Bill"

function updateTotals() {
    let totalQty = 0;
    let subtotal = 0;
    let totalGst = 0;

    billItems.forEach(item => {
        const qty = Number(item.qty) || 0;
        const finalPrice = Number(item.final_price || item.price) || 0;   // selling price per unit
        const gstPercent = Number(item.gst_percent) || 0;

        totalQty += qty;

        const lineAmount = qty * finalPrice;
        subtotal += lineAmount;

        const lineGst = (lineAmount * gstPercent) / 100;
        totalGst += lineGst;
    });

    const totalQtyInput = document.getElementById('totalQty');
    const subtotalInput = document.getElementById('subtotal');
    const totalGstInput = document.getElementById('totalGst');
    const cgstSplitSpan = document.getElementById('cgstSplit');
    const sgstSplitSpan = document.getElementById('sgstSplit');

    if (totalQtyInput) totalQtyInput.value = totalQty;
    if (subtotalInput) subtotalInput.value = subtotal.toFixed(2);
    if (totalGstInput) totalGstInput.value = totalGst.toFixed(2);

    const halfGst = totalGst / 2;
    if (cgstSplitSpan) cgstSplitSpan.innerText = halfGst.toFixed(2);
    if (sgstSplitSpan) sgstSplitSpan.innerText = halfGst.toFixed(2);
}


function recalcSellingPrice() {
    const mrp = parseFloat($('#bill_mrp option:selected').text()) || 0;
    const defaultDisc = parseFloat($('#bill_default_disc').val()) || 0;
    const manualChecked = $('#bill_manual_disc_check').is(':checked');
    const manualDiscRs = manualChecked ? parseFloat($('#bill_manual_disc').val()) || 0 : 0;

    // Calculate selling price:
    // First apply default percent discount, then subtract manual Rs discount (if enabled)
    const priceAfterDefault = mrp - (mrp * defaultDisc / 100);
    let price = priceAfterDefault - manualDiscRs;
    if (price < 0) price = 0;

    $('#bill_selling_price').val(price.toFixed(2));
}

function refreshBillTable() {
    const $tbody = $('#bill_items_table tbody');
    $tbody.empty();
    let totalQty = 0, subtotal = 0, totalGst = 0;

    billItems.forEach((item, idx) => {
        totalQty += item.qty;
        subtotal += item.final;
        totalGst += item.gst_amount;

        $tbody.append(`
            <tr>
                <td>${item.brand}</td>
                <td>${item.category}</td>
                <td>${item.section}</td>
                <td>${item.size}</td>
                <td>${item.qty}</td>
                <td>${item.mrp.toFixed(2)}</td>
                <td>${item.price.toFixed(2)}</td>
                <td>${item.discount.toFixed(2)}%</td>
                <td>${item.gst_percent.toFixed(2)}%</td>
                <td>${item.final.toFixed(2)}</td>
                <td><button type="button" class="btn btn-sm btn-danger" onclick="removeBillItem(${idx})">X</button></td>
            </tr>
        `);
    });

    $('#totalQty').val(totalQty);
    $('#subtotal').val(subtotal.toFixed(2));
    $('#totalGst').val(totalGst.toFixed(2));
    $('#cgstSplit').text((totalGst/2).toFixed(2));
    $('#sgstSplit').text((totalGst/2).toFixed(2));
    $('#items_json').val(JSON.stringify(billItems));
}

function removeBillItem(idx) {
    billItems.splice(idx, 1);
    refreshBillTable();
    updateTotals();
}

/* helper to read CSRF cookie (Django default) */
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            // Does this cookie string begin with the name we want?
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

$(function () {
    // Selling price recalculation when manual value or MRP/default discount changes
    $('#bill_manual_disc, #bill_mrp, #bill_default_disc').on('input change', recalcSellingPrice);

    // Robust change handler that reads data-default-disc and data-stock safely
    $('#bill_mrp').on('change', function () {
        const sel = this;
        const opt = (sel.selectedOptions && sel.selectedOptions[0]) || sel.options[sel.selectedIndex];
        if (!opt) return;

        const defaultDisc = opt.getAttribute('data-default-disc') || $(opt).data('defaultDisc') || 0;
        const stock = opt.getAttribute('data-stock') || $(opt).data('stock') || 0;

        $('#bill_default_disc').val(defaultDisc);
        $('#bill_stock_qty').text(stock);
        recalcSellingPrice();
    });

    // Toggle manual discount UI
    $('#bill_manual_disc_check').on('change', function () {
        if ($(this).is(':checked')) {
            $('#bill_manual_disc_container').show();
        } else {
            $('#bill_manual_disc_container').hide();
            $('#bill_manual_disc').val('0');
            recalcSellingPrice();
        }
    });

    $('#btn_add_to_bill').on('click', function () {
        const qty = parseInt($('#bill_qty').val()) || 0;
        const stockQty = parseInt($('#bill_stock_qty').text()) || 0;

        if (qty <= 0 || qty > stockQty) {
            alert('Invalid quantity or exceeds stock.');
            if (qty > stockQty) $('#bill_qty').val(stockQty);
            return;
        }

        const brandText = $('#bill_brand option:selected').text();
        const categoryText = $('#bill_category option:selected').text();
        const sectionText = $('#bill_section option:selected').text();
        const sizeText = $('#bill_size option:selected').text();
        const productId = $('#bill_mrp').val();
        if (!productId) {
            alert('Select MRP / product.');
            return;
        }

        const mrp = parseFloat($('#bill_mrp option:selected').text()) || 0;
        const price = parseFloat($('#bill_selling_price').val()) || 0;
        const discount = mrp > 0 ? (1 - price / mrp) * 100 : 0;
        const gstPercent = parseFloat($('#bill_mrp option:selected').data('gst')) || 0;

        // Manual discount validation: if manual discount is enabled, ensure it does not exceed 15% of MRP
        const manualEnabled = $('#bill_manual_disc_check').is(':checked');
        const manualDiscRs = manualEnabled ? parseFloat($('#bill_manual_disc').val()) || 0 : 0;
        const maxAllowed = mrp * 0.15;
        if (manualEnabled && manualDiscRs > maxAllowed) {
            alert(`Manual discount cannot exceed  Max ₹${maxAllowed.toFixed(2)}.`);
            return;
        }

        const gstAmount = price * qty * gstPercent / 100;
        const finalAmount = price * qty + gstAmount;

        billItems.push({
            product_id: productId,
            brand: brandText,
            category: categoryText,
            section: sectionText,
            size: sizeText,
            qty: qty,
            mrp: mrp,
            price: price,
            discount: discount,
            gst_percent: gstPercent,
            gst_amount: gstAmount,
            final: finalAmount
        });

        refreshBillTable();
        updateTotals();
    });

    // Confirm on submit: show confirmation popup and only submit if confirmed
    $('#billing_form').on('submit', function (e) {
        e.preventDefault();

        // Basic validation: there must be at least one item
        if (billItems.length === 0) {
            alert('Please add at least one item to the bill before submitting.');
            return;
        }

        if (!confirm('Are you sure you want to submit the bill?')) {
            return;
        }

        // Prepare form data and include items_json (ensure server accepts multipart/form-data or JSON)
        const $form = $(this);
        const url = $form.attr('action') || window.location.href;
        // Use FormData so CSRF token from form is included automatically if in a hidden input
        const formEl = $form.get(0);
        const formData = new FormData(formEl);
        // make sure items are included/updated
        formData.set('items_json', JSON.stringify(billItems));

        const csrftoken = getCookie('csrftoken');

        $.ajax({
            url: url,
            method: 'POST',
            data: formData,
            processData: false,
            contentType: false,
            headers: {
                'X-CSRFToken': csrftoken,
                'Accept': 'application/json'
            },
            success: function (resp) {
                // Expect JSON response with invoice_url
                // Example: { success: true, invoice_url: "/invoice/123/print/?download=1" }
                try {
                    if (typeof resp === 'string') resp = JSON.parse(resp);
                } catch (e) { /* ignore */ }

                if (resp && resp.success && resp.invoice_url) {
                    // Redirect to invoice print page; include download=1 to auto-download PDF
                    window.location.href = resp.invoice_url;
                } else if (resp && resp.redirect_url) {
                    window.location.href = resp.redirect_url;
                } else {
                    // fallback: submit normally
                    // If server doesn't return JSON, do a normal form submit as last resort
                    formEl.submit();
                }
            },
            error: function (xhr, status, err) {
                alert('Failed to submit bill. See console for details.');
                console.error('Billing submit error', status, err, xhr.responseText);
            }
        });
    });

    // Purchase MSP = MRP * 1.15 and discount interlink (unchanged)
    function recalcPurchase() {
        const mrp = parseFloat($('#pur_mrp').val()) || 0;
        const discPercent = parseFloat($('#pur_disc_percent').val()) || 0;
        const discRs = parseFloat($('#pur_disc_rs').val()) || 0;
        let price = parseFloat($('#pur_price').val()) || 0;

        // priority – if percent typed, compute price & discRs
        if (document.activeElement.id === 'pur_disc_percent') {
            price = mrp - (mrp * discPercent / 100);
            $('#pur_price').val(price.toFixed(2));
            $('#pur_disc_rs').val((mrp - price).toFixed(2));
        } else if (document.activeElement.id === 'pur_disc_rs') {
            price = mrp - discRs;
            $('#pur_price').val(price.toFixed(2));
            $('#pur_disc_percent').val(((discRs / mrp) * 100).toFixed(2));
        } else if (document.activeElement.id === 'pur_price') {
            const disc = mrp - price;
            $('#pur_disc_rs').val(disc.toFixed(2));
            $('#pur_disc_percent').val(((disc / mrp) * 100).toFixed(2));
        }

        $('#pur_msp').val((mrp * 1.15).toFixed(2));
    }

    $('#pur_mrp, #pur_disc_percent, #pur_disc_rs, #pur_price').on('input', recalcPurchase);

//    $('#bill_stock_qty').text(data.stock_qty);
//    $('#bill_qty').attr('max', data.stock_qty);

    // Purchase add button (unchanged)
    $('#btn_add_for_billing').on('click', function () {
        const qty = parseInt($('#pur_qty').val()) || 0;
        if (qty <= 0) {
            alert('Quantity must be > 0');
            return;
        }
        const brandText = $('#pur_brand option:selected').text();
        const categoryText = $('#pur_category option:selected').text();
        const sectionText = $('#pur_section option:selected').text();
        const sizeText = $('#pur_size option:selected').text();
        if (!$('#pur_size').val()) {
            alert('Select product hierarchy');
            return;
        }

        const item = {
            brand_id: $('#pur_brand').val(),
            category_id: $('#pur_category').val(),
            section_id: $('#pur_section').val(),
            size_id: $('#pur_size').val(),
            brand: brandText,
            category: categoryText,
            section: sectionText,
            size: sizeText,
            mrp: parseFloat($('#pur_mrp').val()) || 0,
            price: parseFloat($('#pur_price').val()) || 0,
            disc_percent: parseFloat($('#pur_disc_percent').val()) || 0,
            disc_rs: parseFloat($('#pur_disc_rs').val()) || 0,
            qty: qty,
            gst: parseFloat($('#pur_gst').val()) || 0,
            msp: parseFloat($('#pur_msp').val()) || 0
        };

        purchaseItems.push(item);
        $('#pur_items_json').val(JSON.stringify(purchaseItems));

        const $tbody = $('#purchase_items_table tbody');
        $tbody.append(`
            <tr>
                <td>${item.brand}</td>
                <td>${item.category}</td>
                <td>${item.section}</td>
                <td>${item.size}</td>
                <td>${item.mrp.toFixed(2)}</td>
                <td>${item.price.toFixed(2)}</td>
                <td>${item.disc_percent.toFixed(2)}%</td>
                <td>${item.gst.toFixed(2)}%</td>
                <td>${item.qty}</td>
                <td>${item.msp.toFixed(2)}</td>
                <td></td>
            </tr>
        `);
    });
});

$("#printBtn").on("click", function () {
    window.print();
});

//$.ajax({
//    url: "/billing/",
//    type: "POST",
//    data: formData,
//    success: function (resp) {
//        if (resp.success && resp.invoice_url) {
//
//            // Open PDF in a new hidden tab (auto-download)
//            let pdfWindow = window.open(resp.invoice_url, "_blank");
//
//            // After small delay, refresh billing page
//            setTimeout(function () {
//                window.location.href = "/billing/";
//            }, 1500); // 1.5 seconds
//        }
//    }
//});