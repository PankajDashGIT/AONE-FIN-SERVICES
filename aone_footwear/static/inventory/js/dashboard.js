console.log("dashboard.js loaded");

/* -------------------------------
   CATEGORY LOADING FOR SECTION
--------------------------------*/
document.getElementById("sec_brand").addEventListener("change", function () {
    fetch(`/api/categories/?brand_id=${this.value}`)
        .then(res => res.json())
        .then(data => {
            let box = document.getElementById("sec_category");
            box.innerHTML = `<option value="">Select Category</option>`;
            data.forEach(cat => {
                box.innerHTML += `<option value="${cat.id}">${cat.name}</option>`;
            });
        });
});

/* -------------------------------
   CATEGORY LOADING FOR SIZE
--------------------------------*/
document.getElementById("size_brand").addEventListener("change", function () {
    fetch(`/api/categories/?brand_id=${this.value}`)
        .then(res => res.json())
        .then(data => {
            size_category.innerHTML = `<option value="">Select Category</option>`;
            data.forEach(cat => {
                size_category.innerHTML += `<option value="${cat.id}">${cat.name}</option>`;
            });
            size_section.innerHTML = `<option value="">Select Section</option>`;
        });
});

/* -------------------------------
   SECTION LOADING FOR SIZE
--------------------------------*/
document.getElementById("size_category").addEventListener("change", function () {
    fetch(`/api/sections/?category_id=${this.value}`)
        .then(res => res.json())
        .then(data => {
            size_section.innerHTML = `<option value="">Select Section</option>`;
            data.forEach(sec => {
                size_section.innerHTML += `<option value="${sec.id}">${sec.name}</option>`;
            });
        });
});
