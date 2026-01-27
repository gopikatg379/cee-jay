document.querySelectorAll(".dropdown").forEach(drop => {
  drop.addEventListener("click", function (e) {
    e.stopPropagation();
    this.querySelector("div").style.display =
      this.querySelector("div").style.display === "block" ? "none" : "block";
  });
});

document.addEventListener("click", () => {
  document.querySelectorAll(".dropdown div").forEach(d => {
    d.style.display = "none";
  });
});

document.addEventListener('DOMContentLoaded', () => {
    const btnForm = document.getElementById('btn-show-form');
    const btnList = document.getElementById('btn-show-list');
    const viewForm = document.getElementById('view-form');
    const viewList = document.getElementById('view-list');
    const searchBar = document.getElementById('search-bar');

    btnForm.addEventListener('click', () => {
        viewForm.classList.remove('d-none');
        viewList.classList.add('d-none');

        btnForm.classList.add('active');
        btnList.classList.remove('active');

        if (searchBar) searchBar.classList.add('d-none');

        history.pushState({}, '', '?mode=add');
    });

    btnList.addEventListener('click', () => {
        viewList.classList.remove('d-none');
        viewForm.classList.add('d-none');

        btnList.classList.add('active');
        btnForm.classList.remove('active');

        if (searchBar) searchBar.classList.remove('d-none');

    });
});