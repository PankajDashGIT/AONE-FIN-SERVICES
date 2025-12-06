// Cascading selects for ledger page (brand -> category -> section -> size) and auto-submit
// Expects API endpoints similar to:
// /api/categories/?brand_id=..., /api/sections/?category_id=..., /api/sizes/?section_id=...
// Also listens to supplier select changes (no cascade for supplier).

(function () {
    function fillSelect(el, placeholder, items, textKey='name') {
        if (!el) return;
        el.innerHTML = `<option value="">${placeholder}</option>`;
        if (!items || !items.length) return;
        items.forEach(it => {
            const opt = document.createElement('option');
            opt.value = it.id;
            opt.textContent = it[textKey] || it.name || it.label || it.value;
            el.appendChild(opt);
        });
    }

    const brandEl = document.getElementById('led_brand');
    const catEl = document.getElementById('led_category');
    const secEl = document.getElementById('led_section');
    const sizeEl = document.getElementById('led_size');
    const supplierEl = document.getElementById('led_supplier');
    const form = document.getElementById('ledger_filters');

    if (!brandEl) return;

    brandEl.addEventListener('change', function () {
        const brandId = this.value;
        fillSelect(catEl, 'Category', []);
        fillSelect(secEl, 'Section', []);
        fillSelect(sizeEl, 'Size', []);

        if (!brandId) {
            form.submit(); // user likely wants results for no-brand selection
            return;
        }

        fetch(`/api/categories/?brand_id=${encodeURIComponent(brandId)}`)
            .then(r => r.json())
            .then(data => {
                fillSelect(catEl, 'Category', data);
                // optionally submit automatically
                form.submit();
            })
            .catch(e => {
                console.error('Failed to load categories', e);
                form.submit();
            });
    });

    catEl && catEl.addEventListener('change', function () {
        const catId = this.value;
        fillSelect(secEl, 'Section', []);
        fillSelect(sizeEl, 'Size', []);

        if (!catId) {
            form.submit();
            return;
        }

        fetch(`/api/sections/?category_id=${encodeURIComponent(catId)}`)
            .then(r => r.json())
            .then(data => {
                fillSelect(secEl, 'Section', data);
                form.submit();
            })
            .catch(e => {
                console.error('Failed to load sections', e);
                form.submit();
            });
    });

    secEl && secEl.addEventListener('change', function () {
        const secId = this.value;
        fillSelect(sizeEl, 'Size', []);

        if (!secId) {
            form.submit();
            return;
        }

        fetch(`/api/sizes/?section_id=${encodeURIComponent(secId)}`)
            .then(r => r.json())
            .then(data => {
                fillSelect(sizeEl, 'Size', data, 'label');
                form.submit();
            })
            .catch(e => {
                console.error('Failed to load sizes', e);
                form.submit();
            });
    });

    // If supplier changes, just submit (no cascading)
    supplierEl && supplierEl.addEventListener('change', function () {
        form.submit();
    });

    // If size changed, submit to apply filters
    sizeEl && sizeEl.addEventListener('change', function () {
        form.submit();
    });
})();