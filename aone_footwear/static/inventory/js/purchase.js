/* inventory/js/purchase.js
   Rewritten to support:
   - Independent dropdowns (no cascading AJAX)
   - Add / Edit / Remove line items
   - Form validation before submit
   - Totals (count, qty, approx amount)
*/

console.log("purchase.js (Version A2)");

let purchaseItems = [];
let editingIndex = -1;

function updateItemsJSON() {
    document.getElementById("items_json").value = JSON.stringify(purchaseItems);
    renderPurchaseTable();
    renderTotals();
}

/* -------------------------------
   AUTO CALCULATIONS
--------------------------------*/

function safeFloat(v) {
    let n = parseFloat(v);
    return isNaN(n) ? 0 : n;
}

function recalcPurchaseFields() {
    let mrp = safeFloat($("#pur_mrp").val());
    let price = safeFloat($("#pur_price").val());
    let discP = safeFloat($("#pur_disc_percent").val());
    let discR = safeFloat($("#pur_disc_rs").val());

    const activeId = document.activeElement ? document.activeElement.id : "";

    // ---------- When Discount % is edited ----------
    if (activeId === "pur_disc_percent" && mrp > 0) {
        discR = (mrp * discP) / 100;
        price = mrp - discR;

        $("#pur_disc_rs").val(discR.toFixed(2));
        $("#pur_price").val(price.toFixed(2));
    }

    // ---------- When Discount Rs is edited ----------
    else if (activeId === "pur_disc_rs" && mrp > 0) {
        discP = (discR / mrp) * 100;
        price = mrp - discR;

        $("#pur_disc_percent").val(discP.toFixed(2));
        $("#pur_price").val(price.toFixed(2));
    }

    // ---------- When Billing Price is edited ----------
    else if (activeId === "pur_price" && mrp > 0) {
        discR = mrp - price;
        discP = (discR / mrp) * 100;

        $("#pur_disc_rs").val(discR.toFixed(2));
        $("#pur_disc_percent").val(discP.toFixed(2));
    }

    // ---------- When MRP is edited ----------
    else if (activeId === "pur_mrp" && mrp > 0 && price > 0) {
        discR = mrp - price;
        discP = (discR / mrp) * 100;

        $("#pur_disc_rs").val(discR.toFixed(2));
        $("#pur_disc_percent").val(discP.toFixed(2));
    }

    // ---------- MSP ----------
    let msp = price + (price * 0.20);
    $("#pur_msp").val(msp ? msp.toFixed(2) : "");
}

$("#pur_mrp, #pur_price, #pur_disc_percent, #pur_disc_rs, #pur_gst, #pur_qty").on("input", recalcPurchaseFields);

/* -------------------------------
   VALIDATION
--------------------------------*/

function validateProductEntry() {
    const brand = $("#pur_brand").val();
    const category = $("#pur_category").val();
    const section = $("#pur_section").val();
    const size = $("#pur_size").val();
    const mrp = $("#pur_mrp").val();
    const price = $("#pur_price").val();
    const qty = $("#pur_qty").val();

    let missing = [];
    if (!brand) missing.push("Brand");
    if (!category) missing.push("Category");
    if (!section) missing.push("Section");
    if (!size) missing.push("Size");
    if (!mrp) missing.push("MRP");
    if (!price) missing.push("Billing Price");
    if (!qty || safeFloat(qty) <= 0) missing.push("Quantity (must be > 0)");

    if (missing.length) {
        alert("Please fill: " + missing.join(", "));
        return false;
    }
    return true;
}

/* -------------------------------
   ADD / UPDATE ITEM
--------------------------------*/

function clearProductEntry() {
    $("#pur_brand").val("");
    $("#pur_category").val("");
    $("#pur_section").val("");
    $("#pur_size").val("");
    $("#pur_mrp").val("");
    $("#pur_price").val("");
    $("#pur_disc_percent").val("");
    $("#pur_disc_rs").val("");
    $("#pur_gst").val("0");
    $("#pur_qty").val("1");
    $("#pur_msp").val("");
    // reset edit state
    editingIndex = -1;
    $("#btn_add_for_billing").text("+ Add Item").removeClass("btn-warning").addClass("btn-success");
    $("#btn_cancel_edit").addClass("d-none");
}

$("#btn_add_for_billing").click(function (e) {
    e.preventDefault();

    if (!validateProductEntry()) return;

    const item = {
        brand_id: $("#pur_brand").val(),
        category_id: $("#pur_category").val(),
        section_id: $("#pur_section").val(),
        size_id: $("#pur_size").val(),

        brand_name: $("#pur_brand option:selected").text(),
        category_name: $("#pur_category option:selected").text(),
        section_name: $("#pur_section option:selected").text(),
        size_name: $("#pur_size option:selected").text(),

        mrp: safeFloat($("#pur_mrp").val()),
        price: safeFloat($("#pur_price").val()),
        discount_percent: safeFloat($("#pur_disc_percent").val()),
        discount_rs: safeFloat($("#pur_disc_rs").val()),
        gst_percent: safeFloat($("#pur_gst").val()),
        qty: parseInt($("#pur_qty").val() || 0),
        msp: safeFloat($("#pur_msp").val() || 0),
    };

    // gst amount (per line)
    item.gst_amount = ((item.price * item.qty) * item.gst_percent) / 100;
    item.line_total = (item.price * item.qty) + item.gst_amount;

    if (editingIndex >= 0) {
        // update existing
        purchaseItems[editingIndex] = item;
        editingIndex = -1;
    } else {
        // append new
        purchaseItems.push(item);
    }

    updateItemsJSON();
    clearProductEntry();
});

