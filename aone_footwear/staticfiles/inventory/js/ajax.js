function loadProductInfo(sizeId) {
    fetch(`/api/product-info/?size_id=${sizeId}`)
        .then(response => response.json())
        .then(data => {
            document.getElementById('mrp').value = data.mrp;
            document.getElementById('stock_qty').innerText = data.stock_qty;
        })
        .catch(err => console.error("Error fetching product info:", err));
}

// inventory/static/inventory/js/ajax.js
function loadOptions(url, params, targetSelect, placeholder) {
    const qs = new URLSearchParams(params).toString();
    fetch(url + '?' + qs)
        .then(resp => resp.json())
        .then(data => {
            const $sel = $(targetSelect);
            $sel.empty();
            $sel.append(`<option value="">${placeholder}</option>`);
            data.forEach(row => {
                const text = row.name || row.value;
                $sel.append(`<option value="${row.id}">${text}</option>`);
            });
        });
}

$(function () {
    // Billing cascade
    $('#bill_brand').on('change', function () {
        loadOptions('/api/categories/', {brand_id: this.value}, '#bill_category', 'Select Category');
    });
    $('#bill_category').on('change', function () {
        loadOptions('/api/sections/', {category_id: this.value}, '#bill_section', 'Select Section');
    });
    $('#bill_section').on('change', function () {
        loadOptions('/api/sizes/', {section_id: this.value}, '#bill_size', 'Select Size');
    });

    $('#bill_size').on('change', function () {
        fetch('/api/product-info/?' + new URLSearchParams({
            brand_id: $('#bill_brand').val(),
            category_id: $('#bill_category').val(),
            section_id: $('#bill_section').val(),
            size_id: $('#bill_size').val()
        }))
            .then(r => r.json())
            .then(data => {
                const $mrp = $('#bill_mrp');
                $mrp.empty().append('<option value="">Select MRP</option>');
                if (data.length > 0) {
                    data.forEach(p => {
                        $mrp.append(`<option data-default-disc="${p.default_discount}"
                                      data-gst="${p.gst_percent}"
                                      data-stock="${p.stock_qty}"
                                      value="${p.product_id}">${p.mrp}</option>`);
                    });
                    $('#bill_stock_qty').text(data[0].stock_qty);
                }
            });
    });

    $('#bill_mrp').on('change', function () {
        const opt = this.selectedOptions[0];
        if (!opt) return;
        $('#bill_default_disc').val(opt.dataset.defaultDisc);
        $('#bill_stock_qty').text(opt.dataset.stock);
        recalcSellingPrice();
    });

    // Purchase cascade – reuse same endpoints
    $('#pur_brand').on('change', function () {
        loadOptions('/api/categories/', {brand_id: this.value}, '#pur_category', 'Select Category');
    });
    $('#pur_category').on('change', function () {
        loadOptions('/api/sections/', {category_id: this.value}, '#pur_section', 'Select Section');
    });
    $('#pur_section').on('change', function () {
        loadOptions('/api/sizes/', {section_id: this.value}, '#pur_size', 'Select Size');
    });
});
