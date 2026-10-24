document.querySelectorAll("[data-copy]").forEach((btn) => {
  btn.addEventListener("click", async () => {
    const text = btn.dataset.copy;
    try {
      await navigator.clipboard.writeText(text);
    } catch (e) {
      const field = document.getElementById(btn.dataset.target);
      if (field) {
        field.select();
        document.execCommand("copy");
      }
    }
    const old = btn.textContent;
    btn.textContent = "Kopiert ✔";
    setTimeout(() => (btn.textContent = old), 1500);
  });
});
