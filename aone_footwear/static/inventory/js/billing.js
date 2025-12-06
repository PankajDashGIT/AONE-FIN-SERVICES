
// inventory/static/inventory/js/billing.js

let billItems = [];
let purchaseItems = [];

// global array that holds items already added to the bill
// billItems should be filled when you click "Add to Bill"

function updateTotals() {
    let totalQty = 0;
    let subtotal = 0;
    let totalGst = 0;

    billItems.forEach(item => {
        const qty = Number(item.qty) || 0;
        const finalPrice = Number(item.final_price) || 0;   // selling price per unit
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
    const manualDisc = parseFloat($('#bill_manual_disc').val()) || 0;
    const totalDisc = defaultDisc + manualDisc;
    const price = mrp - (mrp * totalDisc / 100);
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

$(function () {
    // Selling price recalculation
    $('#bill_manual_disc').on('input', recalcSellingPrice);

    $('#btn_add_to_bill').on('click', function () {
        const qty = parseInt($('#bill_qty').val()) || 0;
        const stock = parseInt($('#bill_stock_qty').text()) || 0;

        if (qty > stock) {
            alert(`Only ${stock} items left in stock.`);
            $('#bill_qty').val(stock);   // auto-correct
            return;                       // stop adding
        }

        const stock = parseInt($('#bill_stock_qty').text()) || 0;
        if (qty <= 0 || qty > stock) {
            alert('Invalid quantity or exceeds stock.');
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
        const discount = (1 - price / mrp) * 100;
        const gstPercent = parseFloat($('#bill_mrp option:selected').data('gst')) || 0;
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
    });

    // Purchase MSP = MRP * 1.15 and discount interlink
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

    $('#bill_stock_qty').text(data.stock_qty);
    $('#bill_qty').attr('max', data.stock_qty);

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