/* Cancel edit */
$("#btn_cancel_edit").click(function (e) {
    e.preventDefault();
    clearProductEntry();
});

/* -------------------------------
   RENDER TABLE / EDIT / REMOVE
--------------------------------*/

function renderPurchaseTable() {
    let tbody = $("#purchase_items_table tbody");
    tbody.html("");

    purchaseItems.forEach((i, idx) => {
        tbody.append(`
            <tr>
                <td>${escapeHtml(i.brand_name)}</td>
                <td>${escapeHtml(i.category_name)}</td>
                <td>${escapeHtml(i.section_name)}</td>
                <td>${escapeHtml(i.size_name)}</td>
                <td>${i.mrp.toFixed(2)}</td>
                <td>${i.price.toFixed(2)}</td>
                <td>${i.discount_rs.toFixed(2)}</td>
                <td>${i.discount_percent.toFixed(2)}</td>
                <td>${i.gst_percent.toFixed(2)}</td>
                <td>${i.qty}</td>
                <td>${i.msp.toFixed(2)}</td>
                <td>
                    <button class="btn btn-sm btn-primary" onclick="editItem(${idx})">Edit</button>
                    <button class="btn btn-sm btn-danger" onclick="removeItem(${idx})">Remove</button>
                </td>
            </tr>
        `);
    });
}

function escapeHtml(unsafe) {
    return (unsafe + '')
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

function editItem(index) {
    const i = purchaseItems[index];
    editingIndex = index;

    $("#pur_brand").val(i.brand_id);
    $("#pur_category").val(i.category_id);
    $("#pur_section").val(i.section_id);
    $("#pur_size").val(i.size_id);

    $("#pur_mrp").val(i.mrp);
    $("#pur_price").val(i.price);
    $("#pur_disc_percent").val(i.discount_percent);
    $("#pur_disc_rs").val(i.discount_rs);
    $("#pur_gst").val(i.gst_percent);
    $("#pur_qty").val(i.qty);
    $("#pur_msp").val(i.msp);

    $("#btn_add_for_billing").text("Update Item").removeClass("btn-success").addClass("btn-warning");
    $("#btn_cancel_edit").removeClass("d-none");
    // scroll to left panel (optional)
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

function removeItem(index) {
    if (!confirm("Remove this item?")) return;
    purchaseItems.splice(index, 1);
    updateItemsJSON();
}

/* -------------------------------
   TOTALS
--------------------------------*/

function renderTotals() {
    let totItems = purchaseItems.length;
    let totQty = purchaseItems.reduce((s, x) => s + (x.qty || 0), 0);
    let totAmount = purchaseItems.reduce((s, x) => s + (x.line_total || 0), 0);

    $("#tot_items").text(totItems);
    $("#tot_qty").text(totQty);
    $("#tot_amount").text(totAmount.toFixed(2));
}

/* -------------------------------
   SUBMIT VALIDATION
--------------------------------*/

$("#purchase_form").on("submit", function (e) {
    // ensure items_json is current
    updateItemsJSON();

    if (purchaseItems.length === 0) {
        alert("Add at least one purchase item before submitting the bill.");
        e.preventDefault();
        return false;
    }

    // Validate bill header fields (use names rendered by Django form)
    const supplier = $('select[name="supplier"]').val();
    const billNo = $('input[name="bill_number"]').val();
    const billDate = $('input[name="bill_date"]').val();
    const paymentMode = $('select[name="payment_mode"]').val();

    let missing = [];
    if (!supplier) missing.push("Supplier");
    if (!billNo) missing.push("Bill Number");
    if (!billDate) missing.push("Bill Date");
    if (!paymentMode) missing.push("Payment Mode");

    if (missing.length) {
        alert("Please fill bill header: " + missing.join(", "));
        e.preventDefault();
        return false;
    }

    // let normal form submission continue (server side will save)
    return true;
});

/* Initialize (if server rendered defaults etc.) */
$(function () {
    renderPurchaseTable();
    renderTotals();
});

$(document).ready(function () {

    function checkBillExists() {
        let supplierId = $("#id_supplier").val();
        let billNo = $("#id_bill_number").val().trim();

        if (!supplierId || !billNo) {
            $("#bill_check_msg").html("");
            return;
        }

        $.ajax({
            url: "/purchase/check-bill/",
            method: "GET",
            data: {
                supplier_id: supplierId,
                bill_number: billNo
            },
            success: function (resp) {
                if (resp.exists) {
                    $("#bill_check_msg").html(
                        "<span style='color:red; font-weight:bold;'>❌ This bill already exists for this supplier.</span>"
                    );
                } else {
                    $("#bill_check_msg").html(
                        "<span style='color:green; font-weight:bold;'>✅ Bill number is available.</span>"
                    );
                }
            }
        });
    }

    // Trigger validation when supplier changes or bill number typed
    $("#id_supplier").on("change", checkBillExists);
    $("#id_bill_number").on("keyup change", checkBillExists);

});